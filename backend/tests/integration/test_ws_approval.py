"""
模块八:WebSocket 端点 + ApprovalHook 闭环集成测试

测试范围:
  WS /ws/{conv_id}:
    - approval_decision approve → approval.decide 投递成功 → ApprovalAcknowledgedEvent
    - approval_decision 不存在的 block_id → error
    - approval_decision schema 错 → error
    - 未知消息 type → error
  approval._publish_approval_block:
    - 创建 ApprovalBlock 消息 + 推 SSE BlockStartEvent

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-29
"""

from __future__ import annotations

import asyncio

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
from backend.hooks.approval import _PendingApproval, _pending_approvals, decide
from backend.hooks.base import HookContext, HookEvent


@pytest.fixture
def app_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    s = TestSession()
    s.add(User(id="ws-user", username="wsu", password_hash="x"*60, display_name="WS"))
    s.add(Conversation(id="ws-conv", user_id="ws-user", title="ws", mode="single"))
    s.commit()
    s.close()

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    import backend.services.message_service as _msg_mod
    import backend.services.conversation_service as _conv_mod
    original = (_msg_mod.SessionLocal, _conv_mod.SessionLocal)
    _msg_mod.SessionLocal = TestSession
    _conv_mod.SessionLocal = TestSession

    app = create_app(include_lifespan=False)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c, TestSession

    _msg_mod.SessionLocal, _conv_mod.SessionLocal = original


@pytest.fixture(autouse=True)
def clean_pending_approvals():
    _pending_approvals.clear()
    yield
    _pending_approvals.clear()


# ============================================================
# WS approval_decision 路径
# ============================================================

def test_approval_decision_unknown_block_returns_error(app_client):
    client, _ = app_client
    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        ws.send_json({
            "type": "approval_decision",
            "message_id": "m1",
            "block_id": "nonexistent-block",
            "decision": "approve",
        })
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "不存在" in resp["detail"] or "nonexistent" in resp["detail"]


def test_approval_decision_invalid_schema_returns_error(app_client):
    client, _ = app_client
    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        # 缺 message_id / block_id 必填字段
        ws.send_json({
            "type": "approval_decision",
            "decision": "approve",
        })
        resp = ws.receive_json()
        assert resp["type"] == "error"


def test_unknown_message_type_returns_error(app_client):
    client, _ = app_client
    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        ws.send_json({"type": "totally_unknown"})
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "未知" in resp["detail"] or "unknown" in resp["detail"].lower()


def test_apply_diff_returns_not_implemented(app_client):
    client, _ = app_client
    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        ws.send_json({
            "type": "apply_diff",
            "message_id": "m1",
            "block_id": "b1",
        })
        resp = ws.receive_json()
        assert resp["type"] == "error"
        assert "尚未实装" in resp["detail"]


def test_approval_decision_wakes_pending_hook(app_client):
    """
    模拟 ApprovalHook 注册了一个 _PendingApproval 在等待,
    WS 调 approval_decision 后,该 pending 的 event 被 set + decision 写入。
    """
    client, _ = app_client
    block_id = "test-block-1"
    pending = _PendingApproval(block_id=block_id, event=asyncio.Event())
    _pending_approvals[block_id] = pending

    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        ws.send_json({
            "type": "approval_decision",
            "message_id": "msg-x",
            "block_id": block_id,
            "decision": "approve",
        })
        ack = ws.receive_json()

    assert ack["type"] == "approval_acknowledged"
    assert ack["block_id"] == block_id
    assert ack["decision"] == "approve"
    # decide 已经投递:event set + decision 写入
    assert pending.event.is_set()
    assert pending.decision == "approve"


def test_approval_decision_reject_with_reason(app_client):
    client, _ = app_client
    block_id = "test-block-reject"
    pending = _PendingApproval(block_id=block_id, event=asyncio.Event())
    _pending_approvals[block_id] = pending

    with client.websocket_connect("/api/v1/ws/ws-conv?user_id=ws-user") as ws:
        ws.send_json({
            "type": "approval_decision",
            "message_id": "msg-r",
            "block_id": block_id,
            "decision": "reject",
            "reason": "测试拒绝原因",
        })
        ws.receive_json()

    assert pending.event.is_set()
    assert pending.decision == "reject"
    assert pending.reject_reason == "测试拒绝原因"


# ============================================================
# decide() 直接调用(不经 WS)
# ============================================================

def test_decide_returns_false_for_unknown_block():
    assert decide("never-registered", "approve") is False


def test_decide_sets_event_and_decision():
    block_id = "direct-decide"
    pending = _PendingApproval(block_id=block_id, event=asyncio.Event())
    _pending_approvals[block_id] = pending

    ok = decide(block_id, "approve")
    assert ok is True
    assert pending.event.is_set()
    assert pending.decision == "approve"


# ============================================================
# _publish_approval_block:落库 + 推 SSE
# ============================================================

@pytest.mark.asyncio
async def test_publish_approval_block_persists_message(app_client, monkeypatch):
    """
    调 ApprovalHook._publish_approval_block 后:
    1. messages 表新增 assistant 消息含 ApprovalBlock
    2. stream_service 收到 BlockStartEvent
    """
    client, TestSession = app_client

    from backend.hooks.approval import ApprovalHook
    from backend.services import stream_service as _stream_mod

    captured_events: list = []

    async def _capture_push(conv_id, event):
        captured_events.append((conv_id, event))

    monkeypatch.setattr(_stream_mod.stream_service, "push_event", _capture_push)

    ctx = HookContext(
        event=HookEvent.PRE_TOOL_USE,
        trace_id="trace-x",
        user_id="ws-user",
        conversation_id="ws-conv",
        thread_id="thread-x",
        message_id="user-msg-x",
        agent_id="some-agent",
        tool_name="create_file",
        tool_input={"path": "/tmp/x", "content": "hi"},
    )

    await ApprovalHook._publish_approval_block(ctx, "block-publish-1", "create_file")

    # 1. messages 表落库
    s = TestSession()
    try:
        from backend.models.message import Message
        msgs = s.query(Message).filter(Message.conversation_id == "ws-conv").all()
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg.role == "assistant"
        assert msg.thread_id == "thread-x"
        # content 含 approval block
        approval_blocks = [b for b in (msg.content or []) if b.get("type") == "approval"]
        assert len(approval_blocks) == 1
        ab = approval_blocks[0]
        assert ab["block_id"] == "block-publish-1"
        assert ab["action"] == "create_file"
    finally:
        s.close()

    # 2. SSE 推送至少一条 BlockStartEvent
    assert len(captured_events) >= 1
    conv_id, event = captured_events[0]
    assert conv_id == "ws-conv"
    assert event.type == "block_start"
