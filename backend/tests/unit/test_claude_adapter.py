"""Unit tests for ClaudeAdapter — all external calls are mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from backend.adapters.base import StreamInput
from backend.adapters.claude import (
    ClaudeAdapter,
    _build_anthropic_messages,
    _build_system_prompt,
    _blocks_to_text,
)
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.adapters.mcp_client import MCPTool
from backend.domain.agent import AgentCapabilities
from backend.domain.message import TextBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory, MessageRole
from backend.schemas.skill import SkillWithContent
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Fake Anthropic stream helpers
# ---------------------------------------------------------------------------

def _text_block_start() -> SimpleNamespace:
    block = SimpleNamespace(type="text")
    return SimpleNamespace(type="content_block_start", content_block=block)


def _text_delta(text: str) -> SimpleNamespace:
    delta = SimpleNamespace(type="text_delta", text=text)
    return SimpleNamespace(type="content_block_delta", delta=delta)


def _block_stop() -> SimpleNamespace:
    return SimpleNamespace(type="content_block_stop")


def _tool_block_start(tool_id: str, tool_name: str) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", id=tool_id, name=tool_name)
    return SimpleNamespace(type="content_block_start", content_block=block)


def _tool_delta(partial_json: str) -> SimpleNamespace:
    delta = SimpleNamespace(type="input_json_delta", partial_json=partial_json)
    return SimpleNamespace(type="content_block_delta", delta=delta)


class _FakeStream:
    def __init__(self, events: list) -> None:
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for e in self._events:
            yield e


def _patch_stream(events: list):
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _FakeStream(events)
    return mock_client


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="agent-1", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    with patch("backend.adapters.claude.anthropic.AsyncAnthropic"):
        inst = ClaudeAdapter(api_key="sk-test")
        yield inst


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities(adapter):
    caps = adapter.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_diff is True
    assert caps.supports_approval is True


# ---------------------------------------------------------------------------
# Basic stream lifecycle
# ---------------------------------------------------------------------------

async def test_stream_yields_start_and_done(adapter):
    adapter._client = _patch_stream([])
    events = await collect_stream(adapter.stream(_make_inp()))
    assert isinstance(events[0], AgentStartEvent)
    assert events[0].agent_id == "agent-1"
    assert events[0].thread_id == "thread-1"
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_text_block_lifecycle(adapter):
    sdk_events = [_text_block_start(), _text_delta("foo"), _text_delta("bar"), _block_stop()]
    adapter._client = _patch_stream(sdk_events)
    events = await collect_stream(adapter.stream(_make_inp()))

    block_starts = [e for e in events if isinstance(e, BlockStartEvent)]
    block_stops = [e for e in events if isinstance(e, BlockStopEvent)]
    assert len(block_starts) == 1
    assert isinstance(block_starts[0].block, TextBlock)
    assert len(block_stops) == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_stream_api_error_yields_error_event(adapter):
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = anthropic.APIError(
        message="rate limit", request=MagicMock(), body=None
    )
    adapter._client = mock_client
    events = await collect_stream(adapter.stream(_make_inp()))
    assert any(isinstance(e, AgentErrorEvent) for e in events)
    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert "rate limit" in error_events[0].error


async def test_stream_api_error_does_not_raise(adapter):
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None
    )
    adapter._client = mock_client
    events = await collect_stream(adapter.stream(_make_inp()))
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# MCP tool calls — has side effects → ApprovalBlock emitted
# ---------------------------------------------------------------------------

async def test_stream_mcp_tool_has_side_effects_emits_approval_block(adapter):
    tool = MCPTool(
        name="run_command",
        description="runs a shell command",
        input_schema={"type": "object"},
        has_side_effects=True,
    )
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = [tool]
    mock_mcp.call_tool.return_value = SimpleNamespace(content=[SimpleNamespace(text="ok")])
    adapter._mcp_client = mock_mcp

    sdk_events = [
        _tool_block_start("tu-2", "run_command"),
        _tool_delta('{"cmd": "npm test"}'),
        _block_stop(),
    ]
    adapter._client = _patch_stream(sdk_events)
    events = await collect_stream(adapter.stream(_make_inp(prompt="run tests")))

    # Approval block should appear as a BlockStartEvent with ApprovalBlock
    from backend.domain.message import ApprovalBlock
    approval_starts = [
        e for e in events
        if isinstance(e, BlockStartEvent) and isinstance(e.block, ApprovalBlock)
    ]
    assert len(approval_starts) == 1
    assert approval_starts[0].block.action == "run_command"


async def test_stream_mcp_fetch_failure_is_non_fatal(adapter):
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.side_effect = RuntimeError("connection lost")
    adapter._mcp_client = mock_mcp
    sdk_events = [_text_block_start(), _text_delta("hi"), _block_stop()]
    adapter._client = _patch_stream(sdk_events)

    events = await collect_stream(adapter.stream(_make_inp()))
    assert isinstance(events[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Helper: _blocks_to_text
# ---------------------------------------------------------------------------

def test_blocks_to_text_text_block():
    bid = "b1"
    text = _blocks_to_text([TextBlock(block_id=bid, content="hello")])
    assert text == "hello"


def test_blocks_to_text_tool_use_block():
    bid = "b2"
    text = _blocks_to_text([ToolUseBlock(block_id=bid, tool_name="read_file", output="content", status="completed")])
    assert "[Tool: read_file -> content]" in text


def test_blocks_to_text_thinking_block_skipped():
    from backend.domain.message import ThinkingBlock
    text = _blocks_to_text([ThinkingBlock(block_id="b3", content="internal thought")])
    assert text == ""


# ---------------------------------------------------------------------------
# Helper: _build_anthropic_messages
# ---------------------------------------------------------------------------

def test_build_anthropic_messages_empty_history():
    msgs = _build_anthropic_messages([], "what is 2+2?")
    assert len(msgs) == 1
    assert msgs[0] == {"role": "user", "content": "what is 2+2?"}


def test_build_anthropic_messages_with_history():
    history = [
        MessageInHistory(role=MessageRole.USER, blocks=[TextBlock(block_id="b1", content="hi")]),
        MessageInHistory(role=MessageRole.ASSISTANT, blocks=[TextBlock(block_id="b2", content="hello")]),
    ]
    msgs = _build_anthropic_messages(history, "how are you?")
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[-1] == {"role": "user", "content": "how are you?"}


def test_build_anthropic_messages_with_sender_prefix():
    history = [
        MessageInHistory(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(block_id="b1", content="done")],
            sender="CodeReviewer",
        )
    ]
    msgs = _build_anthropic_messages(history, "ok")
    assert msgs[0]["content"].startswith("[CodeReviewer]:")


# ---------------------------------------------------------------------------
# Helper: _build_system_prompt
# ---------------------------------------------------------------------------

def test_build_system_prompt_base_only():
    prompt = _build_system_prompt("You are helpful.", [])
    assert prompt == "You are helpful."


def test_build_system_prompt_with_skills():
    skill = SkillWithContent(
        id="s1", name="code_review", author_id="GUGA", is_public=True, is_active=True,
        content="## Review steps\n1. check types",
    )
    prompt = _build_system_prompt("Base prompt.", [skill])
    assert "Base prompt." in prompt
    assert "## Review steps" in prompt


def test_build_system_prompt_no_base_no_skills():
    prompt = _build_system_prompt(None, [])
    assert prompt == ""
