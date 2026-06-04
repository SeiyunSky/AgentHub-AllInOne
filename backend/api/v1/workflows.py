"""
api/v1/workflows.py —— workflow 视图持久化端点

POST /api/v1/workflows                                  落一行 workflow
GET  /api/v1/workflows?conversation_id=xxx&limit=20     查询某会话历史

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from backend.api.deps import get_current_user
from backend.schemas.workflow import WorkflowCreate, WorkflowResponse
from backend.services.conversation_service import conversation_service
from backend.services.workflow_service import workflow_service

router = APIRouter()


@router.post(
    "/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="保存一份 workflow（前端 round_done 后调用）",
)
async def create_workflow(
    body: WorkflowCreate,
    user_id: Annotated[str, Depends(get_current_user)],
) -> WorkflowResponse:
    # 校验 conversation 归属
    await conversation_service.assert_owned_by(body.conversation_id, user_id)

    wf = await workflow_service.save(
        user_id=user_id,
        conversation_id=body.conversation_id,
        trigger_message_id=body.trigger_message_id,
        threads=body.threads,
    )
    return WorkflowResponse.model_validate(wf)


@router.get(
    "/workflows",
    response_model=list[WorkflowResponse],
    summary="查询某会话的 workflow 历史（最新在前）",
)
async def list_workflows(
    user_id: Annotated[str, Depends(get_current_user)],
    conversation_id: Annotated[str, Query(description="会话 ID")],
    limit: Annotated[int, Query(ge=1, le=100, description="每页返回数量")] = 20,
    offset: Annotated[int, Query(ge=0, description="分页偏移量")] = 0,
) -> list[WorkflowResponse]:
    await conversation_service.assert_owned_by(conversation_id, user_id)

    items = await workflow_service.list_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    return [WorkflowResponse.model_validate(w) for w in items]
