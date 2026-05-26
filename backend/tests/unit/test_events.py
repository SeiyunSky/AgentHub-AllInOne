"""Tests for adapters/events.py — Pydantic models, block-level protocol.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-23
"""
import pytest
from pydantic import TypeAdapter

from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
    RoundDoneEvent,
    QueueDrainedEvent,
)
from backend.domain.message import TextBlock, ToolUseBlock
from backend.core.utils import gen_uuid

_event_adapter = TypeAdapter(AgentEvent)


# ---------------------------------------------------------------------------
# Type defaults
# ---------------------------------------------------------------------------

def test_agent_start_event_type():
    e = AgentStartEvent(agent_id="a1", thread_id="t1", message_id="m1", agent_name="Claude")
    assert e.type == "agent_start"


def test_block_start_event_type():
    bid = gen_uuid()
    e = BlockStartEvent(agent_id="a1", thread_id="t1", message_id="m1",
                        block=TextBlock(block_id=bid, content=""))
    assert e.type == "block_start"


def test_block_delta_event_type():
    e = BlockDeltaEvent(agent_id="a1", thread_id="t1", message_id="m1",
                        block_id="bid", delta={"content": "hi"})
    assert e.type == "block_delta"


def test_block_stop_event_type():
    e = BlockStopEvent(agent_id="a1", thread_id="t1", message_id="m1", block_id="bid")
    assert e.type == "block_stop"


def test_agent_done_event_type():
    e = AgentDoneEvent(agent_id="a1", thread_id="t1", message_id="m1")
    assert e.type == "agent_done"


def test_agent_error_event_type():
    e = AgentErrorEvent(agent_id="a1", thread_id="t1", message_id="m1", error="timeout")
    assert e.type == "agent_error"


def test_round_done_event_type():
    e = RoundDoneEvent()
    assert e.type == "round_done"


def test_queue_drained_event_type():
    e = QueueDrainedEvent()
    assert e.type == "queue_drained"


# ---------------------------------------------------------------------------
# Block serialization
# ---------------------------------------------------------------------------

def test_block_start_with_text_block_serializes():
    bid = gen_uuid()
    e = BlockStartEvent(agent_id="a1", thread_id="t1", message_id="m1",
                        block=TextBlock(block_id=bid, content=""))
    d = e.model_dump()
    assert d["block"]["type"] == "text"
    assert d["block"]["block_id"] == bid


def test_block_start_with_tool_use_block():
    bid = gen_uuid()
    e = BlockStartEvent(agent_id="a1", thread_id="t1", message_id="m1",
                        block=ToolUseBlock(block_id=bid, tool_name="read_file", status="running"))
    d = e.model_dump()
    assert d["block"]["type"] == "tool_use"
    assert d["block"]["tool_name"] == "read_file"


def test_block_stop_with_final_fields():
    e = BlockStopEvent(agent_id="a1", thread_id="t1", message_id="m1",
                       block_id="bid", final_fields={"status": "completed"})
    d = e.model_dump()
    assert d["final_fields"]["status"] == "completed"


# ---------------------------------------------------------------------------
# Union discriminator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,expected_cls", [
    ({"type": "agent_start", "agent_id": "a1", "thread_id": "t1", "message_id": "m1", "agent_name": "C"}, AgentStartEvent),
    ({"type": "block_delta", "agent_id": "a1", "thread_id": "t1", "message_id": "m1", "block_id": "b", "delta": {}}, BlockDeltaEvent),
    ({"type": "block_stop", "agent_id": "a1", "thread_id": "t1", "message_id": "m1", "block_id": "b"}, BlockStopEvent),
    ({"type": "agent_done", "agent_id": "a1", "thread_id": "t1", "message_id": "m1"}, AgentDoneEvent),
    ({"type": "agent_error", "agent_id": "a1", "thread_id": "t1", "message_id": "m1", "error": "oops"}, AgentErrorEvent),
])
def test_union_discriminator(payload, expected_cls):
    event = _event_adapter.validate_python(payload)
    assert isinstance(event, expected_cls)