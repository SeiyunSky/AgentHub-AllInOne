"""
api/v1/approvals.py —— 审批决策 HTTP 端点

前端点 Approve / Reject 后发 POST，后端调 approval.decide() 唤醒等待的 hook。
比 WebSocket 更简单：无需维护长连接，一次请求完成决策。
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.hooks.approval import decide as approval_decide

router = APIRouter()


class ApprovalDecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    reason: Optional[str] = None


@router.post("/approvals/{block_id}/decide")
async def decide_approval(block_id: str, body: ApprovalDecisionBody) -> dict:
    ok = approval_decide(
        block_id=block_id,
        decision=body.decision,
        reject_reason=body.reason,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"block_id {block_id} 不存在或已超时")
    return {"block_id": block_id, "decision": body.decision}
