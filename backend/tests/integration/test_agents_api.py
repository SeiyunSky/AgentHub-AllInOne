"""
Agents API 集成测试 — SQLite in-memory，不依赖真实 DB / Redis / LLM。

测试范围：
  GET    /api/v1/agents          列表
  POST   /api/v1/agents          创建
  GET    /api/v1/agents/{id}     详情
  PATCH  /api/v1/agents/{id}     更新
  DELETE /api/v1/agents/{id}     删除
  POST   /api/v1/agents/{id}/activate
  POST   /api/v1/agents/{id}/deactivate
  POST   /api/v1/agents/build        (mock LLM)
  POST   /api/v1/agents/build/confirm

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.database import get_db
from backend.main import create_app
import backend.models  # noqa: F401 — 确保所有 ORM 模型注册到 Base.metadata
from backend.models.base import Base
from backend.schemas.agent import AgentBuildDraft
from backend.domain.agent import AgentCapabilities


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """共享同一个 SQLite in-memory DB 和 TestClient，模块级别复用。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app = create_app(include_lifespan=False)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


@pytest.fixture
def agent_payload():
    return {
        "name": "Test Agent",
        "description": "A test agent",
        "type": "claude",
        "system_prompt": "You are a test agent.",
        "capabilities": {
            "supports_code": False,
            "supports_diff": False,
            "supports_approval": False,
            "supports_image": False,
        },
        "tags": ["test"],
        "is_public": False,
        "skill_ids": [],
    }


# ---------------------------------------------------------------------------
# CRUD 测试
# ---------------------------------------------------------------------------

def test_list_agents_empty(client):
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_agent(client, agent_payload):
    resp = client.post("/api/v1/agents", json=agent_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == agent_payload["name"]
    assert data["type"] == agent_payload["type"]
    assert data["is_active"] is True
    assert "id" in data


def test_list_agents_returns_created(client, agent_payload):
    client.post("/api/v1/agents", json=agent_payload)
    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert agent_payload["name"] in names


def test_get_agent(client, agent_payload):
    create_resp = client.post("/api/v1/agents", json=agent_payload)
    agent_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


def test_get_agent_not_found(client):
    resp = client.get("/api/v1/agents/nonexistent-id")
    assert resp.status_code == 404


def test_update_agent(client, agent_payload):
    create_resp = client.post("/api/v1/agents", json=agent_payload)
    agent_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"name": "Updated Agent", "tags": ["updated"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Agent"
    assert data["tags"] == ["updated"]


def test_update_agent_not_found(client):
    resp = client.patch("/api/v1/agents/nonexistent-id", json={"name": "X"})
    assert resp.status_code == 404


def test_deactivate_activate_agent(client, agent_payload):
    create_resp = client.post("/api/v1/agents", json=agent_payload)
    agent_id = create_resp.json()["id"]

    deact_resp = client.post(f"/api/v1/agents/{agent_id}/deactivate")
    assert deact_resp.status_code == 200
    assert deact_resp.json()["is_active"] is False

    act_resp = client.post(f"/api/v1/agents/{agent_id}/activate")
    assert act_resp.status_code == 200
    assert act_resp.json()["is_active"] is True


def test_delete_agent(client, agent_payload):
    create_resp = client.post("/api/v1/agents", json=agent_payload)
    agent_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/agents/{agent_id}")
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 404


def test_delete_agent_not_found(client):
    resp = client.delete("/api/v1/agents/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /agents/build + /agents/build/confirm（mock LLM，不发真实请求）
# ---------------------------------------------------------------------------

def _make_draft() -> AgentBuildDraft:
    return AgentBuildDraft(
        name="Mock Agent",
        description="A mocked agent",
        type="claude",
        system_prompt="You are a mock agent.",
        capabilities=AgentCapabilities(),
        tags=["mock"],
        suggested_skill_names=[],
    )


def test_build_agent_mock_llm(client):
    from backend.services.agent_builder_service import AgentBuilderService

    mock_result = ("test-session-id", _make_draft())

    with patch.object(AgentBuilderService, "build", new=AsyncMock(return_value=mock_result)):
        resp = client.post("/api/v1/agents/build", json={"description": "I want a mock agent"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"] == "test-session-id"
    assert data["draft"]["name"] == "Mock Agent"


def test_build_confirm_creates_agent(client):
    from backend.services.agent_builder_service import AgentBuilderService, _store_put

    session_id = "confirm-test-session"
    draft = _make_draft()
    _store_put("GUGA", session_id, draft)

    resp = client.post(
        "/api/v1/agents/build/confirm",
        json={
            "session_id": session_id,
            "edited_draft": {
                "name": draft.name,
                "description": draft.description,
                "type": draft.type,
                "system_prompt": draft.system_prompt,
                "capabilities": {
                    "supports_code": False,
                    "supports_diff": False,
                    "supports_approval": False,
                    "supports_image": False,
                },
                "tags": draft.tags,
                "suggested_skill_names": [],
            },
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Mock Agent"


def test_build_confirm_invalid_session(client):
    resp = client.post(
        "/api/v1/agents/build/confirm",
        json={
            "session_id": "nonexistent-session",
            "edited_draft": {
                "name": "X",
                "type": "claude",
                "system_prompt": "x",
                "capabilities": {
                    "supports_code": False,
                    "supports_diff": False,
                    "supports_approval": False,
                    "supports_image": False,
                },
                "tags": [],
                "suggested_skill_names": [],
            },
        },
    )
    assert resp.status_code == 422
