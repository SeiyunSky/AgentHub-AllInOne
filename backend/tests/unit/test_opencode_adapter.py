"""Unit tests for OpencodeAdapter — subprocess mode is mocked.

队伍：咕嘎一辈子队
修改者：lp
修改日期：2026-05-27
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.adapters.base import StreamInput
from backend.adapters.opencode import OpencodeAdapter, _build_prompt
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.domain.message import TextBlock, ToolUseBlock
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    return OpencodeAdapter(bin_path="opencode")


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="opencode-1", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


def _line(payload: dict) -> bytes:
    """Serialize a payload as a single opencode JSON-stream line."""
    return (json.dumps(payload) + "\n").encode("utf-8")


class _FakeProcess:
    """Mimic asyncio subprocess: async-iterable stdout, awaitable wait/stderr."""

    def __init__(self, lines: list[bytes], returncode: int = 0, stderr: bytes = b""):
        self._lines = lines
        self.returncode = returncode
        self.stdout = self
        self.stderr = AsyncMock()
        self.stderr.read = AsyncMock(return_value=stderr)
        self.terminate = lambda: None  # no-op for cancellation tests

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for line in self._lines:
            yield line

    async def wait(self):
        pass


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities():
    from backend.domain.agent import AgentCapabilities

    caps = _make_adapter().get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_code is True
    assert caps.supports_diff is True
    # AgentHub adapters auto-skip permissions; approval round-trip is not modeled.
    assert caps.supports_approval is False


# ---------------------------------------------------------------------------
# Basic text streaming
# ---------------------------------------------------------------------------

async def test_stream_text_event_order():
    """A single `text` event produces start → block_start → block_delta → block_stop → done."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "hello"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert types[-1] == "agent_done"
    assert "block_start" in types
    assert "block_delta" in types
    assert "block_stop" in types


async def test_stream_text_accumulates_into_one_block():
    """Multiple text events should share one TextBlock (one start, multiple deltas, one stop)."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "hello "}}),
        _line({"type": "text", "part": {"text": "world"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    text_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock)]
    text_deltas = [e for e in events if isinstance(e, BlockDeltaEvent)]
    text_stops = [e for e in events if isinstance(e, BlockStopEvent)]

    assert len(text_starts) == 1
    assert len(text_deltas) == 2
    assert len(text_stops) == 1
    # All deltas share the start's block_id
    assert all(d.block_id == text_starts[0].block.block_id for d in text_deltas)


async def test_stream_text_delta_content_preserved():
    """The `content` field in each delta must equal the original text fragment."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "alpha"}}),
        _line({"type": "text", "part": {"text": "beta"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    deltas = [e for e in events if isinstance(e, BlockDeltaEvent)]
    contents = [d.delta.get("content") for d in deltas]
    assert contents == ["alpha", "beta"]


async def test_stream_skips_step_events():
    """`step_start` / `step_finish` are internal — must produce no output blocks."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "step_start", "part": {}}),
        _line({"type": "step_finish", "part": {"reason": "stop"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    types = [e.type for e in events]
    # Only agent_start + agent_done — no block events, no errors
    assert types == ["agent_start", "agent_done"]


async def test_stream_ignores_non_json_lines():
    """Banner/log lines that fail JSON-parse must be silently skipped."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        b"opencode v1.2.3 banner line\n",
        _line({"type": "text", "part": {"text": "hi"}}),
        b"\n",  # blank
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    deltas = [e for e in events if isinstance(e, BlockDeltaEvent)]
    assert len(deltas) == 1
    assert deltas[0].delta["content"] == "hi"


# ---------------------------------------------------------------------------
# Tool use translation
# ---------------------------------------------------------------------------

async def test_stream_tool_use_emits_block():
    """A completed tool_use event yields a ToolUseBlock with input/output."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({
            "type": "tool_use",
            "part": {
                "tool": "read_file",
                "callID": "tool_abc",
                "state": {
                    "status": "completed",
                    "input": {"path": "/tmp/x.txt"},
                    "output": "file contents",
                },
            },
        }),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    tool_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, ToolUseBlock)]
    assert len(tool_starts) == 1
    block = tool_starts[0].block
    assert block.tool_name == "read_file"
    assert block.input == {"path": "/tmp/x.txt"}
    # status is initialized to "running" at start; the delta updates it to "completed"
    assert block.status == "running"

    tool_deltas = [
        e for e in events
        if isinstance(e, BlockDeltaEvent) and e.block_id == block.block_id
    ]
    assert tool_deltas
    assert tool_deltas[-1].delta["status"] == "completed"
    assert tool_deltas[-1].delta["output"] == "file contents"


async def test_stream_tool_use_closes_text_block_first():
    """When a tool_use arrives mid-text, the in-flight text block must close before the tool block opens."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "before"}}),
        _line({
            "type": "tool_use",
            "part": {
                "tool": "list_files",
                "callID": "tool_xyz",
                "state": {"status": "completed", "output": "[]"},
            },
        }),
        _line({"type": "text", "part": {"text": "after"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    # Order should be:
    # agent_start, text-start, text-delta, text-stop, tool-start, tool-delta, tool-stop,
    # text-start (new block!), text-delta, text-stop, agent_done
    types_with_blocks = [
        (e.type, type(e.block).__name__ if isinstance(e, BlockStartEvent) else None)
        for e in events
    ]

    # Two distinct text blocks, one tool block
    text_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock)]
    tool_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, ToolUseBlock)]
    assert len(text_starts) == 2
    assert len(tool_starts) == 1

    # The first text block must have a stop before the tool block starts
    indexed = list(enumerate(events))
    first_text_start = next(i for i, e in indexed if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock))
    first_tool_start = next(i for i, e in indexed if isinstance(e, BlockStartEvent) and isinstance(e.block, ToolUseBlock))
    text_stops_before_tool = [
        i for i, e in indexed
        if isinstance(e, BlockStopEvent) and i < first_tool_start and i > first_text_start
    ]
    assert text_stops_before_tool, "text block must be closed before tool block opens"


async def test_stream_tool_use_with_dict_output_serialized():
    """If `state.output` is a dict, it must be JSON-serialized before assignment."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({
            "type": "tool_use",
            "part": {
                "tool": "search",
                "callID": "tool_1",
                "state": {
                    "status": "completed",
                    "output": {"hits": 3, "items": ["a", "b", "c"]},
                },
            },
        }),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    deltas = [e for e in events if isinstance(e, BlockDeltaEvent)]
    output = deltas[-1].delta["output"]
    assert isinstance(output, str)
    parsed = json.loads(output)
    assert parsed == {"hits": 3, "items": ["a", "b", "c"]}


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

async def test_stream_cancel_event_aborts_mid_stream():
    """Setting cancel_event must terminate the loop and emit AgentErrorEvent('cancelled')."""
    adapter = _make_adapter()
    cancel_event = asyncio.Event()
    cancel_event.set()  # already cancelled before first line

    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "hello"}}),
        _line({"type": "text", "part": {"text": "world"}}),
    ])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp(cancel_event=cancel_event)))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].error == "cancelled"
    # Must NOT have produced an AgentDoneEvent
    assert not any(isinstance(e, AgentDoneEvent) for e in events)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

async def test_stream_nonzero_exit_emits_error():
    adapter = _make_adapter()
    proc = _FakeProcess([], returncode=1, stderr=b"opencode: provider not configured")

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "provider not configured" in error_events[0].error


async def test_stream_binary_not_found():
    adapter = _make_adapter()

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", side_effect=FileNotFoundError), \
         patch("backend.adapters.opencode.shutil.which", return_value=None):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "not found" in error_events[0].error.lower()
    # AgentStart must still have fired before the error
    assert isinstance(events[0], AgentStartEvent)


async def test_stream_empty_output_still_completes():
    """No JSON lines at all — adapter must still close cleanly with AgentDone."""
    adapter = _make_adapter()
    proc = _FakeProcess([])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(_make_inp()))

    types = [e.type for e in events]
    assert types == ["agent_start", "agent_done"]


# ---------------------------------------------------------------------------
# ID propagation invariants
# ---------------------------------------------------------------------------

async def test_stream_ids_propagated_to_all_events():
    """agent_id / thread_id / message_id from StreamInput must appear on every event."""
    adapter = _make_adapter()
    proc = _FakeProcess([
        _line({"type": "text", "part": {"text": "x"}}),
        _line({
            "type": "tool_use",
            "part": {
                "tool": "t",
                "callID": "c1",
                "state": {"status": "completed", "output": "ok"},
            },
        }),
    ])

    inp = _make_inp(agent_id="A", thread_id="T", message_id="M")
    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        events = await collect_stream(adapter.stream(inp))

    for ev in events:
        assert ev.agent_id == "A"
        assert ev.thread_id == "T"
        assert ev.message_id == "M"


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

def test_build_prompt_no_history():
    inp = _make_inp(prompt="just this")
    assert _build_prompt(inp) == "User: just this"


def test_build_prompt_with_history(make_message):
    inp = _make_inp(
        prompt="follow up",
        history=[
            make_message(role="user", content="first"),
            make_message(role="assistant", content="reply"),
        ],
    )
    out = _build_prompt(inp)
    assert "User: first" in out
    assert "Assistant: reply" in out
    assert out.endswith("User: follow up")


def test_build_prompt_with_system_prompt():
    inp = _make_inp(prompt="hi", system_prompt="be terse")
    out = _build_prompt(inp)
    assert out.startswith("System: be terse")
    assert "User: hi" in out


def test_build_prompt_with_skills(make_skill):
    inp = _make_inp(prompt="hi", skills=[make_skill(name="s1", content="skill body")])
    out = _build_prompt(inp)
    assert "Skill (s1):" in out
    assert "skill body" in out
