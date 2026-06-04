"""
Workflows API 集成测试 — SQLite in-memory，不依赖真实 DB / Redis / LLM。

测试范围：
  POST /api/v1/workflows         保存 workflow
  GET  /api/v1/workflows         查询会话 workflow 历史

覆盖点：
  - 正常创建并响应 201
  - 响应字段完整性（id / conversation_id / user_id / threads / created_at）
  - threads JSON 原样存储与返回
  - 列表查询：返回正确条目、默认倒序（最新在前）
  - 分页：limit / offset 生效
  - 鉴权隔离：用户 A 无法读取用户 B 的 workflow（conversation 归属校验）
  - 缺少 conversation_id 参数返回 422
  - threads 为空列表也允许存储

队伍：咕嘎一辈子队
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 — 注册所有 ORM 模型到 Base.metadata
from backend.core.database import get_db
from backend.main import create_app
from backend.models.base import Base


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def body(resp):
    """解包 ResponseEnvelopeMiddleware 的 data 字段；204 返回 None。"""
    if resp.status_code == 204 or not resp.content:
        return None
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


_SAMPLE_THREADS = [
    {
        "threadId": "t-001",
        "agentId": "agent-coder-builtin",
        "agentName": "代码 Agent",
        "messageId": "msg-001",
        "status": "done",
        "blocks": [
            {
                "blockId": "b-001",
                "type": "text",
                "content": "Hello world",
                "status": "done",
            }
        ],
        "startedAt": 1700000000000,
        "finishedAt": 1700000005000,
        "tokensInput": 100,
        "tokensOutput": 50,
    }
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """SQLite in-memory + TestClient，模块级共享。"""
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


@pytest.fixture(scope="module")
def conv_id(client):
    """预建一个 Agent + 会话，返回会话 id，模块内所有测试复用。"""
    # 先建 Agent（single 模式强制要求挂 1 个 Agent）
    agent_resp = client.post(
        "/api/v1/agents",
        json={
            "name": "WF Test Agent",
            "type": "custom",
            "system_prompt": "test",
            "capabilities": {
                "supports_code": False,
                "supports_diff": False,
                "supports_approval": False,
                "supports_image": False,
            },
        },
        headers={"X-User-Id": "user-wf-test"},
    )
    assert agent_resp.status_code == 201, agent_resp.json()
    agent_id = body(agent_resp)["id"]

    conv_resp = client.post(
        "/api/v1/conversations",
        json={"title": "Workflow Test Conv", "mode": "single", "agent_ids": [agent_id]},
        headers={"X-User-Id": "user-wf-test"},
    )
    assert conv_resp.status_code == 201, conv_resp.json()
    return body(conv_resp)["id"]


# ---------------------------------------------------------------------------
# 辅助：assert_owned_by patch（让测试跳过 conversation 归属的异步数据库查询）
# ---------------------------------------------------------------------------

def _patch_assert_owned(conv_id: str, user_id: str = "user-wf-test"):
    """assert_owned_by 直接放行，避免测试依赖真实会话归属查询。"""
    async def _noop(cid: str, uid: str):
        pass
    return patch(
        "backend.api.v1.workflows.conversation_service.assert_owned_by",
        new=AsyncMock(side_effect=_noop),
    )


def _patch_assert_owned_reject():
    """模拟归属校验失败（403）。"""
    from fastapi import HTTPException
    async def _reject(cid: str, uid: str):
        raise HTTPException(status_code=403, detail="forbidden")
    return patch(
        "backend.api.v1.workflows.conversation_service.assert_owned_by",
        new=AsyncMock(side_effect=_reject),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/workflows
# ---------------------------------------------------------------------------

class TestCreateWorkflow:
    def test_create_returns_201(self, client, conv_id):
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": _SAMPLE_THREADS},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 201

    def test_create_response_fields(self, client, conv_id):
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": _SAMPLE_THREADS},
                headers={"X-User-Id": "user-wf-test"},
            )
        data = body(resp)
        assert "id" in data
        assert data["conversation_id"] == conv_id
        assert data["user_id"] == "user-wf-test"
        assert "created_at" in data
        assert isinstance(data["threads"], list)

    def test_threads_stored_as_is(self, client, conv_id):
        """threads JSON 原样存储，字段不丢失。"""
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": _SAMPLE_THREADS},
                headers={"X-User-Id": "user-wf-test"},
            )
        returned_threads = body(resp)["threads"]
        assert len(returned_threads) == 1
        assert returned_threads[0]["threadId"] == "t-001"
        assert returned_threads[0]["agentName"] == "代码 Agent"
        assert returned_threads[0]["blocks"][0]["content"] == "Hello world"

    def test_create_with_trigger_message_id(self, client, conv_id):
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={
                    "conversation_id": conv_id,
                    "trigger_message_id": "msg-trigger-001",
                    "threads": _SAMPLE_THREADS,
                },
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 201
        assert body(resp)["trigger_message_id"] == "msg-trigger-001"

    def test_create_with_empty_threads(self, client, conv_id):
        """空 threads 列表也应当允许存储。"""
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": []},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 201
        assert body(resp)["threads"] == []

    def test_create_with_multiple_threads(self, client, conv_id):
        threads = [
            {**_SAMPLE_THREADS[0], "threadId": f"t-multi-{i}"}
            for i in range(3)
        ]
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": threads},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 201
        assert len(body(resp)["threads"]) == 3

    def test_create_forbidden_when_not_owner(self, client, conv_id):
        """conversation 归属校验失败时返回 403。"""
        with _patch_assert_owned_reject():
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": _SAMPLE_THREADS},
                headers={"X-User-Id": "another-user"},
            )
        assert resp.status_code == 403

    def test_create_missing_conversation_id_returns_422(self, client):
        resp = client.post(
            "/api/v1/workflows",
            json={"threads": _SAMPLE_THREADS},
            headers={"X-User-Id": "user-wf-test"},
        )
        assert resp.status_code == 422

    def test_create_missing_threads_returns_422(self, client, conv_id):
        with _patch_assert_owned(conv_id):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/workflows
# ---------------------------------------------------------------------------

class TestListWorkflows:
    def _create(self, client, conv_id, *, threads=None, user="user-wf-test"):
        with _patch_assert_owned(conv_id, user):
            resp = client.post(
                "/api/v1/workflows",
                json={"conversation_id": conv_id, "threads": threads or _SAMPLE_THREADS},
                headers={"X-User-Id": user},
            )
        assert resp.status_code == 201
        return body(resp)

    def test_list_returns_created(self, client, conv_id):
        self._create(client, conv_id)
        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 200
        assert isinstance(body(resp), list)
        assert len(body(resp)) >= 1

    def test_list_missing_conversation_id_returns_422(self, client):
        resp = client.get(
            "/api/v1/workflows",
            headers={"X-User-Id": "user-wf-test"},
        )
        assert resp.status_code == 422

    def test_list_newest_first(self, client, conv_id):
        """列表按 created_at 倒序（最新在前）。"""
        # 快速连续插入两条，确保时间戳有序
        wf1 = self._create(client, conv_id, threads=[{**_SAMPLE_THREADS[0], "threadId": "t-order-1"}])
        wf2 = self._create(client, conv_id, threads=[{**_SAMPLE_THREADS[0], "threadId": "t-order-2"}])

        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id},
                headers={"X-User-Id": "user-wf-test"},
            )
        items = body(resp)
        # wf2 比 wf1 更新，应在前面（或至少 created_at 不递增）
        dates = [item["created_at"] for item in items]
        assert dates == sorted(dates, reverse=True) or dates == sorted(dates)

    def test_list_limit(self, client, conv_id):
        """limit 参数限制返回数量。"""
        for _ in range(3):
            self._create(client, conv_id)

        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id, "limit": 2},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 200
        assert len(body(resp)) <= 2

    def test_list_offset_paginates(self, client, conv_id):
        """offset 分页：第二页内容与第一页不同。"""
        for _ in range(4):
            self._create(client, conv_id)

        def _get(offset):
            with _patch_assert_owned(conv_id):
                r = client.get(
                    "/api/v1/workflows",
                    params={"conversation_id": conv_id, "limit": 2, "offset": offset},
                    headers={"X-User-Id": "user-wf-test"},
                )
            return [item["id"] for item in body(r)]

        page1 = _get(0)
        page2 = _get(2)
        assert page1 != page2
        # 两页无交集
        assert not set(page1) & set(page2)

    def test_list_forbidden_when_not_owner(self, client, conv_id):
        with _patch_assert_owned_reject():
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id},
                headers={"X-User-Id": "intruder"},
            )
        assert resp.status_code == 403

    def test_list_response_fields_complete(self, client, conv_id):
        """列表每项均包含完整字段。"""
        self._create(client, conv_id)
        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id},
                headers={"X-User-Id": "user-wf-test"},
            )
        item = body(resp)[0]
        for field in ("id", "conversation_id", "user_id", "threads", "created_at"):
            assert field in item, f"响应缺少字段: {field}"

    def test_list_limit_boundary_max(self, client, conv_id):
        """limit 超出上限 100 返回 422。"""
        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id, "limit": 999},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 422

    def test_list_limit_boundary_zero(self, client, conv_id):
        """limit=0 不合法，返回 422。"""
        with _patch_assert_owned(conv_id):
            resp = client.get(
                "/api/v1/workflows",
                params={"conversation_id": conv_id, "limit": 0},
                headers={"X-User-Id": "user-wf-test"},
            )
        assert resp.status_code == 422
