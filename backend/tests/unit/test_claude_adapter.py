"""Unit tests for ClaudeAdapter — all external calls are mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from backend.adapters.claude import (
    ClaudeAdapter,
    _build_anthropic_messages,
    _build_system_prompt,
)
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    ApprovalRequestEvent,
    TokenEvent,
)
from backend.adapters.mcp_client import MCPTool
from backend.domain.message import MessageEntity
from backend.domain.skill import SkillEntity
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Helpers to build fake Anthropic stream events
# ---------------------------------------------------------------------------

def _text_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_start_event(tool_id: str, tool_name: str) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", id=tool_id, name=tool_name)
    return SimpleNamespace(type="content_block_start", content_block=block)


def _tool_delta_event(partial_json: str) -> SimpleNamespace:
    return SimpleNamespace(type="input_json_delta", partial_json=partial_json)


def _tool_stop_event() -> SimpleNamespace:
    return SimpleNamespace(type="content_block_stop")


class _FakeStream:
    """Async context manager that yields pre-built Anthropic-like events."""

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
    """Return a patcher that replaces messages.stream with _FakeStream(events)."""
    fake = _FakeStream(events)
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = fake
    return mock_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    with patch("backend.adapters.claude.anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value = MagicMock()
        inst = ClaudeAdapter(
            agent_id="agent-1",
            agent_name="Claude",
            api_key="sk-test",
        )
        yield inst


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities(adapter):
    caps = adapter.get_capabilities()
    assert caps == {"supports_diff": True, "supports_approval": True}


# ---------------------------------------------------------------------------
# Basic stream lifecycle
# ---------------------------------------------------------------------------

async def test_stream_yields_start_and_done(adapter):
    adapter._client = _patch_stream([])
    events = await collect_stream(adapter.stream("hello", [], []))
    assert isinstance(events[0], AgentStartEvent)
    assert events[0].agent_id == "agent-1"
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_token_events(adapter):
    sdk_events = [_text_event("foo"), _text_event("bar")]
    adapter._client = _patch_stream(sdk_events)
    events = await collect_stream(adapter.stream("hello", [], []))
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) == 2
    assert token_events[0].content == "foo"
    assert token_events[1].content == "bar"


async def test_stream_start_before_tokens(adapter):
    adapter._client = _patch_stream([_text_event("hi")])
    events = await collect_stream(adapter.stream("hello", [], []))
    assert isinstance(events[0], AgentStartEvent)
    assert isinstance(events[1], TokenEvent)
    assert isinstance(events[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_stream_api_error_yields_error_event(adapter):
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = anthropic.APIError(
        message="rate limit", request=MagicMock(), body=None
    )
    adapter._client = mock_client
    events = await collect_stream(adapter.stream("hello", [], []))
    assert any(isinstance(e, AgentErrorEvent) for e in events)
    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert "rate limit" in error_events[0].error


async def test_stream_api_error_does_not_raise(adapter):
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = anthropic.APIError(
        message="server error", request=MagicMock(), body=None
    )
    adapter._client = mock_client
    # Should not raise — error is surfaced as AgentErrorEvent
    events = await collect_stream(adapter.stream("hello", [], []))
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# MCP tool calls — no side effects
# ---------------------------------------------------------------------------

async def test_stream_mcp_tool_no_side_effects(adapter):
    tool = MCPTool(
        name="read_file",
        description="reads a file",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        has_side_effects=False,
    )
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = [tool]
    mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="file contents")]
    )
    adapter._mcp_client = mock_mcp

    sdk_events = [
        _tool_start_event("tu-1", "read_file"),
        _tool_delta_event('{"path": "x.py"}'),
        _tool_stop_event(),
    ]
    adapter._client = _patch_stream(sdk_events)
    events = await collect_stream(adapter.stream("read x.py", [], []))

    approval_events = [e for e in events if isinstance(e, ApprovalRequestEvent)]
    assert len(approval_events) == 0
    # Tool result injected as token
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert any("file contents" in e.content for e in token_events)


# ---------------------------------------------------------------------------
# MCP tool calls — has side effects → ApprovalRequestEvent
# ---------------------------------------------------------------------------

async def test_stream_mcp_tool_has_side_effects(adapter):
    tool = MCPTool(
        name="run_command",
        description="runs a shell command",
        input_schema={"type": "object", "properties": {"cmd": {"type": "string"}}},
        has_side_effects=True,
    )
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = [tool]
    mock_mcp.call_tool.return_value = SimpleNamespace(content=[SimpleNamespace(text="ok")])
    adapter._mcp_client = mock_mcp

    sdk_events = [
        _tool_start_event("tu-2", "run_command"),
        _tool_delta_event('{"cmd": "npm test"}'),
        _tool_stop_event(),
    ]
    adapter._client = _patch_stream(sdk_events)
    events = await collect_stream(adapter.stream("run tests", [], []))

    approval_events = [e for e in events if isinstance(e, ApprovalRequestEvent)]
    assert len(approval_events) == 1
    assert approval_events[0].action == "run_command"


# ---------------------------------------------------------------------------
# MCP fetch failure is non-fatal
# ---------------------------------------------------------------------------

async def test_stream_mcp_fetch_failure_is_non_fatal(adapter):
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.side_effect = RuntimeError("connection lost")
    adapter._mcp_client = mock_mcp
    adapter._client = _patch_stream([_text_event("hi")])

    events = await collect_stream(adapter.stream("hello", [], []))
    # Stream should complete normally despite MCP failure
    assert isinstance(events[-1], AgentDoneEvent)
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert token_events[0].content == "hi"


# ---------------------------------------------------------------------------
# Helper: _build_anthropic_messages
# ---------------------------------------------------------------------------

def test_build_anthropic_messages_empty_history():
    msgs = _build_anthropic_messages([], "what is 2+2?")
    assert len(msgs) == 1
    assert msgs[0] == {"role": "user", "content": "what is 2+2?"}


def test_build_anthropic_messages_with_history():
    history = [
        MessageEntity(id="1", role="user", content="hi"),
        MessageEntity(id="2", role="assistant", content="hello"),
    ]
    msgs = _build_anthropic_messages(history, "how are you?")
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[-1] == {"role": "user", "content": "how are you?"}


def test_build_anthropic_messages_non_user_role_maps_to_assistant():
    history = [MessageEntity(id="1", role="system", content="be helpful")]
    msgs = _build_anthropic_messages(history, "hi")
    assert msgs[0]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Helper: _build_system_prompt
# ---------------------------------------------------------------------------

def test_build_system_prompt_base_only():
    prompt = _build_system_prompt("You are helpful.", [])
    assert prompt == "You are helpful."


def test_build_system_prompt_with_skills():
    skill = SkillEntity(id="s1", name="code_review", file_path="skills/code_review.md", content="## Review steps\n1. check types")
    prompt = _build_system_prompt("Base prompt.", [skill])
    assert "Base prompt." in prompt
    assert "## Review steps" in prompt


def test_build_system_prompt_skill_without_content_is_skipped():
    skill = SkillEntity(id="s1", name="empty_skill", file_path="skills/empty.md", content=None)
    prompt = _build_system_prompt("Base.", [skill])
    assert prompt == "Base."


def test_build_system_prompt_no_base_no_skills():
    prompt = _build_system_prompt(None, [])
    assert prompt == ""
