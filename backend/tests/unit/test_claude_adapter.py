"""Unit tests for ClaudeAdapter (CLI subprocess mode) — subprocess is mocked.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-26
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.adapters.base import StreamInput
from backend.adapters.claude import (
    ClaudeAdapter,
    _blocks_to_text,
    _build_prompt,
    _build_system_prompt,
)
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.domain.agent import AgentCapabilities
from backend.domain.message import TextBlock, ThinkingBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory, MessageRole
from backend.schemas.skill import SkillWithContent
from tests.test_utils import collect_stream

import json


# ---------------------------------------------------------------------------
# Fake subprocess helpers
# ---------------------------------------------------------------------------

class _FakeProcess:
    def __init__(self, lines: list[bytes], returncode: int = 0, stderr: bytes = b""):
        self._lines = lines
        self.returncode = returncode
        self.stdout = self
        self.stderr = AsyncMock()
        self.stderr.read = AsyncMock(return_value=stderr)

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for line in self._lines:
            yield line

    async def wait(self):
        pass


def _assistant_line(text: str) -> bytes:
    payload = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }
    return (json.dumps(payload) + "\n").encode()


def _result_line(result: str = "done", success: bool = True) -> bytes:
    payload = {
        "type": "result",
        "subtype": "success" if success else "error_during_execution",
        "is_error": not success,
        "result": result,
    }
    return (json.dumps(payload) + "\n").encode()


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="agent-1", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities():
    adapter = ClaudeAdapter()
    caps = adapter.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_diff is True
    assert caps.supports_approval is False


# ---------------------------------------------------------------------------
# Basic stream lifecycle
# ---------------------------------------------------------------------------

async def test_stream_yields_start_and_done():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([_assistant_line("hello"), _result_line()])

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[0], AgentStartEvent)
    assert events[0].agent_id == "agent-1"
    assert events[0].thread_id == "thread-1"
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_text_block_lifecycle():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([_assistant_line("foo"), _assistant_line("bar"), _result_line()])

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    block_starts = [e for e in events if isinstance(e, BlockStartEvent)]
    block_stops = [e for e in events if isinstance(e, BlockStopEvent)]
    assert len(block_starts) == 1
    assert isinstance(block_starts[0].block, TextBlock)
    assert len(block_stops) == 1


async def test_stream_empty_output():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([_result_line()])

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[0], AgentStartEvent)
    assert isinstance(events[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

async def test_stream_binary_not_found():
    adapter = ClaudeAdapter()

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", side_effect=FileNotFoundError), \
         patch("backend.adapters.claude.shutil.which", return_value=None):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "not found" in error_events[0].error.lower()


async def test_stream_nonzero_exit():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([], returncode=1, stderr=b"login required")

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "login required" in error_events[0].error


async def test_stream_result_error_subtype():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([_result_line("something went wrong", success=False)])

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "something went wrong" in error_events[0].error


async def test_stream_ignores_non_json_lines():
    adapter = ClaudeAdapter()
    proc = _FakeProcess([
        b"not json at all\n",
        _assistant_line("hello"),
        _result_line(),
    ])

    with patch("backend.adapters.claude.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.claude.shutil.which", return_value="claude"):
        events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Helper: _blocks_to_text
# ---------------------------------------------------------------------------

def test_blocks_to_text_text_block():
    assert _blocks_to_text([TextBlock(block_id="b1", content="hello")]) == "hello"


def test_blocks_to_text_tool_use_block():
    text = _blocks_to_text([ToolUseBlock(block_id="b2", tool_name="read_file", output="content", status="completed")])
    assert "[Tool: read_file -> content]" in text


def test_blocks_to_text_thinking_block_skipped():
    assert _blocks_to_text([ThinkingBlock(block_id="b3", content="internal thought")]) == ""


# ---------------------------------------------------------------------------
# Helper: _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_no_history():
    inp = _make_inp(prompt="what is 2+2?")
    assert _build_prompt(inp) == "what is 2+2?"


def test_build_prompt_with_history():
    inp = _make_inp(
        prompt="how are you?",
        history=[
            MessageInHistory(role=MessageRole.USER, blocks=[TextBlock(block_id="b1", content="hi")]),
            MessageInHistory(role=MessageRole.ASSISTANT, blocks=[TextBlock(block_id="b2", content="hello")]),
        ],
    )
    result = _build_prompt(inp)
    assert "User: hi" in result
    assert "Assistant: hello" in result
    assert result.endswith("User: how are you?")


def test_build_prompt_with_sender():
    inp = _make_inp(
        prompt="ok",
        history=[
            MessageInHistory(
                role=MessageRole.ASSISTANT,
                blocks=[TextBlock(block_id="b1", content="done")],
                sender="CodeReviewer",
            )
        ],
    )
    result = _build_prompt(inp)
    assert "CodeReviewer: done" in result


# ---------------------------------------------------------------------------
# Helper: _build_system_prompt
# ---------------------------------------------------------------------------

def test_build_system_prompt_base_only():
    assert _build_system_prompt("You are helpful.", []) == "You are helpful."


def test_build_system_prompt_with_skills():
    skill = SkillWithContent(
        id="s1", name="code_review", author_id="GUGA", is_public=True, is_active=True,
        content="## Review steps\n1. check types",
    )
    prompt = _build_system_prompt("Base prompt.", [skill])
    assert "Base prompt." in prompt
    assert "## Review steps" in prompt


def test_build_system_prompt_no_base_no_skills():
    assert _build_system_prompt(None, []) == ""
