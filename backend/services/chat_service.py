"""
ChatService —— /api/v1/chat 业务入口

职责:
- 路由分发(单聊 / 群聊主 Agent / @个体特化 / 局部修改)
- conversation 锁 + 排队队列(用户在 round 进行中再发消息走排队)
- 紧急中止 (POST /chat/stop)

调用链:
    HTTP API → ChatService.handle_chat → 落用户消息 → 路由 → 创建 Thread →
    schedule → 返回 Started/Queued
    SSE 端点单独从 stream_service.consume(session) 拿事件流推前端

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.core.utils import gen_uuid
from backend.domain.message import TextBlock
from backend.schemas.chat import (
    ChatQueuedResponse,
    ChatRequest,
    ChatStartedResponse,
    ChatStopResponse,
)
from backend.services.stream_service import stream_service
from backend.services.thread_service import ThreadService

# TODO[H1]: 等 message_service 实装,删 try 块直接 import
try:
    from backend.services.message_service import message_service  # type: ignore
except ImportError:
    message_service = None

# TODO[H2]: 等 conversation_service 实装,删 try 块直接 import
try:
    from backend.services.conversation_service import conversation_service  # type: ignore
except ImportError:
    conversation_service = None

# TODO[H3]: 等 prompt_service 实装,删 try 块直接 import
try:
    from backend.services.prompt_service import prompt_service  # type: ignore
except ImportError:
    prompt_service = None

# TODO[F]: orchestrator 子模块的 start_loop / agent_loop 仍是 stub,
#   调用时会抛 NotImplementedError。F 阶段完整实装后即可端到端跑通。
try:
    from backend.services.orchestrator import orchestrator_service  # type: ignore
except ImportError:
    orchestrator_service = None


logger = logging.getLogger(__name__)


ORCHESTRATOR_AGENT_ID = "orchestrator"


# ============================================================
# 模块级全局状态
# ============================================================
# 每个 conversation 一把 asyncio.Lock,串行化"路由 + 落库 + 派活"
# pending 队列存 round 进行中收到的新消息,当前轮 round_done 后取出处理

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_pending: dict[str, list["_PendingItem"]] = defaultdict(list)


@dataclass
class _PendingItem:
    request: ChatRequest
    user_id: str
    enqueued_at: datetime


# ============================================================
# ChatService
# ============================================================

class ChatService:
    """业务编排层。session 由调用方注入,commit 由调用方控制。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.thread_service = ThreadService(session)

    # --------------------------------------------------------
    # 主入口
    # --------------------------------------------------------

    async def handle_chat(
        self,
        request: ChatRequest,
        *,
        user_id: str,
    ) -> ChatStartedResponse | ChatQueuedResponse:
        """
        发消息主入口。

        流程:
        1. 检查 conversation 锁;锁被占 → 入队列返回 Queued
        2. 锁空 → acquire → 落用户消息 → 路由 → 创建 Thread → schedule
        3. 释放锁,返回 Started

        并发限制:locked() 检查与 async with lock 之间的竞态在单进程 asyncio 下
        不会触发(协程在没有 await 让出前不会切换)。多进程 / 多 worker 部署时需要
        换成 Redis 分布式锁,接口语义不变。
        """
        conv_id = request.conversation_id
        lock = _locks[conv_id]

        if lock.locked():
            return self._enqueue(request, user_id)

        async with lock:
            return await self._dispatch(request, user_id)

    async def handle_stop(self, conversation_id: str) -> ChatStopResponse:
        """
        紧急中止:取消所有未结束 Thread + 清空排队 + 推 round_done + 释放锁。
        """
        # 设 stream 中止标志
        stream_service.abort(conversation_id)
        # 清空排队消息(用户的"停止"语义包括"丢掉后续待处理")
        _pending.pop(conversation_id, None)
        # 真正取消 Thread
        cancelled = await self.thread_service.cancel_all_in_conversation(conversation_id)
        # 推整轮结束
        await stream_service.push_round_done(conversation_id)

        return ChatStopResponse(
            conversation_id=conversation_id,
            aborted=bool(cancelled),
            cancelled_thread_ids=[t.id for t in cancelled],
            timestamp=datetime.now(timezone.utc),
        )

    # --------------------------------------------------------
    # 队列入队
    # --------------------------------------------------------

    def _enqueue(
        self,
        request: ChatRequest,
        user_id: str,
    ) -> ChatQueuedResponse:
        conv_id = request.conversation_id
        item = _PendingItem(
            request=request,
            user_id=user_id,
            enqueued_at=datetime.now(timezone.utc),
        )
        _pending[conv_id].append(item)
        return ChatQueuedResponse(
            conversation_id=conv_id,
            queued_message_id=gen_uuid(),
            queue_position=len(_pending[conv_id]),
        )

    async def _drain_pending(self, conversation_id: str) -> None:
        """
        当前轮 round_done 后调:取出排队消息依次处理。
        每条消息走完整 _dispatch 流程,各自占用锁。
        全部处理完推 queue_drained 让前端关 SSE。
        """
        while _pending.get(conversation_id):
            item = _pending[conversation_id].pop(0)
            async with _locks[conversation_id]:
                await self._dispatch(item.request, item.user_id)
        await stream_service.push_queue_drained(conversation_id)

    # --------------------------------------------------------
    # 路由分发(已持锁)
    # --------------------------------------------------------

    async def _dispatch(
        self,
        request: ChatRequest,
        user_id: str,
    ) -> ChatStartedResponse:
        """已持锁状态下执行:落用户消息 → 路由 → 创建 Thread → schedule。"""
        conversation = await self._get_conversation(request.conversation_id)
        # 清除可能存在的旧 abort 标志(新一轮开始,见 stream_service.clear_abort 时序约定)
        stream_service.clear_abort(request.conversation_id)

        user_msg = await self._save_user_message(request, user_id)

        if request.selected_range is not None:
            await self._local_edit_flow(request, user_msg, conversation, user_id)
        elif self._conversation_mode(conversation) == "single":
            await self._single_chat_flow(request, user_msg, conversation)
        elif (
            self._conversation_mode(conversation) == "group"
            and len(request.mention_ids) == 1
        ):
            await self._individual_mention_flow(
                request, user_msg, conversation, request.mention_ids[0]
            )
        else:
            await self._group_orchestrate_flow(request, user_msg, conversation, user_id)

        return ChatStartedResponse(
            conversation_id=request.conversation_id,
            user_message_id=user_msg.id if hasattr(user_msg, "id") else user_msg["id"],
        )

    # --------------------------------------------------------
    # 四种流程
    # --------------------------------------------------------

    async def _single_chat_flow(self, request, user_msg, conversation) -> None:
        """单聊直通:创建 Thread 给 conversation 唯一 Agent,启动调度。"""
        agent_id = self._sole_agent_id(conversation)
        self.thread_service.create_thread(
            conversation_id=request.conversation_id,
            message_id=self._msg_id(user_msg),
            agent_id=agent_id,
        )
        await self.thread_service.schedule_conversation(request.conversation_id)

    async def _individual_mention_flow(
        self,
        request,
        user_msg,
        conversation,
        agent_id: str,
    ) -> None:
        """@个体特化:resume_or_create 复用历史 Thread,启动调度。"""
        self.thread_service.resume_or_create(
            conversation_id=request.conversation_id,
            agent_id=agent_id,
            message_id=self._msg_id(user_msg),
        )
        await self.thread_service.schedule_conversation(request.conversation_id)

    async def _group_orchestrate_flow(
        self,
        request,
        user_msg,
        conversation,
        user_id: str,
    ) -> None:
        """
        群聊全员:创建主 Agent Thread,由 orchestrator 自己决定派活。
        """
        if orchestrator_service is None:
            raise NotImplementedError("[TODO/F] orchestrator_service 未实装")

        # 主 Agent Thread,agent_id 用约定常量
        orchestrator_thread = self.thread_service.create_thread(
            conversation_id=request.conversation_id,
            message_id=self._msg_id(user_msg),
            agent_id=ORCHESTRATOR_AGENT_ID,
        )
        # 启动主 Agent loop(orchestrator_service 内部跑 agent_loop +
        # 通过 dispatch_to_agent 工具创建子 Thread)
        await orchestrator_service.start_loop(  # type: ignore[union-attr]
            thread_id=orchestrator_thread.id,
            conversation_id=request.conversation_id,
            user_message_id=self._msg_id(user_msg),
            user_id=user_id,
        )

    async def _local_edit_flow(
        self,
        request,
        user_msg,
        conversation,
        user_id: str,
    ) -> None:
        """
        对话式局部修改:加载 prompts/local_edit.md,渲染 → 走单聊或群聊主流程。
        """
        if prompt_service is None:
            raise NotImplementedError("[TODO/H3] prompt_service 未实装")

        rendered = await prompt_service.render(  # type: ignore[union-attr]
            "local_edit",
            file=request.selected_range.file,
            start=request.selected_range.start,
            end=request.selected_range.end,
            selected_code=request.selected_range.code,
            user_intent=request.content,
        )
        # 用渲染后的 prompt 替换 request.content,继续走原 mode 流程
        rebuilt = request.model_copy(update={"content": rendered, "selected_range": None})
        if self._conversation_mode(conversation) == "single":
            await self._single_chat_flow(rebuilt, user_msg, conversation)
        else:
            await self._group_orchestrate_flow(rebuilt, user_msg, conversation, user_id)

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------

    async def _save_user_message(self, request: ChatRequest, user_id: str):
        if message_service is None:
            raise NotImplementedError("[TODO/H1] message_service 未实装")
        return await message_service.create_user_message(  # type: ignore[union-attr]
            conversation_id=request.conversation_id,
            user_id=user_id,
            content_blocks=[TextBlock(block_id=gen_uuid(), content=request.content)],
            selected_range=request.selected_range,
        )

    async def _get_conversation(self, conversation_id: str):
        if conversation_service is None:
            raise NotImplementedError("[TODO/H2] conversation_service 未实装")
        return await conversation_service.get(conversation_id)  # type: ignore[union-attr]

    @staticmethod
    def _conversation_mode(conversation) -> str:
        return getattr(conversation, "mode", None) or conversation["mode"]

    @staticmethod
    def _sole_agent_id(conversation) -> str:
        agent_ids = getattr(conversation, "agent_ids", None) or conversation.get("agent_ids", [])
        if not agent_ids:
            raise ValueError("单聊 conversation 缺少挂载的 Agent")
        if len(agent_ids) > 1:
            logger.warning(
                "单聊 conversation %s 含 %d 个 Agent,取首个 %s 处理",
                getattr(conversation, "id", "<unknown>"),
                len(agent_ids),
                agent_ids[0],
            )
        return agent_ids[0]

    @staticmethod
    def _msg_id(user_msg) -> str:
        return getattr(user_msg, "id", None) or user_msg["id"]


# ============================================================
# 整轮结束回调(orchestrator_service 调本方法)
# ============================================================

async def on_round_done(conversation_id: str) -> None:
    """
    主 Agent loop 整轮结束时调:
    1. 推 round_done 给前端 SSE
    2. 取出排队消息依次处理
    3. 全部处理完推 queue_drained

    drain 阶段的 NotImplementedError(TODO[H4])会被捕获记日志,不影响整轮结束推送。
    """
    await stream_service.push_round_done(conversation_id)
    try:
        await _drain_pending_messages(conversation_id)
    except NotImplementedError as exc:
        logger.error(
            "_drain_pending_messages 未实装,排队消息暂不处理: %s",
            exc,
        )


async def _drain_pending_messages(conversation_id: str) -> None:
    """取出该 conversation 的排队消息依次走 _dispatch。"""
    # 只在有排队时才创建 service 实例,避免空跑
    if not _pending.get(conversation_id):
        await stream_service.push_queue_drained(conversation_id)
        return

    # TODO[H4]: drain 时需要 session,现在没有自动注入机制,先抛 NotImplementedError
    # 等 main.py 启动时注册 SessionLocal 工厂后接通
    raise NotImplementedError(
        "[TODO/H4] _drain_pending_messages 需要 session 工厂,"
        "等 main.py / 依赖注入接通后实装"
    )
