"""Integration tests for CustomAdapter — requires OPENAI_API_KEY or compatible endpoint.

Run with:
    OPENAI_API_KEY=sk-... pytest -m integration tests/integration/test_custom_stream.py -v

For local Ollama:
    OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama \
    OPENAI_MODEL_ID=llama3 pytest -m integration tests/integration/test_custom_stream.py -v
"""
import os

import pytest

from backend.adapters.custom import CustomAdapter
from backend.adapters.events import AgentDoneEvent, AgentStartEvent, TokenEvent
from tests.test_utils import collect_stream

pytestmark = pytest.mark.integration


@pytest.fixture
def custom_adapter():
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    model = os.environ.get("OPENAI_MODEL_ID")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set")
    return CustomAdapter(
        agent_id="integration-test",
        agent_name="Custom",
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


async def test_real_custom_stream_event_order(custom_adapter):
    events = await collect_stream(custom_adapter.stream("Reply with only: hello", [], []))
    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert "token" in types
    assert types[-1] == "agent_done"


async def test_real_custom_stream_agent_id_consistent(custom_adapter):
    events = await collect_stream(custom_adapter.stream("Say hi", [], []))
    for event in events:
        if hasattr(event, "agent_id"):
            assert event.agent_id == "integration-test"


async def test_real_custom_stream_token_content_nonempty(custom_adapter):
    events = await collect_stream(custom_adapter.stream("Reply with only: hello", [], []))
    token_events = [e for e in events if isinstance(e, TokenEvent)]
    assert len(token_events) > 0
    full_text = "".join(e.content for e in token_events)
    assert len(full_text.strip()) > 0
