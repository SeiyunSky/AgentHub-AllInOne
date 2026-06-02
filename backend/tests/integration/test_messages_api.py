"""
模块六:messages API + conversations 归属校验集成测试

测试范围:
  POST   /api/v1/messages/{id}/feedback    点赞 / 踩 / 清除
  DELETE /api/v1/messages/{id}             软删除
  POST   /api/v1/messages/{id}/regenerate  未实装 → 501
  GET    /api/v1/conversations/{id}         跨用户访问 → 403
  PATCH  /api/v1/conversations/{id}         跨用户编辑 → 403
  GET    /api/v1/conversations/{id}/messages 跨用户拉历史 → 403
  不存在 conversation → 404
  不存在 message → 404

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-29
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.database import get_db
from backend.main import create_app
import backend.models  # noqa: F401
from backend.models.base import Base
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.message import Message


def body(resp):
    if resp.status_code == 204 or not resp.content:
        return None
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


@pytest.fixture(scope="module")
def env():
    """SQLite in-memory + 两个用户 + 一个会话 + 一条 assistant 消息。

    message_service / conversation_service 内部用 SessionLocal 单例,
    必须 monkeypatch 这俩模块的 SessionLocal 才能让它们走测试 DB。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    s = TestSession()
    s.add(User(id="user-a", username="alice", password_hash="x"*60, display_name="Alice"))
    s.add(User(id="user-b", username="bob", password_hash="x"*60, display_name="Bob"))
    s.add(Conversation(id="conv-a", user_id="user-a", title="A's chat", mode="single"))
    s.add(Message(
        id="msg-assistant-1",
        conversation_id="conv-a",
        agent_id="agent-coder-builtin",
        role="assistant",
        content=[{"type": "text", "block_id": "b-1", "content": "hello"}],
        status="done",
    ))
    s.commit()
    s.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # monkeypatch 各 service 模块内 import 的 SessionLocal
    import backend.services.message_service as _msg_mod
    import backend.services.conversation_service as _conv_mod
    import backend.services.chat_service as _chat_mod
    original = {
        "msg": _msg_mod.SessionLocal,
        "conv": _conv_mod.SessionLocal,
        "chat": _chat_mod.SessionLocal,
    }
    _msg_mod.SessionLocal = TestSession
    _conv_mod.SessionLocal = TestSession
    _chat_mod.SessionLocal = TestSession

    app = create_app(include_lifespan=False)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c, TestSession

    _msg_mod.SessionLocal = original["msg"]
    _conv_mod.SessionLocal = original["conv"]
    _chat_mod.SessionLocal = original["chat"]


# ============================================================
# messages API
# ============================================================

def test_feedback_up(env):
    client, _ = env
    resp = client.post(
        "/api/v1/messages/msg-assistant-1/feedback",
        headers={"X-User-Id": "user-a"},
        json={"feedback": "up"},
    )
    assert resp.status_code == 204


def test_feedback_down(env):
    client, _ = env
    resp = client.post(
        "/api/v1/messages/msg-assistant-1/feedback",
        headers={"X-User-Id": "user-a"},
        json={"feedback": "down"},
    )
    assert resp.status_code == 204


def test_feedback_clear(env):
    client, _ = env
    resp = client.post(
        "/api/v1/messages/msg-assistant-1/feedback",
        headers={"X-User-Id": "user-a"},
        json={"feedback": None},
    )
    assert resp.status_code == 204


def test_feedback_message_not_found(env):
    client, _ = env
    resp = client.post(
        "/api/v1/messages/nonexistent/feedback",
        headers={"X-User-Id": "user-a"},
        json={"feedback": "up"},
    )
    assert resp.status_code == 404


def test_regenerate_not_implemented(env):
    client, _ = env
    resp = client.post(
        "/api/v1/messages/msg-assistant-1/regenerate",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 501


def test_soft_delete_message(env):
    client, TestSession = env
    # 单独造一条只给本测试用,免得污染 feedback 测试
    s = TestSession()
    s.add(Message(
        id="msg-to-delete",
        conversation_id="conv-a",
        agent_id="agent-coder-builtin",
        role="assistant",
        content=[{"type": "text", "block_id": "b-x", "content": "byebye"}],
        status="done",
    ))
    s.commit()
    s.close()

    resp = client.delete(
        "/api/v1/messages/msg-to-delete",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 204


def test_soft_delete_message_not_found(env):
    client, _ = env
    resp = client.delete(
        "/api/v1/messages/nonexistent",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 404


# ============================================================
# conversations 归属校验
# ============================================================

def test_get_conversation_owner_ok(env):
    client, _ = env
    resp = client.get(
        "/api/v1/conversations/conv-a",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 200
    assert body(resp)["id"] == "conv-a"


def test_get_conversation_cross_user_403(env):
    client, _ = env
    resp = client.get(
        "/api/v1/conversations/conv-a",
        headers={"X-User-Id": "user-b"},
    )
    assert resp.status_code == 403


def test_get_conversation_not_found_404(env):
    client, _ = env
    resp = client.get(
        "/api/v1/conversations/nonexistent",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 404


def test_patch_conversation_cross_user_403(env):
    client, _ = env
    resp = client.patch(
        "/api/v1/conversations/conv-a",
        headers={"X-User-Id": "user-b"},
        json={"title": "hijacked"},
    )
    assert resp.status_code == 403


def test_messages_list_cross_user_403(env):
    client, _ = env
    resp = client.get(
        "/api/v1/conversations/conv-a/messages",
        headers={"X-User-Id": "user-b"},
    )
    assert resp.status_code == 403


def test_messages_list_owner_ok(env):
    client, _ = env
    resp = client.get(
        "/api/v1/conversations/conv-a/messages",
        headers={"X-User-Id": "user-a"},
    )
    assert resp.status_code == 200
    msgs = body(resp)
    assert isinstance(msgs, list)
