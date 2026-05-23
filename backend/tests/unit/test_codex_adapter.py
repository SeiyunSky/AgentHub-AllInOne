"""Unit tests for CodexAdapter — subprocess and MCP modes are mocked."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.adapters.codex import (
    CodexAdapter,
    _looks_like_diff,
    _parse_diff_to_events,
)
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    ApprovalRequestEvent,
    ArtifactDiffEvent,
    TokenEvent,
)
from tests.test_utils import collect_stream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter(mcp_client=None):
    return CodexAdapter(
        agent_id="codex-1",
        agent_name="Codex",
        bin_path="codex",
        mcp_client=mcp_client,
    )


class _FakeProcess:
    """Fake asyncio subprocess."""

    def __init__(self, lines: list[bytes], returncode: int = 0, stderr: bytes = b""):
        self._lines = lines
        self.returncode = returncode
        self._stderr = stderr
        self.stdin = AsyncMock()
        self.stdin.drain = AsyncMock()
        self.stdout = self  # async-iterable
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
    adapter = _make_adapter()
    assert adapter.get_capabilities() == {"supports_diff": True, "supports_approval": True}


# ---------------------------------------------------------------------------
# Subprocess mode: basic token streaming
# ---------------------------------------------------------------------------

async def test_stream_subprocess_tokens():
    adapter = _make_adapter()
    proc = _FakeProcess([b"hello world\n", b"second line\n"])

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream("write hello", [], []))

    assert isinstance(events[0], AgentStartEvent)
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert any("hello world" in e.content for e in token_events)
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_subprocess_empty_output():
    adapter = _make_adapter()
    proc = _FakeProcess([])

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream("do nothing", [], []))

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
    lines = [line.encode() for line in SAMPLE_DIFF.splitlines(keepends=True)]
    proc = _FakeProcess(lines)

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream("add sys import", [], []))

    diff_events = [e for e in events if isinstance(e, ArtifactDiffEvent)]
    assert len(diff_events) == 1
    assert diff_events[0].file == "src/app.py"
    assert diff_events[0].additions == 1
    assert diff_events[0].deletions == 0


# ---------------------------------------------------------------------------
# Subprocess mode: approval detection
# ---------------------------------------------------------------------------

async def test_stream_subprocess_approval():
    adapter = _make_adapter()
    lines = [b"? running: npm test\n", b"Tests passed\n"]
    proc = _FakeProcess(lines)

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream("run tests", [], []))

    approval_events = [e for e in events if isinstance(e, ApprovalRequestEvent)]
    assert len(approval_events) == 1
    assert approval_events[0].action == "run_command"
    assert approval_events[0].detail == "npm test"


# ---------------------------------------------------------------------------
# Subprocess mode: non-zero exit code
# ---------------------------------------------------------------------------

async def test_stream_subprocess_error_exit():
    adapter = _make_adapter()
    proc = _FakeProcess([], returncode=1, stderr=b"error: command failed")

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", return_value=proc), \
         patch("backend.adapters.codex.shutil.which", return_value="codex"):
        events = await collect_stream(adapter.stream("broken", [], []))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "command failed" in error_events[0].error


async def test_stream_subprocess_binary_not_found():
    adapter = _make_adapter()

    with patch("backend.adapters.codex.asyncio.create_subprocess_exec", side_effect=FileNotFoundError), \
         patch("backend.adapters.codex.shutil.which", return_value=None):
        events = await collect_stream(adapter.stream("hello", [], []))

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

    events = await collect_stream(adapter.stream("do something", [], []))

    assert isinstance(events[0], AgentStartEvent)
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert any("output line" in e.content for e in token_events)
    assert isinstance(events[-1], AgentDoneEvent)


async def test_stream_via_mcp_diff():
    mock_mcp = AsyncMock()
    mock_mcp.call_tool.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=SAMPLE_DIFF)]
    )
    adapter = _make_adapter(mcp_client=mock_mcp)

    events = await collect_stream(adapter.stream("add import", [], []))

    diff_events = [e for e in events if isinstance(e, ArtifactDiffEvent)]
    assert len(diff_events) == 1


async def test_stream_via_mcp_error():
    mock_mcp = AsyncMock()
    mock_mcp.call_tool.side_effect = RuntimeError("mcp timeout")
    adapter = _make_adapter(mcp_client=mock_mcp)

    events = await collect_stream(adapter.stream("do something", [], []))

    error_events = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(error_events) == 1
    assert "mcp timeout" in error_events[0].error


# ---------------------------------------------------------------------------
# Helpers: _looks_like_diff
# ---------------------------------------------------------------------------

def test_looks_like_diff_true():
    assert _looks_like_diff("--- a/foo.py\n+++ b/foo.py\n") is True


def test_looks_like_diff_false():
    assert _looks_like_diff("just a normal line\n") is False


# ---------------------------------------------------------------------------
# Helpers: _parse_diff_to_events
# ---------------------------------------------------------------------------

def test_parse_diff_single_file():
    events = _parse_diff_to_events("a1", "m1", SAMPLE_DIFF)
    assert len(events) == 1
    assert events[0].file == "src/app.py"
    assert events[0].additions == 1


def test_parse_diff_multi_file():
    two_file_diff = (
        "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1,2 @@\n x\n+y\n"
        "--- a/bar.py\n+++ b/bar.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    events = _parse_diff_to_events("a1", "m1", two_file_diff)
    assert len(events) == 2
    files = {e.file for e in events}
    assert files == {"foo.py", "bar.py"}


def test_parse_diff_counts_additions_and_deletions():
    diff = (
        "--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,4 @@\n"
        " unchanged\n"
        "+added line\n"
        "+another added\n"
        "-removed line\n"
    )
    events = _parse_diff_to_events("a1", "m1", diff)
    assert events[0].additions == 2
    assert events[0].deletions == 1


def test_parse_diff_empty_returns_no_events():
    events = _parse_diff_to_events("a1", "m1", "")
    assert events == []
