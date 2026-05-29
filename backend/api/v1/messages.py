"""
api/v1/messages.py —— 消息操作端点

端点：
- POST   /api/v1/messages/{id}/feedback    点赞 / 踩
- DELETE /api/v1/messages/{id}             软删除消息
- POST   /api/v1/messages/{id}/regenerate  重新生成（MVP 返回 501）

鉴权(MVP)：全部走 X-User-Id header，见 api/deps.py:get_current_user。

队伍：咕嘎一辈子队
修改者：I778387
修改日期：2026-05-28
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.services.message_service import message_service


router = APIRouter()


# ============================================================
# 请求体 Schema
# ============================================================

class FeedbackRequest(BaseModel):
    feedback: Optional[str] = None  # "up" / "down" / None（清除）


# ============================================================
# POST /api/v1/messages/{id}/feedback
# ============================================================

@router.post(
    "/messages/{message_id}/feedback",
    summary="消息点赞 / 踩（feedback: up / down / null）",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_message_feedback(
    message_id: Annotated[str, Path(description="消息 ID")],
    body: FeedbackRequest,
    user_id: Annotated[str, Depends(get_current_user)],
) -> None:
    msg = await message_service.get(message_id)
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"消息 {message_id} 不存在",
        )
    await message_service.set_feedback(message_id, body.feedback)


# ============================================================
# DELETE /api/v1/messages/{id}
# ============================================================

@router.delete(
    "/messages/{message_id}",
    summary="软删除消息",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_message(
    message_id: Annotated[str, Path(description="消息 ID")],
    user_id: Annotated[str, Depends(get_current_user)],
) -> None:
    ok = await message_service.soft_delete(message_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"消息 {message_id} 不存在",
        )


# ============================================================
# POST /api/v1/messages/{id}/regenerate
# ============================================================

@router.post(
    "/messages/{message_id}/regenerate",
    summary="重新生成消息（未实装）",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def regenerate_message(
    message_id: Annotated[str, Path(description="消息 ID")],
    user_id: Annotated[str, Depends(get_current_user)],
) -> None:
    # TODO[regen]: 软删原消息 + 重新触发 chat_service，待模块十前端联调时实装
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="重新生成功能尚未实装",
    )
