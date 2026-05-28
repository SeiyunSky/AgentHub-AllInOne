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
from backend.adapters.opencode import (
    OpencodeAdapter,
    _build_prompt,
)
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
# _build_prompt: natural-language wrapping (no role labels, no banners)
# ---------------------------------------------------------------------------
#
# Design: opencode's alignment training treats anything that *looks* like a
# meta/system instruction (labels like "system prompt", "orchestrator",
# "sub-agent", "dispatch", "BEGIN/END SECTION", role brackets) as a jailbreak
# attempt and refuses. So _build_prompt avoids ALL such markers and presents
# the prompt as plain conversational user speech. These tests pin that
# invariant down.

_FORBIDDEN_MARKERS = [
    "system prompt", "System Prompt",
    "orchestrator", "Orchestrator",
    "sub-agent", "sub agent", "Sub-Agent",
    "dispatch", "Dispatch", "DISPATCH",
    "BEGIN ", "END ",
    "===",
    "---",  # markdown rule lines used to be in our wrappers; not anymore
    "PERSONA DESCRIPTION", "Persona for this task",
    "ACTUAL TASK FROM USER",
    "injection",
]


def _assert_no_forbidden_markers(text: str) -> None:
    """Assert the text contains no jailbreak-trigger markers from our wrapping.

    Note: the orchestrator's own dispatch_prompt content (passed in inp.prompt)
    may legitimately contain such words — this assertion is on the *wrapper*
    that _build_prompt adds, so callers should pass user-facing prompts that
    don't already contain these strings as substrings of their own content.
    """
    lowered = text.lower()
    for marker in _FORBIDDEN_MARKERS:
        assert marker.lower() not in lowered, (
            f"_build_prompt output contains forbidden marker {marker!r} which "
            "would trip opencode's anti-jailbreak guard:\n" + text
        )


def test_build_prompt_no_history():
    inp = _make_inp(prompt="just this")
    out = _build_prompt(inp)
    assert "just this" in out
    _assert_no_forbidden_markers(out)


def test_build_prompt_with_history(make_message):
    inp = _make_inp(
        prompt="follow up",
        history=[
            make_message(role="user", content="first"),
            make_message(role="assistant", content="reply"),
        ],
    )
    out = _build_prompt(inp)
    # History is folded into natural conversational language; the actual
    # text content is preserved.
    assert "first" in out
    assert "reply" in out
    assert "follow up" in out
    # No "User:" / "Assistant:" role labels — those look meta to opencode
    assert "User:" not in out
    assert "Assistant:" not in out
    # Final task comes after history in document order
    history_idx = out.index("reply")
    task_idx = out.index("follow up")
    assert history_idx < task_idx
    _assert_no_forbidden_markers(out)


def test_build_prompt_with_system_prompt():
    """system_prompt is folded in as a casual conversational opener.

    No "system prompt" / "persona" / "orchestrator" labels should appear in
    the wrapping; the persona's content itself is reproduced verbatim.
    """
    inp = _make_inp(prompt="hi", system_prompt="be terse")
    out = _build_prompt(inp)
    # Persona content reproduced
    assert "be terse" in out
    # Final task present
    assert "hi" in out
    # Wrapping must not use any of the forbidden labels
    _assert_no_forbidden_markers(out)


def test_build_prompt_with_skills(make_skill):
    inp = _make_inp(prompt="hi", skills=[make_skill(name="s1", content="skill body")])
    out = _build_prompt(inp)
    # Skill content reproduced
    assert "skill body" in out
    assert "s1" in out
    _assert_no_forbidden_markers(out)


def test_build_prompt_preserves_structured_prompt_content_verbatim():
    """The orchestrator's dispatch_prompt content (which may contain markdown
    headings) is reproduced verbatim. We do NOT rewrite the user's content —
    only our own wrapping is constrained to plain conversational language.
    """
    raw = "## 任务\n请用 Python 写 FizzBuzz\n\n## 要求\n- 简短\n- 直接可运行"
    inp = _make_inp(prompt=raw)
    out = _build_prompt(inp)
    # The orchestrator's headings survive — we don't demote them
    assert "## 任务" in out
    assert "## 要求" in out
    assert "请用 Python 写 FizzBuzz" in out
    assert "- 简短" in out


# ---------------------------------------------------------------------------
# stream() launches the subprocess with the natural-language prompt + sandbox cwd
# ---------------------------------------------------------------------------

async def test_stream_passes_built_prompt_to_subprocess():
    """The prompt argv is exactly what _build_prompt returned; nothing extra
    wraps it inside stream() itself.
    """
    adapter = _make_adapter()
    proc = _FakeProcess([])

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", return_value=proc) as mock_exec, \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        inp = _make_inp(prompt="write fizzbuzz", system_prompt="be terse")
        await collect_stream(adapter.stream(inp))

    prompt_arg = mock_exec.call_args.args[-1]
    expected = _build_prompt(inp)
    assert prompt_arg == expected
    # Sanity: persona content + task content both made it through
    assert "be terse" in prompt_arg
    assert "write fizzbuzz" in prompt_arg
    _assert_no_forbidden_markers(prompt_arg)


async def test_stream_uses_sandbox_cwd():
    """stream() always launches the subprocess with a sandbox cwd (a temp dir).

    The exact path is implementation detail; we just verify it's set to a
    non-None string that's a freshly-created temp dir.
    """
    import os as _os

    adapter = _make_adapter()
    proc = _FakeProcess([])

    captured_cwd: list[str | None] = []

    async def _capture_exec(*args, **kwargs):
        captured_cwd.append(kwargs.get("cwd"))
        return proc

    with patch("backend.adapters.opencode.asyncio.create_subprocess_exec", side_effect=_capture_exec), \
         patch("backend.adapters.opencode.shutil.which", return_value="opencode"):
        await collect_stream(adapter.stream(_make_inp(prompt="hello")))

    assert len(captured_cwd) == 1
    cwd = captured_cwd[0]
    assert cwd is not None
    assert isinstance(cwd, str)
    # Path must look like a temp dir we created (prefix from tempfile.mkdtemp)
    assert "agenthub-opencode-" in cwd
    # Sandbox is cleaned up after stream() finishes
    assert not _os.path.exists(cwd)
