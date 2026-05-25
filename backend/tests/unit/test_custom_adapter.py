"""Unit tests for CustomAdapter — OpenAI SDK is fully mocked."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from backend.adapters.base import StreamInput
from backend.adapters.custom import (
    CustomAdapter,
    _build_openai_messages,
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
from backend.domain.message import ApprovalBlock, TextBlock
from backend.schemas.message import MessageInHistory, MessageRole
from backend.schemas.skill import SkillWithContent
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_chunk(content: str, finish: str | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(choices=[choice])


def _stop_chunk() -> SimpleNamespace:
    delta = SimpleNamespace(content=None, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason="stop")
    return SimpleNamespace(choices=[choice])


def _tool_chunk(idx: int, tool_id: str, name: str, args: str, finish: bool = False) -> SimpleNamespace:
    func = SimpleNamespace(name=name, arguments=args)
    tc = SimpleNamespace(index=idx, id=tool_id, function=func)
    delta = SimpleNamespace(content=None, tool_calls=[tc])
    finish_reason = "tool_calls" if finish else None
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


class _FakeStream:
    def __init__(self, chunks: list) -> None:
        self._chunks = chunks

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for c in self._chunks:
            yield c


def _patch_openai_client(chunks: list) -> MagicMock:
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=_FakeStream(chunks))
    return mock_client


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="custom-1", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    with patch("backend.adapters.custom.openai.AsyncOpenAI"):
        inst = CustomAdapter(api_key="sk-test", base_url="http://localhost:11434/v1")
        yield inst


@pytest.fixture
def adapter_with_mcp():
    mock_mcp = AsyncMock()
    mock_mcp.list_tools.return_value = []
    with patch("backend.adapters.custom.openai.AsyncOpenAI"):
        inst = CustomAdapter(api_key="sk-test", mcp_client=mock_mcp)
        inst._mock_mcp = mock_mcp
        yield inst


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities_no_mcp(adapter):
    caps = adapter.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_diff is True
    assert caps.supports_approval is False


def test_get_capabilities_with_mcp(adapter_with_mcp):
    caps = adapter_with_mcp.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_approval is True


# ---------------------------------------------------------------------------
# Basic stream lifecycle
# ---------------------------------------------------------------------------

async def test_stream_yields_start_and_done(adapter):
    adapter._client = _patch_openai_client([])
    events = await collect_stream(adapter.stream(_make_inp()))
    assert isinstance(events[0], AgentStartEvent)
    assert events[0].thread_id == "thread-1"
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_text_block_lifecycle(adapter):
    chunks = [_text_chunk("hello "), _text_chunk("world"), _stop_chunk()]
    adapter._client = _patch_openai_client(chunks)
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
    adapter._client = MagicMock()
    adapter._client.chat.completions.create = AsyncMock(
        side_effect=openai.APIError(message="quota exceeded", request=MagicMock(), body=None)
    )
    events = await collect_stream(adapter.stream(_make_inp()))
    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "quota exceeded" in error_events[0].error


# ---------------------------------------------------------------------------
# Tool calls — side effects → ApprovalBlock
# ---------------------------------------------------------------------------

async def test_stream_tool_call_has_side_effects(adapter_with_mcp):
    tool = MCPTool(
        name="write_file",
        description="writes a file",
        input_schema={"type": "object"},
        has_side_effects=True,
    )
    adapter_with_mcp._mock_mcp.list_tools.return_value = [tool]
    adapter_with_mcp._mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="wrote ok")]
    )

    chunks = [_tool_chunk(0, "tc-1", "write_file", '{"path":"x.py"}', finish=True)]
    adapter_with_mcp._client = _patch_openai_client(chunks)
    events = await collect_stream(adapter_with_mcp.stream(_make_inp(prompt="write file")))

    approval_starts = [
        e for e in events
        if isinstance(e, BlockStartEvent) and isinstance(e.block, ApprovalBlock)
    ]
    assert len(approval_starts) == 1
    assert approval_starts[0].block.action == "write_file"


async def test_stream_tool_call_no_side_effects(adapter_with_mcp):
    tool = MCPTool(
        name="read_file",
        description="reads a file",
        input_schema={"type": "object"},
        has_side_effects=False,
    )
    adapter_with_mcp._mock_mcp.list_tools.return_value = [tool]
    adapter_with_mcp._mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="contents")]
    )

    chunks = [_tool_chunk(0, "tc-1", "read_file", '{"path":"x.py"}', finish=True)]
    adapter_with_mcp._client = _patch_openai_client(chunks)
    events = await collect_stream(adapter_with_mcp.stream(_make_inp(prompt="read file")))

    approval_starts = [
        e for e in events
        if isinstance(e, BlockStartEvent) and isinstance(e.block, ApprovalBlock)
    ]
    assert len(approval_starts) == 0


# ---------------------------------------------------------------------------
# Helper: _build_openai_messages
# ---------------------------------------------------------------------------

def test_build_openai_messages_no_system():
    msgs = _build_openai_messages(None, [], [], "hello")
    assert len(msgs) == 1
    assert msgs[0] == {"role": "user", "content": "hello"}


def test_build_openai_messages_system_first():
    msgs = _build_openai_messages("You are helpful.", [], [], "hello")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "You are helpful."
    assert msgs[-1]["role"] == "user"


def test_build_openai_messages_skill_injected_into_system():
    skill = SkillWithContent(
        id="s1", name="sk", author_id="GUGA", is_public=True, is_active=True,
        content="## Do this",
    )
    msgs = _build_openai_messages("Base.", [skill], [], "hello")
    system_content = msgs[0]["content"]
    assert "Base." in system_content
    assert "## Do this" in system_content


def test_build_openai_messages_history_order():
    history = [
        MessageInHistory(role=MessageRole.USER, blocks=[TextBlock(block_id="b1", content="hi")]),
        MessageInHistory(role=MessageRole.ASSISTANT, blocks=[TextBlock(block_id="b2", content="hello")]),
    ]
    msgs = _build_openai_messages(None, [], history, "how are you?")
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user"]
    assert msgs[-1]["content"] == "how are you?"
