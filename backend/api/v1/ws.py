"""
api/v1/ws.py —— WebSocket 端点

处理双向实时通信（审批决策 / Diff 应用）：
- 客户端发 ApprovalDecisionRequest → 调 approval.decide() 唤醒等待的 hook
- 客户端发 ApplyDiffRequest → TODO[diff]: diff_apply_service 实装后接通
- 服务端回 ApprovalAcknowledgedEvent / 错误提示

连接路径：ws://host/api/v1/ws/{conversation_id}
鉴权(MVP)：URL query param user_id（WebSocket 不支持自定义 header）

队伍：咕嘎一辈子队
修改者：I778387
修改日期：2026-05-28
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.hooks.approval import decide as approval_decide
from backend.schemas.ws import ApprovalAcknowledgedEvent, ApprovalDecisionRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
    user_id: Optional[str] = Query(default=None, description="用户 ID（MVP 鉴权）"),
) -> None:
    await websocket.accept()
    logger.info("WS connected conversation=%s user=%s", conversation_id, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "approval_decision":
                try:
                    req = ApprovalDecisionRequest(**data)
                except Exception as e:
                    await websocket.send_json({"type": "error", "detail": f"消息格式错误: {e}"})
                    continue

                ok = approval_decide(
                    block_id=req.block_id,
                    decision=req.decision,
                    reject_reason=req.reason,
                )
                if not ok:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"block_id {req.block_id} 不存在或已超时",
                    })
                    continue

                ack = ApprovalAcknowledgedEvent(
                    message_id=req.message_id,
                    block_id=req.block_id,
                    decision=req.decision,
                    thread_id="",  # TODO[ws]: 从 approval 上下文回填 thread_id
                )
                await websocket.send_json(ack.model_dump(mode="json"))
                logger.info(
                    "WS approval_decision processed block_id=%s decision=%s",
                    req.block_id, req.decision,
                )

            elif msg_type == "apply_diff":
                # TODO[diff]: diff_apply_service 实装后接通
                await websocket.send_json({
                    "type": "error",
                    "detail": "apply_diff 功能尚未实装",
                })

            else:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"未知消息类型: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("WS disconnected conversation=%s user=%s", conversation_id, user_id)
    except Exception:
        logger.exception("WS error conversation=%s", conversation_id)
