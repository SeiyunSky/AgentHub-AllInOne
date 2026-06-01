"""
api/v1/conversations.py —— 会话 CRUD HTTP 端点

5 个端点:
- POST   /api/v1/conversations             新建会话(挂载初始 Agent)
- GET    /api/v1/conversations             我的会话列表(置顶 + 最近活跃排序)
- GET    /api/v1/conversations/{id}        会话详情(含成员)
- PATCH  /api/v1/conversations/{id}        重命名 / 置顶 / 归档
- GET    /api/v1/conversations/{id}/messages   会话历史消息(分页)

鉴权(MVP):全部走 X-User-Id header,见 api/deps.py:get_current_user。

权限校验(MVP 留 TODO):
- get / patch / messages 三类端点理论上要校验 conversation_id 属于 user_id
- 防止 A 用户访问 B 的会话
- 列表端点(GET /conversations)走 list_for_user(user_id) 内置过滤,不需要校验
- MVP 先信任传入 user_id,后续 conversation_service.assert_owned_by 实装后接通

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from backend.api.deps import get_current_user
from backend.schemas.conversation import (
    AgentMember,
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    ConversationUpdate,
)
from backend.schemas.message import MessageResponse
from backend.services.conversation_service import conversation_service
from backend.services.message_service import message_service


logger = logging.getLogger(__name__)


router = APIRouter()


# ============================================================
# 内部辅助:把 ORM Conversation 转成 ConversationResponse(含 agents 列表)
# ============================================================

async def _to_conversation_response(conv) -> ConversationResponse:
    """
    把 ORM Conversation 转成 ConversationResponse。
    需要额外查 conversation_agents → agents 拼成员列表,所以单独抽函数。
    """
    agents = await conversation_service.get_active_agents(conv.id)
    members = [AgentMember.model_validate(a) for a in agents]
    base = ConversationListItem.model_validate(conv).model_dump()
    return ConversationResponse(
        **base,
        user_id=conv.user_id,
        agents=members,
    )


# ============================================================
# POST /api/v1/conversations —— 新建会话
# ============================================================

@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新建会话(挂载初始 Agent)",
)
async def create_conversation(
    request: ConversationCreate,
    user_id: Annotated[str, Depends(get_current_user)],
) -> ConversationResponse:
    """
    创建会话 + 挂载初始 Agent 列表。
    single 模式期望 agent_ids 长度为 1(chat_service.\_sole_agent_id 默认取首个),
    但本端点不强制——chat_service 路由分发时会日志警告并取首个。
    """
    conv = await conversation_service.create(
        user_id=user_id,
        title=request.title,
        mode=request.mode.value,
        agent_ids=request.agent_ids,
    )
    return await _to_conversation_response(conv)


# ============================================================
# GET /api/v1/conversations —— 我的会话列表
# ============================================================

@router.get(
    "/conversations",
    response_model=list[ConversationListItem],
    summary="我的会话列表(置顶 + 最近活跃排序)",
)
async def list_conversations(
    user_id: Annotated[str, Depends(get_current_user)],
    include_archived: Annotated[
        bool,
        Query(description="是否包含已归档会话"),
    ] = False,
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="每页返回数量，默认 20"),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, le=10000, description="分页偏移量"),
    ] = 0,
) -> list[ConversationListItem]:
    """列出当前 user 的所有会话。仅显示自己的(service 内置 user_id 过滤)。"""
    convs = await conversation_service.list_for_user(
        user_id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return [ConversationListItem.model_validate(c) for c in convs]


# ============================================================
# GET /api/v1/conversations/{id} —— 详情
# ============================================================

@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="会话详情(含成员列表)",
)
async def get_conversation(
    conversation_id: Annotated[str, Path(description="会话 ID")],
    user_id: Annotated[str, Depends(get_current_user)],
) -> ConversationResponse:
    conv = await conversation_service.assert_owned_by(conversation_id, user_id)
    return await _to_conversation_response(conv)


# ============================================================
# PATCH /api/v1/conversations/{id} —— 重命名 / 置顶 / 归档
# ============================================================

@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="编辑会话元信息(重命名 / 置顶 / 归档)",
)
async def update_conversation(
    conversation_id: Annotated[str, Path(description="会话 ID")],
    update: ConversationUpdate,
    user_id: Annotated[str, Depends(get_current_user)],
) -> ConversationResponse:
    """每次只更新传入的非 None 字段。三个动作走对应的 service 方法。"""
    await conversation_service.assert_owned_by(conversation_id, user_id)

    if update.title is not None:
        await conversation_service.rename(conversation_id, update.title)
    if update.is_pinned is not None:
        await conversation_service.set_pinned(conversation_id, update.is_pinned)
    if update.is_archived is not None:
        await conversation_service.set_archived(conversation_id, update.is_archived)

    refreshed = await conversation_service.get(conversation_id)
    return await _to_conversation_response(refreshed)


# ============================================================
# GET /api/v1/conversations/{id}/messages —— 历史消息分页
# ============================================================

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="会话历史消息(倒序 + 游标分页)",
    description=(
        "返回最近 N 条消息,按 created_at 倒序(最新在前)。"
        "前端按时间线展示需要 reversed()。"
        "before:游标分页,传消息 id 表示只要该消息**之前**的;"
        "首次请求不传,后续把当前列表最旧一条的 id 作为 before 翻下一页。"
    ),
)
async def list_conversation_messages(
    conversation_id: Annotated[str, Path(description="会话 ID")],
    user_id: Annotated[str, Depends(get_current_user)],
    limit: Annotated[
        int,
        Query(ge=1, le=200, description="单次返回上限,默认 20"),
    ] = 20,
    before: Annotated[
        Optional[str],
        Query(description="游标:消息 id,只返回 created_at 早于该消息的记录"),
    ] = None,
) -> list[MessageResponse]:
    await conversation_service.assert_owned_by(conversation_id, user_id)

    try:
        messages = await message_service.list_recent(
            conversation_id,
            limit=limit,
            before=before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [_message_orm_to_response(m) for m in messages]


# ============================================================
# 内部辅助:Message ORM → MessageResponse
# ============================================================

def _message_orm_to_response(msg) -> MessageResponse:
    """
    把 ORM Message 转成 MessageResponse。
    重点处理 content 字段:DB 存的是 list[dict](JSON),Pydantic 需要 list[ContentBlock]。
    MessageResponse 的 blocks 字段会自动反序列化(ContentBlock 是 discriminated union)。
    """
    return MessageResponse.model_validate({
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "thread_id": msg.thread_id,
        "parent_id": msg.parent_id,
        "user_id": msg.user_id,
        "agent_id": msg.agent_id,
        "role": msg.role,
        "blocks": msg.content or [],  # DB 字段叫 content,API 字段叫 blocks
        "status": msg.status,
        "error_message": msg.error_message,
        "model": msg.model,
        "sender": msg.sender,
        "tokens_input": msg.tokens_input,
        "tokens_output": msg.tokens_output,
        "latency_ms": msg.latency_ms,
        "feedback": msg.feedback,
        "selected_range": msg.selected_range,
        "is_deleted": bool(msg.is_deleted),
        "created_at": msg.created_at,
    })
