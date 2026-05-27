"""Integration tests for OpencodeAdapter — requires `opencode` CLI installed and configured.

Run with:
    pytest -m integration tests/integration/test_opencode_stream.py -v

Skip behavior: if `opencode` is not on PATH, all tests in this module are skipped.

队伍：咕嘎一辈子队
修改者：lp
修改日期：2026-05-27
"""
import shutil

import pytest

from backend.adapters.base import StreamInput
from backend.adapters.opencode import OpencodeAdapter
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.domain.message import TextBlock
from tests.test_utils import collect_stream

pytestmark = pytest.mark.integration


@pytest.fixture
def opencode_adapter():
    if not shutil.which("opencode"):
        pytest.skip("opencode CLI not found in PATH")
    return OpencodeAdapter()


def _inp(prompt: str) -> StreamInput:
    return StreamInput(
        agent_id="integration-test",
        thread_id="thread-integ",
        message_id="msg-integ",
        prompt=prompt,
    )


async def test_real_opencode_stream_event_order(opencode_adapter):
    """Real CLI: smoke test that we get start → ... → done in order."""
    events = await collect_stream(opencode_adapter.stream(_inp("Reply with only the word: hello")))
    types = [e.type for e in events]
    assert types[0] == "agent_start"
    # Should contain at least one block_delta from a text block
    assert "block_delta" in types
    # Last event should be either agent_done (success) or agent_error (provider not set up etc.)
    assert types[-1] in ("agent_done", "agent_error")


async def test_real_opencode_stream_text_content_nonempty(opencode_adapter):
    """Real CLI: actual text content reaches the deltas."""
    events = await collect_stream(opencode_adapter.stream(_inp("Reply with only the word: hello")))

    # If the run errored (e.g. no provider configured), surface that — don't pretend to pass
    errors = [e for e in events if isinstance(e, AgentErrorEvent)]
    if errors:
        pytest.skip(f"opencode run failed (likely env not configured): {errors[0].error}")

    text_starts = [e for e in events if isinstance(e, BlockStartEvent) and isinstance(e.block, TextBlock)]
    assert text_starts, "expected at least one TextBlock"

    text_deltas = [
        e for e in events
        if isinstance(e, BlockDeltaEvent) and any(e.block_id == s.block.block_id for s in text_starts)
    ]
    assert text_deltas
    full_text = "".join(d.delta.get("content", "") for d in text_deltas)
    assert full_text.strip(), "text deltas concatenated to empty string"


async def test_real_opencode_stream_id_consistency(opencode_adapter):
    """Real CLI: IDs from StreamInput propagate to every event."""
    inp = _inp("Say hi")
    events = await collect_stream(opencode_adapter.stream(inp))
    for ev in events:
        assert ev.agent_id == inp.agent_id
        assert ev.thread_id == inp.thread_id
        assert ev.message_id == inp.message_id


async def test_real_opencode_block_lifecycle_balanced(opencode_adapter):
    """Real CLI: every block_start has a matching block_stop with the same block_id."""
    events = await collect_stream(opencode_adapter.stream(_inp("Reply with only: ok")))

    errors = [e for e in events if isinstance(e, AgentErrorEvent)]
    if errors:
        pytest.skip(f"opencode run failed (likely env not configured): {errors[0].error}")

    starts = {e.block.block_id for e in events if isinstance(e, BlockStartEvent)}
    stops = {e.block_id for e in events if isinstance(e, BlockStopEvent)}
    # Every started block must be stopped (no dangling blocks)
    assert starts == stops, f"unbalanced blocks: started={starts}, stopped={stops}"
