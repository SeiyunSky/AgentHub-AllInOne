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

from backend.repositories.conversation_repo import ConversationRepository

from backend.core.database import SessionLocal
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

# broadcast 模式下，Agent 不回复时在 dispatch_prompt 里发这个 sentinel；
# Adapter 层识别后跳过 streaming，直接写 read_receipts 表 + 推 ReadReceiptEvent。
BROADCAST_NO_REPLY_SENTINEL = "__READ_RECEIPT__"


# ============================================================
# 模块级全局状态
# ============================================================
# 每个 conversation 一把 asyncio.Lock,串行化"路由 + 落库 + 派活"
# pending 队列存 round 进行中收到的新消息,当前轮 round_done 后取出处理

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_pending: dict[str, list["_PendingItem"]] = defaultdict(list)
_orchestrator_tasks: dict[str, asyncio.Task] = {}  # conversation_id → 当前主 Agent loop task

# broadcast 互聊状态：记录本轮有哪些 agent 实际回复了，以及当前轮次深度
# 结构: { conv_id: {"depth": int, "pending": int, "replies": [...]} }
_broadcast_state: dict[str, dict] = {}


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

        关键点:必须强制清掉 _locks[conv_id]。
        否则 handle_chat 那一侧的 `async with lock` 协程可能还在等
        start_loop 自然结束(start_loop 收到 cancel 后未必立即返回),
        锁不释放 → 后续 POST /chat 全部进 pending 队列等永远不会到来的 round_done
        → 会话彻底卡死。

        删除 _locks[conv_id] 让下次 handle_chat 拿到一把全新的空闲锁。
        旧的 async with 块走完后会触发 RuntimeError(release on already-released lock)
        但被 asyncio 框架吞掉,不影响业务。MVP 单进程内可接受。
        """
        # 设 stream 中止标志
        stream_service.abort(conversation_id)
        # cancel 主 Agent loop task(若有)
        orch_task = _orchestrator_tasks.pop(conversation_id, None)
        if orch_task and not orch_task.done():
            orch_task.cancel()
        # 清空排队消息(用户的"停止"语义包括"丢掉后续待处理")
        _pending.pop(conversation_id, None)
        # 真正取消 Thread
        cancelled = await self.thread_service.cancel_all_in_conversation(conversation_id)
        # 推整轮结束
        await stream_service.push_round_done(conversation_id)
        # 强制摘掉旧锁,下次 handle_chat 自动建新锁(defaultdict),保证后续消息能被处理
        _locks.pop(conversation_id, None)

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

        前置条件:调用方必须确保 _locks[conversation_id] 已释放，
        否则 async with _locks[conversation_id] 会死锁（asyncio.Lock 不可重入）。
        orchestrator_service 在 start_loop finally 块末尾调 on_round_done，
        此时 handle_chat 的 async with lock 块已经结束，锁已释放，时序安全。
        """
        while _pending.get(conversation_id):
            item = _pending[conversation_id].pop(0)
            try:
                async with _locks[conversation_id]:
                    await self._dispatch(item.request, item.user_id)
            except Exception:
                logger.exception(
                    "drain _dispatch failed for conversation=%s, skipping item",
                    conversation_id,
                )

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
        elif self._conversation_mode(conversation) == "broadcast":
            await self._broadcast_flow(request, user_msg, conversation)
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
            # 单聊绕过主 Agent,用户原话直接当子 Agent 输入
            dispatch_prompt=request.content,
        )
        # 必须 commit,否则 _launch_thread_task 起的后台 SessionLocal 看不到这条 thread
        # → mark_status 返回 None → Adapter 永远不启动
        self.session.commit()
        await self.thread_service.schedule_conversation(request.conversation_id)

    async def _individual_mention_flow(
        self,
        request,
        user_msg,
        conversation,
        agent_id: str,
    ) -> None:
        """@个体特化:resume_or_create 复用历史 Thread,启动调度。"""
        # 注:身份 / 角色 / 群聊成员等基础信息由 thread_service._build_runtime_context_header
        # 统一注入 system_prompt 顶部,这里不再重复 anchor。
        # 只保留 @ 个体特化独有的语境信号:让 Agent 知道"是用户在群里 @ 了我",
        # 而不是"主 Agent 派了个任务给我"——dispatch_prompt 是 Agent message 级语境,
        # 用前缀提示足够。
        dispatch_prompt = (
            "[用户在群聊中直接 @ 了你,这是面向你的请求]\n\n"
            + request.content
        )

        self.thread_service.resume_or_create(
            conversation_id=request.conversation_id,
            agent_id=agent_id,
            message_id=self._msg_id(user_msg),
            # @个体特化也是用户与子 Agent 直接对话,本次消息作为 dispatch_prompt;
            # 复用既有 Thread 时也要刷新,否则子 Adapter 永远拿到第一次的 prompt
            dispatch_prompt=dispatch_prompt,
        )
        # 同 _single_chat_flow:commit 让后台 Task 能看到
        self.session.commit()
        await self.thread_service.schedule_conversation(request.conversation_id)

    async def _broadcast_flow(
        self,
        request,
        user_msg,
        conversation,
    ) -> None:
        """
        broadcast 模式：把消息广播给所有挂载的 Agent，各自独立决定回不回。

        规则：
        - mention_ids 里的 Agent → dispatch_prompt 加"[你被@了，必须回复]"前缀，强制回复。
        - 其余 Agent → dispatch_prompt 加自决前缀：
            若这条消息与你无关或你不想参与，只回 BROADCAST_NO_REPLY_SENTINEL，不要说其他任何话。
          Adapter 层检测到 sentinel 后跳过 streaming，写 read_receipts + 推 ReadReceiptEvent。

        每个 Agent 各自创建独立 Thread，全部 schedule 后并行跑。
        broadcast 模式下不走 orchestrator，不做任务拆解。
        """
        conv_id = request.conversation_id
        conv_repo = ConversationRepository(self.session)
        agents = conv_repo.list_active_agents(conv_id)
        if not agents:
            logger.warning("broadcast conversation %s has no active agents", conv_id)
            return

        import random

        # 初始化本轮 broadcast 互聊状态（depth=0 表示这是用户消息触发的第 0 轮）
        _broadcast_state[conv_id] = {"depth": 0, "replies": [], "pending": len(agents)}

        forced_ids = set(request.mention_ids or [])
        msg_id = self._msg_id(user_msg)

        for agent in agents:
            if agent.id in forced_ids:
                # @ 强制回复
                prefix = "[用户在群聊中直接 @ 了你，你必须回复]\n\n"
            elif random.random() < 0.7:
                # 70% 概率：鼓励回复，但仍可自决
                prefix = (
                    f"[broadcast 消息，你可以用你的角色身份回复。"
                    f"如果回不回复都无所谓，只回 {BROADCAST_NO_REPLY_SENTINEL}，不要说其他任何话。]\n\n"
                )
            else:
                # 30% 概率：倾向已读不回
                prefix = (
                    f"[broadcast 消息，你此刻不太想开口。除非内容强烈触动你，否则只回 {BROADCAST_NO_REPLY_SENTINEL}，不要说其他任何话。]\n\n"
                )
            dispatch_prompt = prefix + request.content

            self.thread_service.resume_or_create(
                conversation_id=conv_id,
                agent_id=agent.id,
                message_id=msg_id,
                dispatch_prompt=dispatch_prompt,
            )

        self.session.commit()
        await self.thread_service.schedule_conversation_staggered(conv_id)

    async def _broadcast_agent_reply_flow(
        self,
        *,
        conversation_id: str,
        prompt: str,
        depth: int,
        selected_agents: list,
    ) -> None:
        """
        broadcast 互聊下一轮：只给 selected_agents 创建 Thread。
        selected_agents 由调用方（_maybe_trigger_broadcast_next_round）按概率筛选好传入。
        """
        if not selected_agents:
            logger.info("broadcast conv=%s depth=%d selected_agents 为空，终止互聊", conversation_id, depth)
            await stream_service.push_round_done(conversation_id)
            await _drain_pending_messages(conversation_id)
            return

        # 初始化本轮 broadcast_state，pending 只计命中的 agent 数
        _broadcast_state[conversation_id] = {"depth": depth, "replies": [], "pending": len(selected_agents)}

        from backend.core.utils import gen_uuid
        virtual_msg_id = gen_uuid()

        for agent in selected_agents:
            agent_prompt = (
                f"[broadcast 续话，你自己决定要不要回复。"
                f"如果你没有什么要说的，只回 {BROADCAST_NO_REPLY_SENTINEL}，不要说其他任何话。]\n\n"
                + prompt
            )
            self.thread_service.resume_or_create(
                conversation_id=conversation_id,
                agent_id=agent.id,
                message_id=virtual_msg_id,
                dispatch_prompt=agent_prompt,
            )

        self.session.commit()
        await self.thread_service.schedule_conversation_staggered(conversation_id)

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
        # 必须 commit,否则 start_loop 起的独立 session 查不到这条 thread,
        # mark_running / mark_done 全部 no-op,thread 永远停在 init 状态
        self.session.commit()
        # start_loop 改为后台 Task:让锁立即释放,stop 时可以 cancel
        task = asyncio.create_task(
            orchestrator_service.start_loop(  # type: ignore[union-attr]
                thread_id=orchestrator_thread.id,
                conversation_id=request.conversation_id,
                user_message_id=self._msg_id(user_msg),
                user_id=user_id,
            )
        )
        _orchestrator_tasks[request.conversation_id] = task

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

    def _sole_agent_id(self, conversation) -> str:
        conv_repo = ConversationRepository(self.session)
        agent_ids = conv_repo.list_active_agent_ids(
            getattr(conversation, "id", None) or conversation["id"]
        )
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
    本轮所有 Thread 完成后由 on_broadcast_thread_done 串行触发（broadcast 模式），
    或由 orchestrator start_loop finally 直接调（群聊主 Agent 路径）。
    1. 检查是否需要触发 broadcast 下一轮互聊
    2. 如果触发了下一轮，直接返回（SSE 保持开着）
    3. 否则推 round_done，取出排队消息
    """
    triggered = await _maybe_trigger_broadcast_next_round(conversation_id)
    if triggered:
        return
    await stream_service.push_round_done(conversation_id)
    await _drain_pending_messages(conversation_id)


def record_broadcast_reply(
    conversation_id: str,
    agent_id: str,
    agent_name: str,
    content: str,
) -> None:
    """
    thread_service 落库 broadcast 回复后调本方法，记录本轮回复信息。
    只记录 _broadcast_state 里已有的会话（由 _broadcast_flow 初始化），
    非 broadcast 模式下不写入，避免误触发。
    """
    state = _broadcast_state.get(conversation_id)
    if state is None:
        return
    state["replies"].append({"agent_id": agent_id, "agent_name": agent_name, "content": content})


async def on_broadcast_thread_done(conversation_id: str) -> None:
    """
    broadcast 模式下每个 Thread（含已读回执）完成时调本方法。
    递减本轮 pending 计数；减到 0 时串行触发 on_round_done，其余直接返回。
    非 broadcast 模式（_broadcast_state 里没有记录）直接跳过。
    """
    state = _broadcast_state.get(conversation_id)
    if state is None:
        return
    state["pending"] = state.get("pending", 1) - 1
    if state["pending"] > 0:
        return
    await on_round_done(conversation_id)


async def _maybe_trigger_broadcast_next_round(conversation_id: str) -> bool:
    """
    broadcast 互聊触发逻辑：
    - 本轮有 agent 回复（replies 非空）
    - 当前深度 < 1
    - 对每个 agent 独立做 30% 概率判定，命中的才进下一轮
    - 命中 0 个则不触发
    返回 True 表示触发了下一轮（调用方不应推 round_done），False 表示没有触发。
    """
    import random

    state = _broadcast_state.get(conversation_id)
    if not state or not state.get("replies"):
        _broadcast_state.pop(conversation_id, None)
        return False

    depth: int = state.get("depth", 0)
    if depth >= 1:
        logger.debug("broadcast conv=%s depth=%d 已达上限，不触发下一轮", conversation_id, depth)
        _broadcast_state.pop(conversation_id, None)
        return False

    replies: list[dict] = state["replies"]
    _broadcast_state.pop(conversation_id, None)

    # 对每个 agent 单独 30% 概率判定，收集命中的
    from backend.core.database import SessionLocal
    session = SessionLocal()
    try:
        from backend.repositories.conversation_repo import ConversationRepository as _ConvRepo
        all_agents = _ConvRepo(session).list_active_agents(conversation_id)
    finally:
        session.close()

    selected = [a for a in all_agents if random.random() < 0.3]
    logger.info(
        "broadcast conv=%s 互聊概率判定：%d/%d 个 agent 命中",
        conversation_id, len(selected), len(all_agents),
    )
    if not selected:
        return False

    # 组装对话摘要
    summary_lines = []
    for r in replies:
        snippet = r["content"][:200] + ("…" if len(r["content"]) > 200 else "")
        summary_lines.append(f"{r['agent_name']}: {snippet}")
    summary = "\n".join(summary_lines)
    next_prompt = f"[群聊续话，其他成员刚刚说了以下内容，你可以自然地接话或保持沉默]\n\n{summary}"

    logger.info(
        "broadcast conv=%s 触发第 %d 轮互聊，selected_agents=%s",
        conversation_id, depth + 1, [a.id for a in selected],
    )

    session = SessionLocal()
    try:
        svc = ChatService(session)
        await svc._broadcast_agent_reply_flow(
            conversation_id=conversation_id,
            prompt=next_prompt,
            depth=depth + 1,
            selected_agents=selected,
        )
        return True
    except Exception:
        logger.exception("broadcast conv=%s 第 %d 轮互聊触发失败", conversation_id, depth + 1)
        return False
    finally:
        session.close()


async def _drain_pending_messages(conversation_id: str) -> None:
    """取出该 conversation 的排队消息依次走 _dispatch。"""
    if not _pending.get(conversation_id):
        await stream_service.push_queue_drained(conversation_id)
        return

    session = SessionLocal()
    try:
        svc = ChatService(session)
        await svc._drain_pending(conversation_id)
    finally:
        session.close()
        await stream_service.push_queue_drained(conversation_id)
