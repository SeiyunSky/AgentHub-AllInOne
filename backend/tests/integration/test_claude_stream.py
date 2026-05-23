"""Integration tests for ClaudeAdapter — requires ANTHROPIC_API_KEY env var.

Run with:
    ANTHROPIC_API_KEY=sk-... pytest -m integration tests/integration/test_claude_stream.py -v
"""
import os

import pytest

from backend.adapters.claude import ClaudeAdapter
from backend.adapters.events import AgentDoneEvent, AgentStartEvent, TokenEvent
from tests.test_utils import collect_stream

pytestmark = pytest.mark.integration


@pytest.fixture
def claude_adapter():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return ClaudeAdapter(
        agent_id="integration-test",
        agent_name="Claude",
        api_key=api_key,
    )


async def test_real_claude_stream_event_order(claude_adapter):
    events = await collect_stream(claude_adapter.stream("Reply with only: hello", [], []))
    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert "token" in types
    assert types[-1] == "agent_done"


async def test_real_claude_stream_agent_id_consistent(claude_adapter):
    events = await collect_stream(claude_adapter.stream("Say hi", [], []))
    for event in events:
        if hasattr(event, "agent_id"):
            assert event.agent_id == "integration-test"


async def test_real_claude_stream_message_id_consistent(claude_adapter):
    events = await collect_stream(claude_adapter.stream("Say hi", [], []))
    start = events[0]
    assert isinstance(start, AgentStartEvent)
    message_id = start.message_id
    for event in events:
        if hasattr(event, "message_id"):
            assert event.message_id == message_id


async def test_real_claude_stream_token_content_nonempty(claude_adapter):
    events = await collect_stream(claude_adapter.stream("Reply with only: hello", [], []))
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    full_text = "".join(e.content for e in token_events)
    assert len(full_text.strip()) > 0
