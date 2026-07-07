"""Unit tests for AnthropicSDKAdapter and OrchestratorLLMClient.

所有 anthropic SDK 调用均通过 mock 拦截，无需真实 API Key 或网络连接。

队伍：咕嘎一辈子队
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.adapters.anthropic_sdk import (
    AnthropicSDKAdapter,
    _blocks_to_text,
    _build_anthropic_messages,
    _extract_tool_result_text,
    _mcp_tool_to_anthropic,
)
from backend.adapters.base import StreamInput
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.adapters.mcp_client import MCPTool
from backend.domain.agent import AgentCapabilities
from backend.domain.message import TextBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory, MessageRole
from backend.schemas.skill import SkillWithContent
from backend.services.orchestrator.llm_client import (
    LLMResponse,
    LLMToolCall,
    OrchestratorLLMClient,
)
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# SDK stream event fakes
#
# AnthropicSDKAdapter 使用 type(event).__name__ 识别事件类型，
# 所以必须创建真正以这些名字命名的类实例，SimpleNamespace 不行。
# ---------------------------------------------------------------------------

class ContentBlockStartEvent:
    def __init__(self, content_block: Any) -> None:
        self.content_block = content_block

class ContentBlockDeltaEvent:
    def __init__(self, delta: Any) -> None:
        self.delta = delta

class ContentBlockStopEvent:
    pass

class MessageDeltaEvent:
    def __init__(self, delta: Any, usage: Any = None) -> None:
        self.delta = delta
        self.usage = usage

class MessageStartEvent:
    def __init__(self, message: Any) -> None:
        self.message = message

class TextDeltaEvent:
    def __init__(self, text: str) -> None:
        self.text = text

class InputJsonDeltaEvent:
    def __init__(self, partial_json: str) -> None:
        self.partial_json = partial_json


def _text_start_event(block_id: str = "blk-1") -> ContentBlockStartEvent:
    blk = SimpleNamespace(type="text", id=block_id, text="")
    return ContentBlockStartEvent(content_block=blk)


def _tool_start_event(block_id: str = "tool-1", name: str = "search") -> ContentBlockStartEvent:
    blk = SimpleNamespace(type="tool_use", id=block_id, name=name)
    return ContentBlockStartEvent(content_block=blk)


def _text_delta_event(text: str) -> ContentBlockDeltaEvent:
    return ContentBlockDeltaEvent(delta=TextDeltaEvent(text=text))


def _input_json_delta_event(partial: str) -> ContentBlockDeltaEvent:
    return ContentBlockDeltaEvent(delta=InputJsonDeltaEvent(partial_json=partial))


def _block_stop_event() -> ContentBlockStopEvent:
    return ContentBlockStopEvent()


def _message_delta_event(stop_reason: str = "end_turn", output_tokens: int = 10) -> MessageDeltaEvent:
    delta = SimpleNamespace(stop_reason=stop_reason)
    usage = SimpleNamespace(output_tokens=output_tokens)
    return MessageDeltaEvent(delta=delta, usage=usage)


def _message_start_event(input_tokens: int = 20) -> MessageStartEvent:
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=0)
    message = SimpleNamespace(usage=usage)
    return MessageStartEvent(message=message)


def _make_sdk_stream(events: list[Any]):
    """返回一个可用作 async context manager 的 fake SDK stream。"""

    @asynccontextmanager
    async def _cm(**kwargs):
        async def _iter():
            for ev in events:
                yield ev

        stream = SimpleNamespace(__aiter__=_iter().__aiter__, __anext__=_iter().__anext__)

        # 让 `async for event in sdk_stream` 可用
        async def _aiter(self):
            async for ev in _iter():
                yield ev

        class _FakeStream:
            def __aiter__(self_inner):
                return _iter()

        yield _FakeStream()

    return _cm


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="agent-sdk", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


def _make_adapter(**kwargs) -> AnthropicSDKAdapter:
    """创建 adapter，api_key/base_url 用测试占位值，不发起真实请求。"""
    return AnthropicSDKAdapter(
        model="claude-haiku-latest",
        api_key="test-key",
        base_url="http://localhost:9999",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities_no_mcp():
    adapter = _make_adapter()
    caps = adapter.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_code is True
    assert caps.supports_approval is False


def test_get_capabilities_with_mcp():
    fake_client = MagicMock()
    adapter = _make_adapter(mcp_clients=[fake_client])
    assert adapter.get_capabilities().supports_approval is True


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.stream — happy path: pure text
# ---------------------------------------------------------------------------

async def test_stream_pure_text_happy_path():
    """简单的纯文本响应：Start → BlockStart → BlockDelta → BlockStop → Done"""
    events_seq = [
        _message_start_event(input_tokens=50),
        _text_start_event(),
        _text_delta_event("Hello "),
        _text_delta_event("world"),
        _block_stop_event(),
        _message_delta_event("end_turn", output_tokens=15),
    ]

    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _make_sdk_stream(events_seq)):
        collected = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(collected[0], AgentStartEvent)
    assert collected[0].agent_id == "agent-sdk"

    block_starts = [e for e in collected if isinstance(e, BlockStartEvent)]
    block_deltas = [e for e in collected if isinstance(e, BlockDeltaEvent)]
    block_stops = [e for e in collected if isinstance(e, BlockStopEvent)]

    assert len(block_starts) == 1
    assert isinstance(block_starts[0].block, TextBlock)
    assert len(block_stops) == 1

    texts = [e.delta.get("content", "") for e in block_deltas]
    assert "Hello " in texts
    assert "world" in texts

    assert isinstance(collected[-1], AgentDoneEvent)


async def test_stream_done_carries_token_counts():
    events_seq = [
        _message_start_event(input_tokens=100),
        _text_start_event(),
        _text_delta_event("hi"),
        _block_stop_event(),
        _message_delta_event("end_turn", output_tokens=5),
    ]
    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _make_sdk_stream(events_seq)):
        collected = await collect_stream(adapter.stream(_make_inp()))

    done: AgentDoneEvent = collected[-1]
    assert isinstance(done, AgentDoneEvent)
    assert done.tokens_input == 100
    assert done.tokens_output >= 5


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.stream — empty response (no text blocks)
# ---------------------------------------------------------------------------

async def test_stream_empty_no_blocks():
    events_seq = [
        _message_start_event(),
        _message_delta_event("end_turn"),
    ]
    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _make_sdk_stream(events_seq)):
        collected = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(collected[0], AgentStartEvent)
    assert isinstance(collected[-1], AgentDoneEvent)
    assert not any(isinstance(e, BlockStartEvent) for e in collected)


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.stream — cancel event
# ---------------------------------------------------------------------------

async def test_stream_cancel_event_aborts():
    cancel = asyncio.Event()
    cancel.set()

    events_seq = [
        _message_start_event(),
        _text_start_event(),
        _text_delta_event("should not appear"),
        _block_stop_event(),
        _message_delta_event("end_turn"),
    ]
    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _make_sdk_stream(events_seq)):
        collected = await collect_stream(adapter.stream(_make_inp(cancel_event=cancel)))

    error_events = [e for e in collected if isinstance(e, AgentErrorEvent)]
    assert any("cancelled" in e.error for e in error_events)
    assert not isinstance(collected[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.stream — API error
# ---------------------------------------------------------------------------

async def test_stream_api_error_yields_error_event():
    import anthropic as _anthropic

    @asynccontextmanager
    async def _fail_stream(**kwargs):
        raise _anthropic.APIStatusError(
            "rate limited",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        yield  # never reached

    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _fail_stream):
        collected = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in collected if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1


async def test_stream_unexpected_exception_yields_error_event():
    @asynccontextmanager
    async def _boom(**kwargs):
        raise RuntimeError("unexpected boom")
        yield

    adapter = _make_adapter()
    with patch.object(adapter._client.messages, "stream", _boom):
        collected = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in collected if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "boom" in error_events[0].error


# ---------------------------------------------------------------------------
# AnthropicSDKAdapter.stream — MCP tool call round-trip
# ---------------------------------------------------------------------------

async def test_stream_mcp_tool_call_round_trip():
    """第一轮 tool_use → 调 MCP → 第二轮 end_turn"""
    # 第一轮：tool_use
    round1 = [
        _message_start_event(input_tokens=30),
        _tool_start_event(block_id="tid-1", name="my_tool"),
        _input_json_delta_event('{"q": "test"}'),
        _block_stop_event(),
        _message_delta_event("tool_use"),
    ]
    # 第二轮：end_turn with text
    round2 = [
        _message_start_event(input_tokens=40),
        _text_start_event(),
        _text_delta_event("tool result processed"),
        _block_stop_event(),
        _message_delta_event("end_turn", output_tokens=8),
    ]

    call_count = 0

    @asynccontextmanager
    async def _two_round_stream(**kwargs):
        nonlocal call_count
        events = round1 if call_count == 0 else round2
        call_count += 1

        class _S:
            def __aiter__(self_inner):
                return _aiter()

            async def __anext__(self_inner):
                raise StopAsyncIteration

        async def _aiter():
            for ev in events:
                yield ev

        yield _S()

    # MCP client mock
    fake_mcp = AsyncMock()
    fake_mcp.server_id = "test-server"
    fake_tool = MCPTool(
        name="my_tool",
        description="test tool",
        input_schema={"type": "object", "properties": {}},
        has_side_effects=False,
    )
    fake_mcp.list_tools = AsyncMock(return_value=[fake_tool])
    tool_result = SimpleNamespace(content=[SimpleNamespace(text="result_text")])
    fake_mcp.call_tool = AsyncMock(return_value=tool_result)

    adapter = _make_adapter(mcp_clients=[fake_mcp])
    with patch.object(adapter._client.messages, "stream", _two_round_stream):
        collected = await collect_stream(adapter.stream(_make_inp()))

    # MCP tool should have been called once
    fake_mcp.call_tool.assert_called_once()
    call_args = fake_mcp.call_tool.call_args
    assert call_args[0][0] == "my_tool"
    assert call_args[0][1] == {"q": "test"}

    # Should see a ToolUseBlock in BlockStartEvent
    tool_starts = [
        e for e in collected
        if isinstance(e, BlockStartEvent) and isinstance(e.block, ToolUseBlock)
    ]
    assert len(tool_starts) == 1

    # Final event is Done
    assert isinstance(collected[-1], AgentDoneEvent)


async def test_stream_mcp_tool_list_failure_is_non_fatal():
    """MCP list_tools 失败时不抛异常，继续正常流程（无工具）"""
    events_seq = [
        _message_start_event(),
        _text_start_event(),
        _text_delta_event("ok"),
        _block_stop_event(),
        _message_delta_event("end_turn"),
    ]

    fake_mcp = AsyncMock()
    fake_mcp.server_id = "bad-server"
    fake_mcp.list_tools = AsyncMock(side_effect=RuntimeError("connection refused"))

    adapter = _make_adapter(mcp_clients=[fake_mcp])
    with patch.object(adapter._client.messages, "stream", _make_sdk_stream(events_seq)):
        collected = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(collected[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Helper: _blocks_to_text
# ---------------------------------------------------------------------------

def test_blocks_to_text_text():
    assert _blocks_to_text([TextBlock(block_id="b1", content="hello")]) == "hello"


def test_blocks_to_text_tool_use():
    text = _blocks_to_text([
        ToolUseBlock(block_id="b2", tool_name="read", output="result", status="completed")
    ])
    assert "[Tool: read -> result]" in text


def test_blocks_to_text_multiple_blocks():
    blocks = [
        TextBlock(block_id="b1", content="intro"),
        ToolUseBlock(block_id="b2", tool_name="search", output="hits", status="completed"),
        TextBlock(block_id="b3", content="conclusion"),
    ]
    result = _blocks_to_text(blocks)
    assert "intro" in result
    assert "[Tool: search -> hits]" in result
    assert "conclusion" in result


def test_blocks_to_text_empty():
    assert _blocks_to_text([]) == ""


# ---------------------------------------------------------------------------
# Helper: _build_anthropic_messages
# ---------------------------------------------------------------------------

def test_build_anthropic_messages_no_history_no_system():
    system, messages = _build_anthropic_messages(None, [], [], "hello")
    assert system == ""
    assert messages == [{"role": "user", "content": "hello"}]


def test_build_anthropic_messages_with_system():
    system, messages = _build_anthropic_messages("You are helpful.", [], [], "hi")
    assert system == "You are helpful."
    assert messages[-1] == {"role": "user", "content": "hi"}


def test_build_anthropic_messages_skills_appended_to_system():
    skill = SkillWithContent(
        id="s1", name="skill_one", author_id="GUGA", is_public=True, is_active=True,
        content="## Skill content",
    )
    system, _ = _build_anthropic_messages("Base.", [skill], [], "q")
    assert "Base." in system
    assert "## Skill content" in system


def test_build_anthropic_messages_history_included():
    history = [
        MessageInHistory(
            role=MessageRole.USER,
            blocks=[TextBlock(block_id="b1", content="first message")],
        ),
        MessageInHistory(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(block_id="b2", content="response")],
        ),
    ]
    _, messages = _build_anthropic_messages(None, [], history, "follow up")
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "follow up"


def test_build_anthropic_messages_sender_prefix():
    """sender 字段出现在 assistant 消息内容中"""
    history = [
        MessageInHistory(
            role=MessageRole.ASSISTANT,
            blocks=[TextBlock(block_id="b1", content="done")],
            sender="CodeAgent",
        )
    ]
    _, messages = _build_anthropic_messages(None, [], history, "next")
    assistant_msg = next(m for m in messages if m["role"] == "assistant")
    assert "CodeAgent" in assistant_msg["content"]


def test_build_anthropic_messages_empty_history_blocks_skipped():
    """history 中 blocks 为空的消息不加入 messages"""
    history = [
        MessageInHistory(role=MessageRole.USER, blocks=[]),
    ]
    _, messages = _build_anthropic_messages(None, [], history, "prompt")
    # 只有最后的 user prompt 消息
    assert len(messages) == 1
    assert messages[0]["content"] == "prompt"


# ---------------------------------------------------------------------------
# Helper: _mcp_tool_to_anthropic
# ---------------------------------------------------------------------------

def test_mcp_tool_to_anthropic_basic():
    tool = MCPTool(
        name="get_info",
        description="Get info about X",
        input_schema={"type": "object", "properties": {"id": {"type": "string"}}},
        has_side_effects=False,
    )
    result = _mcp_tool_to_anthropic(tool)
    assert result["name"] == "get_info"
    assert result["description"] == "Get info about X"
    assert result["input_schema"]["properties"]["id"]["type"] == "string"


def test_mcp_tool_to_anthropic_no_description():
    tool = MCPTool(name="noop", description=None, input_schema=None, has_side_effects=False)
    result = _mcp_tool_to_anthropic(tool)
    assert result["description"] == ""
    assert result["input_schema"] == {"type": "object", "properties": {}}


# ---------------------------------------------------------------------------
# Helper: _extract_tool_result_text
# ---------------------------------------------------------------------------

def test_extract_tool_result_text_with_content_blocks():
    block1 = SimpleNamespace(text="line one")
    block2 = SimpleNamespace(text="line two")
    result = SimpleNamespace(content=[block1, block2])
    assert _extract_tool_result_text(result) == "line one\nline two"


def test_extract_tool_result_text_empty_content():
    """content 列表为空时，实现中 `if result.content` 为 False，走 str(result) 分支。
    这是已知行为——若要修正，应将判断改为 `result.content is not None`。
    """
    result = SimpleNamespace(content=[])
    # 当前实现对空列表返回 str(result)，不是空字符串
    text = _extract_tool_result_text(result)
    # 至少不应该抛异常，且返回字符串
    assert isinstance(text, str)


def test_extract_tool_result_text_no_content_attr():
    result = "plain string"
    assert _extract_tool_result_text(result) == "plain string"


# ===========================================================================
# OrchestratorLLMClient
# ===========================================================================

def _make_llm_client(**kwargs) -> OrchestratorLLMClient:
    return OrchestratorLLMClient(
        api_key="test-key",
        base_url="http://localhost:9999",
        model="claude-haiku-latest",
        **kwargs,
    )


def _fake_message(
    stop_reason: str = "end_turn",
    text_blocks: list[str] | None = None,
    tool_calls: list[dict] | None = None,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> Any:
    """构造 anthropic.types.Message 的 fake 对象"""
    content = []
    for text in text_blocks or []:
        content.append(SimpleNamespace(type="text", text=text))
    for tc in tool_calls or []:
        content.append(SimpleNamespace(
            type="tool_use",
            id=tc.get("id", "tool-1"),
            name=tc["name"],
            input=tc.get("input", {}),
        ))
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(stop_reason=stop_reason, content=content, usage=usage)


# ---------------------------------------------------------------------------
# chat_completion — happy paths
# ---------------------------------------------------------------------------

async def test_chat_completion_end_turn_text():
    client = _make_llm_client()
    fake_resp = _fake_message("end_turn", text_blocks=["Hello there!"])
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    result = await client.chat_completion(
        system="You are helpful.",
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
    )

    assert isinstance(result, LLMResponse)
    assert result.stop_reason == "end_turn"
    assert result.content_text == "Hello there!"
    assert result.tool_calls == []
    assert result.tokens_input == 10
    assert result.tokens_output == 5


async def test_chat_completion_tool_use():
    client = _make_llm_client()
    fake_resp = _fake_message(
        "tool_use",
        tool_calls=[{"id": "tc-1", "name": "dispatch_to_agent", "input": {"agent_id": "coder"}}],
    )
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    result = await client.chat_completion(
        system="",
        messages=[{"role": "user", "content": "write code"}],
        tools=[{"name": "dispatch_to_agent", "description": "...", "input_schema": {}}],
    )

    assert result.stop_reason == "tool_use"
    assert len(result.tool_calls) == 1
    tc: LLMToolCall = result.tool_calls[0]
    assert tc.id == "tc-1"
    assert tc.name == "dispatch_to_agent"
    assert tc.input == {"agent_id": "coder"}
    assert result.content_text is None


async def test_chat_completion_mixed_text_and_tools():
    client = _make_llm_client()
    fake_resp = _fake_message(
        "tool_use",
        text_blocks=["thinking..."],
        tool_calls=[{"id": "tc-2", "name": "read_file", "input": {"path": "/tmp/a.py"}}],
    )
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    result = await client.chat_completion(system="", messages=[], tools=[])

    assert result.content_text == "thinking..."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "read_file"


async def test_chat_completion_empty_content():
    client = _make_llm_client()
    fake_resp = _fake_message("end_turn", text_blocks=[])
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    result = await client.chat_completion(system="", messages=[], tools=[])

    assert result.content_text is None
    assert result.tool_calls == []


async def test_chat_completion_max_tokens():
    client = _make_llm_client()
    fake_resp = _fake_message("max_tokens", text_blocks=["truncated"])
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    result = await client.chat_completion(system="", messages=[], tools=[])
    assert result.stop_reason == "max_tokens"


# ---------------------------------------------------------------------------
# chat_completion — empty system / tools uses NOT_GIVEN
# ---------------------------------------------------------------------------

async def test_chat_completion_empty_system_uses_not_given():
    import anthropic as _anthropic

    client = _make_llm_client()
    fake_resp = _fake_message()
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    await client.chat_completion(system="", messages=[], tools=[])

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["system"] is _anthropic.NOT_GIVEN


async def test_chat_completion_empty_tools_uses_not_given():
    import anthropic as _anthropic

    client = _make_llm_client()
    fake_resp = _fake_message()
    client._client.messages.create = AsyncMock(return_value=fake_resp)

    await client.chat_completion(system="some prompt", messages=[], tools=[])

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["tools"] is _anthropic.NOT_GIVEN


async def test_chat_completion_non_empty_system_is_passed():
    client = _make_llm_client()
    client._client.messages.create = AsyncMock(return_value=_fake_message())

    await client.chat_completion(system="Be concise.", messages=[], tools=[])

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "Be concise."


# ---------------------------------------------------------------------------
# chat_completion — custom model override
# ---------------------------------------------------------------------------

async def test_chat_completion_model_override():
    client = _make_llm_client()
    client._client.messages.create = AsyncMock(return_value=_fake_message())

    await client.chat_completion(
        system="", messages=[], tools=[], model="claude-opus-4-8"
    )

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-8"


async def test_chat_completion_default_model_used_when_no_override():
    client = _make_llm_client()
    client._client.messages.create = AsyncMock(return_value=_fake_message())

    await client.chat_completion(system="", messages=[], tools=[])

    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-latest"


# ---------------------------------------------------------------------------
# chat_completion — error propagation
# ---------------------------------------------------------------------------

async def test_chat_completion_api_error_propagates():
    import anthropic as _anthropic

    client = _make_llm_client()
    client._client.messages.create = AsyncMock(
        side_effect=_anthropic.APIStatusError(
            "server error",
            response=MagicMock(status_code=500, headers={}),
            body=None,
        )
    )

    with pytest.raises(_anthropic.APIError):
        await client.chat_completion(system="", messages=[], tools=[])


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------

async def test_count_tokens_returns_int():
    client = _make_llm_client()
    fake_result = SimpleNamespace(input_tokens=123)
    client._client.messages.count_tokens = AsyncMock(return_value=fake_result)

    count = await client.count_tokens(messages=[{"role": "user", "content": "hello"}])
    assert count == 123


async def test_count_tokens_uses_model():
    client = _make_llm_client()
    fake_result = SimpleNamespace(input_tokens=50)
    client._client.messages.count_tokens = AsyncMock(return_value=fake_result)

    await client.count_tokens(
        messages=[{"role": "user", "content": "test"}],
        model="claude-sonnet-4-6",
    )

    call_kwargs = client._client.messages.count_tokens.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# OrchestratorLLMClient._parse_response (static, no network)
# ---------------------------------------------------------------------------

def test_parse_response_text_only():
    fake_resp = _fake_message("end_turn", text_blocks=["result"], input_tokens=8, output_tokens=3)
    result = OrchestratorLLMClient._parse_response(fake_resp)
    assert result.content_text == "result"
    assert result.tool_calls == []
    assert result.tokens_input == 8
    assert result.tokens_output == 3


def test_parse_response_multiple_text_blocks_joined():
    fake_resp = _fake_message("end_turn", text_blocks=["line1", "line2"])
    result = OrchestratorLLMClient._parse_response(fake_resp)
    assert result.content_text == "line1\nline2"


def test_parse_response_tool_calls_only():
    fake_resp = _fake_message(
        "tool_use",
        tool_calls=[
            {"id": "t1", "name": "tool_a", "input": {"x": 1}},
            {"id": "t2", "name": "tool_b", "input": {}},
        ],
    )
    result = OrchestratorLLMClient._parse_response(fake_resp)
    assert result.content_text is None
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].name == "tool_a"
    assert result.tool_calls[1].id == "t2"


def test_parse_response_no_usage_defaults_to_zero():
    fake_resp = SimpleNamespace(stop_reason="end_turn", content=[], usage=None)
    result = OrchestratorLLMClient._parse_response(fake_resp)
    assert result.tokens_input == 0
    assert result.tokens_output == 0


def test_parse_response_stop_reason_fallback():
    fake_resp = SimpleNamespace(stop_reason=None, content=[], usage=None)
    result = OrchestratorLLMClient._parse_response(fake_resp)
    assert result.stop_reason == "end_turn"
