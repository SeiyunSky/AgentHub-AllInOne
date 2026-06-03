"""
api/v1/artifacts.py —— 产物操作端点

POST /api/v1/artifacts/diff/apply   一键应用 Diff CodeBlock 到本地文件

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.services.diff_apply_service import diff_apply_service

router = APIRouter()


class DiffApplyRequest(BaseModel):
    message_id: str
    edited_code: str | None = None  # 用户在 Monaco 里修改后的内容；None 时用消息原始 code


class DiffApplyResponse(BaseModel):
    success: bool
    applied_files: list[str]


@router.post(
    "/artifacts/diff/apply",
    response_model=DiffApplyResponse,
    summary="一键应用 Diff——把消息里的 CodeBlock 写入本地文件",
)
async def apply_diff(
    body: DiffApplyRequest,
    user_id: Annotated[str, Depends(get_current_user)],
) -> DiffApplyResponse:
    try:
        result = await diff_apply_service.apply(
            body.message_id,
            user_id=user_id,
            edited_code=body.edited_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return DiffApplyResponse(**result)
