"""Unit tests for CodexAdapter — subprocess and MCP modes are mocked."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.adapters.base import StreamInput
from backend.adapters.codex import (
    CodexAdapter,
    _looks_like_diff,
)
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.domain.message import ApprovalBlock, CodeBlock, TextBlock
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter(mcp_client=None):
    return CodexAdapter(bin_path="codex", mcp_client=mcp_client)


def _make_inp(**kwargs) -> StreamInput:
    defaults = dict(agent_id="codex-1", thread_id="thread-1", message_id="msg-1", prompt="hello")
    defaults.update(kwargs)
    return StreamInput(**defaults)


class _FakeProcess:
    def __init__(self, lines: list[bytes], returncode: int = 0, stderr: bytes = b""):
        self._lines = lines
        self.returncode = returncode
        self.stdin = AsyncMock()
        self.stdin.drain = AsyncMock()
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


# ---------------------------------------------------------------------------
# get_capabilities
# ---------------------------------------------------------------------------

def test_get_capabilities():
    from backend.domain.agent import AgentCapabilities
    adapter = _make_adapter()
    caps = adapter.get_capabilities()
    assert isinstance(caps, AgentCapabilities)
    assert caps.supports_diff is True
    assert caps.supports_approval is True


# ---------------------------------------------------------------------------
# Subprocess mode: basic text streaming
# ---------------------------------------------------------------------------

async def test_stream_subprocess_tokens():
    adapter = _make_adapter()
    proc = _FakeProcess([b"hello world\n", b"second line\n"])

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[0], AgentStartEvent)
    text_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock)]
    assert len(text_starts) == 1
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_subprocess_empty_output():
    adapter = _make_adapter()
    proc = _FakeProcess([])

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[0], AgentStartEvent)
    assert isinstance(events[-1], AgentDoneEvent)


# ---------------------------------------------------------------------------
# Subprocess mode: diff detection
# ---------------------------------------------------------------------------

SAMPLE_DIFF = (
    "--- a/src/app.py\n"
    "+++ b/src/app.py\n"
    "@@ -1,3 +1,4 @@\n"
    " import os\n"
    "+import sys\n"
    " \n"
    " def main():\n"
)


async def test_stream_subprocess_diff():
    adapter = _make_adapter()
    lines = [line.encode() for line in SAMPLE_DIFF.splitlines(keepends=True)] + [b"\n"]
    proc = _FakeProcess(lines)

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream(_make_inp()))

    code_starts = [
        e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, CodeBlock)
    ]
    assert len(code_starts) == 1
    assert code_starts[0].block.filename == "src/app.py"


# ---------------------------------------------------------------------------
# Subprocess mode: approval detection
# ---------------------------------------------------------------------------

async def test_stream_subprocess_approval():
    adapter = _make_adapter()
    lines = [b"? running: npm test\n", b"Tests passed\n"]
    proc = _FakeProcess(lines)

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream(_make_inp()))

    approval_starts = [
        e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, ApprovalBlock)
    ]
    assert len(approval_starts) == 1
    assert approval_starts[0].block.action == "run_command"
    assert approval_starts[0].block.detail == "npm test"


# ---------------------------------------------------------------------------
# Subprocess mode: non-zero exit code
# ---------------------------------------------------------------------------

async def test_stream_subprocess_error_exit():
    adapter = _make_adapter()
    proc = _FakeProcess([], returncode=1, stderr=b"error: command failed")

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "command failed" in error_events[0].error


async def test_stream_subprocess_binary_not_found():
    adapter = _make_adapter()

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", side_effect=FileNotFoundError), \
         patch("backend.adapters.codex.shutil.which", return_value=None):
        events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "not found" in error_events[0].error.lower()


# ---------------------------------------------------------------------------
# MCP mode
# ---------------------------------------------------------------------------

async def test_stream_via_mcp_text():
    mock_mcp = AsyncMock()
    mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="output line\n")]
    )
    adapter = _make_adapter(mcp_client=mock_mcp)

    events = await collect_stream(adapter.stream(_make_inp()))

    assert isinstance(events[0], AgentStartEvent)
    text_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock)]
    assert len(text_starts) >= 1
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_via_mcp_diff():
    mock_mcp = AsyncMock()
    mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=SAMPLE_DIFF)]
    )
    adapter = _make_adapter(mcp_client=mock_mcp)

    events = await collect_stream(adapter.stream(_make_inp()))

    code_starts = [
        e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, CodeBlock)
    ]
    assert len(code_starts) == 1


async def test_stream_via_mcp_error():
    mock_mcp = AsyncMock()
    mock_mcp.call_tool.side_effect = RuntimeError("mcp timeout")
    adapter = _make_adapter(mcp_client=mock_mcp)

    events = await collect_stream(adapter.stream(_make_inp()))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "mcp timeout" in error_events[0].error


# ---------------------------------------------------------------------------
# Helper: _looks_like_diff
# ---------------------------------------------------------------------------

def test_looks_like_diff_true():
    assert _looks_like_diff("--- a/foo.py\n+++ b/foo.py\n") is True


def test_looks_like_diff_false():
    assert _looks_like_diff("just a normal line\n") is False
