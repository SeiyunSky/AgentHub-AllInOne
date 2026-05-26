"""Integration tests for ClaudeAdapter — requires `claude` CLI installed and logged in.

Run with:
    pytest -m integration tests/integration/test_claude_stream.py -v

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-26
"""
import shutil

import pytest

from backend.adapters.base import StreamInput
from backend.adapters.claude import ClaudeAdapter
from backend.adapters.events import AgentDoneEvent, AgentStartEvent, BlockDeltaEvent
from tests.test_utils import collect_stream

pytestmark = pytest.mark.integration


@pytest.fixture
def claude_adapter():
    if not shutil.which("claude"):
        pytest.skip("claude CLI not found in PATH")
    return ClaudeAdapter()


def _inp(prompt: str) -> StreamInput:
    return StreamInput(
        agent_id="integration-test",
        thread_id="thread-integ",
        message_id="msg-integ",
        prompt=prompt,
    )


async def test_real_claude_stream_event_order(claude_adapter):
    events = await collect_stream(claude_adapter.stream(_inp("Reply with only: hello")))
    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert "block_delta" in types
    assert types[-1] == "agent_done"


async def test_real_claude_stream_agent_id_consistent(claude_adapter):
    events = await collect_stream(claude_adapter.stream(_inp("Say hi")))
    for event in events:
        if hasattr(event, "agent_id"):
            assert event.agent_id == "integration-test"


async def test_real_claude_stream_message_id_consistent(claude_adapter):
    events = await collect_stream(claude_adapter.stream(_inp("Say hi")))
    start = events[0]
    assert isinstance(start, AgentStartEvent)
    message_id = start.message_id
    for event in events:
        if hasattr(event, "message_id"):
            assert event.message_id == message_id


async def test_real_claude_stream_token_content_nonempty(claude_adapter):
    events = await collect_stream(claude_adapter.stream(_inp("Reply with only: hello")))
    delta_events = [e for e in events if isinstance(e, BlockDeltaEvent)]
    assert len(delta_events) > 0
    full_text = "".join(
        e.delta.get("content", "") if isinstance(e.delta, dict) else ""
        for e in delta_events
    )
    assert len(full_text.strip()) > 0
