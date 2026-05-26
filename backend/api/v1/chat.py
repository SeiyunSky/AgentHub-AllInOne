"""
api/v1/chat.py —— Chat 业务 HTTP 端点

三个端点:
- POST /api/v1/chat            发消息(同步入口),返回 Started / Queued
- POST /api/v1/chat/stop       紧急中止当前轮
- GET  /api/v1/chat/stream/{conversation_id}  SSE 内容流(独立连接)

鉴权(MVP):全部走 X-User-Id header,见 api/deps.py:get_current_user。
[TODO/auth]: SSE 端点的浏览器兼容性问题
- 浏览器原生 EventSource API 不支持自定义 header(只能传 cookie / URL query)
- 前端要么用 polyfill(如 event-source-polyfill 支持 header)
- 要么本端点扩展支持 ?user_id= query 参数兜底
- 解法归前端 / 公共鉴权方案,本端点 MVP 阶段保持 X-User-Id 与其他端点一致

权限校验(MVP 留 TODO):
- handle_stop / stream 端点理论上应该校验 conversation_id 属于 user_id
- 防止 A 用户中止 / 偷看 B 用户的会话
- MVP 阶段先信任传入的 user_id,等 conversation_service 加权限校验方法后接通

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_chat_service, get_current_user
from backend.schemas.chat import (
    ChatQueuedResponse,
    ChatRequest,
    ChatResponse,
    ChatStartedResponse,
    ChatStopRequest,
    ChatStopResponse,
)
from backend.services.chat_service import ChatService
from backend.services.stream_service import (
    QueueDrainedEvent,
    StreamSession,
    stream_service,
)


logger = logging.getLogger(__name__)


router = APIRouter()


# ============================================================
# POST /api/v1/chat —— 发消息
# ============================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="发消息(触发主 Agent loop / 单聊 / @个体特化 / 局部修改)",
    description=(
        "同步入口,只负责落用户消息 + 启动后端处理。"
        "实际 Agent 输出走 SSE 端点 GET /api/v1/chat/stream/{conv_id}。"
        "前端应在发本请求**之前**就建立 SSE 连接,避免错过开头事件。"
    ),
)
async def post_chat(
    request: ChatRequest,
    chat: Annotated[ChatService, Depends(get_chat_service)],
    user_id: Annotated[str, Depends(get_current_user)],
) -> ChatStartedResponse | ChatQueuedResponse:
    """
    路由分发由 ChatService.handle_chat 决定:
    - 锁被占 → ChatQueuedResponse(消息排队)
    - 锁空闲 → 落消息 + 启动调度 → ChatStartedResponse
    """
    return await chat.handle_chat(request, user_id=user_id)


# ============================================================
# POST /api/v1/chat/stop —— 紧急中止
# ============================================================

@router.post(
    "/chat/stop",
    response_model=ChatStopResponse,
    summary="紧急中止当前轮 + 清空排队",
    description="用户点'停止'按钮调用,立即取消所有 Thread,推 round_done,释放锁。",
)
async def post_chat_stop(
    request: ChatStopRequest,
    chat: Annotated[ChatService, Depends(get_chat_service)],
    user_id: Annotated[str, Depends(get_current_user)],
) -> ChatStopResponse:
    """
    [TODO/perm]: MVP 跳过 conversation 归属校验,后续 conversation_service.assert_owned_by(conv_id, user_id)
    实装后接通,防止跨用户中止。
    """
    return await chat.handle_stop(request.conversation_id)


# ============================================================
# GET /api/v1/chat/stream/{conversation_id} —— SSE 内容流
# ============================================================

@router.get(
    "/chat/stream/{conversation_id}",
    summary="订阅会话 SSE 内容流(块级流式协议)",
    description=(
        "SSE 长连接,持续推送 AgentEvent / RoundDoneEvent / QueueDrainedEvent。"
        "QueueDrainedEvent 后服务端主动关闭连接,客户端可断开。"
        "前端应在 POST /chat 之前就建立连接。"
    ),
)
async def get_chat_stream(
    conversation_id: Annotated[str, Path(description="目标会话 ID")],
    user_id: Annotated[str, Depends(get_current_user)],
):
    """
    SSE 端点。流程:
    1. stream_service.open(conv_id) 拿一个 StreamSession(注册到广播表)
    2. async for event in consume(session):
         yield {"event": event.type, "data": event.model_dump_json()}
       —— sse_starlette 自动包成 SSE 协议 (data: ...\n\n)
    3. 收到 QueueDrainedEvent 后停止 yield(也即关 SSE)
    4. finally:stream_service.close(session) 清理广播注册

    [TODO/perm]: 同上,缺 conversation 归属校验。
    """
    if not conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id 不能为空",
        )

    session = stream_service.open(conversation_id)
    logger.debug(
        "SSE session %s opened for conversation %s by user %s",
        session.session_id,
        conversation_id,
        user_id,
    )

    async def event_generator() -> AsyncIterator[dict]:
        try:
            async for event in stream_service.consume(session):
                # sse_starlette 接受 dict 形态:{"event": <type>, "data": <str>}
                # event_type 默认走 SSE 协议的 'event:' 字段(可选,但前端按 type 分流方便)
                # data 里塞 model_dump_json 的字符串,前端 JSON.parse 后拿到完整 event 对象
                yield {
                    "event": event.type,
                    "data": event.model_dump_json(),
                }
                # QueueDrainedEvent 是会话结束信号,推完即关连接
                if isinstance(event, QueueDrainedEvent):
                    break
        finally:
            stream_service.close(session)
            logger.debug(
                "SSE session %s closed for conversation %s",
                session.session_id,
                conversation_id,
            )

    return EventSourceResponse(event_generator())
