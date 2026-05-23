"""Tests for adapters/events.py — Pydantic models, camelCase serialization, union discriminator."""
import pytest
from pydantic import TypeAdapter

from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    ApprovalRequestEvent,
    ArtifactDiffEvent,
    ArtifactHtmlEvent,
    DeployDoneEvent,
    DeployProgressEvent,
    RoundDoneEvent,
    SubAgentSpawnEvent,
    TokenEvent,
)

_event_adapter = TypeAdapter(AgentEvent)


# ---------------------------------------------------------------------------
# type field defaults
# ---------------------------------------------------------------------------

def test_agent_start_event_type():
    e = AgentStartEvent(agent_id="a1", agent_name="Claude", message_id="m1")
    assert e.type == "agent_start"


def test_token_event_type():
    e = TokenEvent(agent_id="a1", message_id="m1", content="hello")
    assert e.type == "token"


def test_artifact_html_event_type():
    e = ArtifactHtmlEvent(agent_id="a1", message_id="m1", preview_url="/p")
    assert e.type == "artifact_html"


def test_artifact_diff_event_type():
    e = ArtifactDiffEvent(agent_id="a1", message_id="m1", file="a.py", patch="@@")
    assert e.type == "artifact_diff"


def test_approval_request_event_type():
    e = ApprovalRequestEvent(agent_id="a1", message_id="m1", action="run", detail="npm i")
    assert e.type == "approval_request"


def test_sub_agent_spawn_event_type():
    e = SubAgentSpawnEvent(agent_id="a1", message_id="m1", sub_task="do thing")
    assert e.type == "sub_agent_spawn"


def test_deploy_progress_event_type():
    e = DeployProgressEvent(stage="build", percent=50)
    assert e.type == "deploy_progress"


def test_deploy_done_event_type():
    e = DeployDoneEvent(url="https://example.com")
    assert e.type == "deploy_done"


def test_agent_done_event_type():
    e = AgentDoneEvent(agent_id="a1", message_id="m1")
    assert e.type == "agent_done"


def test_agent_error_event_type():
    e = AgentErrorEvent(agent_id="a1", message_id="m1", error="timeout")
    assert e.type == "agent_error"


def test_round_done_event_type():
    e = RoundDoneEvent()
    assert e.type == "round_done"


# ---------------------------------------------------------------------------
# camelCase serialization
# ---------------------------------------------------------------------------

def test_agent_start_camel_serialization():
    e = AgentStartEvent(agent_id="a1", agent_name="Claude", message_id="m1")
    d = e.model_dump(by_alias=True)
    assert "agentId" in d
    assert "agentName" in d
    assert "messageId" in d
    assert "agent_id" not in d


def test_artifact_html_preview_url_camel():
    e = ArtifactHtmlEvent(agent_id="a1", message_id="m1", preview_url="/preview/abc")
    d = e.model_dump(by_alias=True)
    assert d["previewUrl"] == "/preview/abc"
    assert "preview_url" not in d


def test_artifact_diff_camel():
    e = ArtifactDiffEvent(agent_id="a1", message_id="m1", file="x.py", patch="@@", additions=3, deletions=1)
    d = e.model_dump(by_alias=True)
    assert d["agentId"] == "a1"
    assert d["messageId"] == "m1"
    assert d["additions"] == 3


def test_round_done_serialization():
    e = RoundDoneEvent()
    d = e.model_dump(by_alias=True)
    assert d == {"type": "round_done"}


# ---------------------------------------------------------------------------
# Union discriminator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,expected_cls", [
    ({"type": "agent_start", "agentId": "a1", "agentName": "C", "messageId": "m1"}, AgentStartEvent),
    ({"type": "token", "agentId": "a1", "messageId": "m1", "content": "hi"}, TokenEvent),
    ({"type": "artifact_diff", "agentId": "a1", "messageId": "m1", "file": "f.py", "patch": "@@"}, ArtifactDiffEvent),
    ({"type": "approval_request", "agentId": "a1", "messageId": "m1", "action": "run", "detail": "x"}, ApprovalRequestEvent),
    ({"type": "agent_done", "agentId": "a1", "messageId": "m1"}, AgentDoneEvent),
    ({"type": "agent_error", "agentId": "a1", "messageId": "m1", "error": "oops"}, AgentErrorEvent),
    ({"type": "round_done"}, RoundDoneEvent),
    ({"type": "deploy_progress", "stage": "build", "percent": 10}, DeployProgressEvent),
    ({"type": "deploy_done", "url": "https://x.com"}, DeployDoneEvent),
    ({"type": "sub_agent_spawn", "agentId": "a1", "messageId": "m1", "subTask": "task"}, SubAgentSpawnEvent),
    ({"type": "artifact_html", "agentId": "a1", "messageId": "m1", "previewUrl": "/p"}, ArtifactHtmlEvent),
])
def test_union_discriminator(payload, expected_cls):
    event = _event_adapter.validate_python(payload)
    assert isinstance(event, expected_cls)
