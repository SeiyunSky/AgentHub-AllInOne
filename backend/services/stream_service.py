"""
StreamService —— SSE 多路合并 + 广播

职责:
- 维护每个 conversation 的活跃 SSE 连接(可多个,支持多 tab 观察)
- thread_service / Adapter 推 AgentEvent 时,广播给该 conversation 的所有连接
- API 层(SSE 端点)从单个 session 异步消费,转 SSE 字节流
- abort 是会话级,Thread 真取消后所有连接自然收到 round_done

并发模型:
- 单进程内 asyncio,事件循环串行
- _sessions 用模块级全局状态,多 ThreadService / chat_service 实例共享
- 多进程部署时换 Redis Pub/Sub,接口不变

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Union

from backend.adapters.events import (
    AgentEvent,
    MessageAppendedEvent,
    QueueDrainedEvent,
    ReadReceiptEvent,
    RoundDoneEvent,
)
from backend.core.utils import gen_uuid


logger = logging.getLogger(__name__)


# stream_service 推到队列里的事件类型(Adapter 块流 + 全局信号)
StreamEvent = Union[AgentEvent, RoundDoneEvent, QueueDrainedEvent, MessageAppendedEvent, ReadReceiptEvent]


# 内部 sentinel:close 时往 queue 推这个,通知消费端正常退出循环
class _SessionClosed:
    pass


_SESSION_CLOSED = _SessionClosed()


# ============================================================
# 会话连接
# ============================================================

@dataclass
class StreamSession:
    """单个 SSE 连接的状态。"""
    session_id: str
    conversation_id: str
    queue: "asyncio.Queue" = field(
        default_factory=lambda: asyncio.Queue(maxsize=1024)
    )


# ============================================================
# 模块级全局状态
# ============================================================
# - _sessions:某 conversation 当前活跃的所有 SSE 连接(支持多 tab)
# - _abort_events:会话级中止信号,任意 tab 点停止后所有 producer 检查
# 多进程部署时换 Redis Pub/Sub + 分布式锁,接口不变。

_sessions: dict[str, list[StreamSession]] = defaultdict(list)
_abort_events: dict[str, asyncio.Event] = {}


# ============================================================
# StreamService
# ============================================================

class StreamService:
    """无状态 facade,所有方法操作模块级全局状态。"""

    # --------------------------------------------------------
    # 连接生命周期
    # --------------------------------------------------------

    def open(self, conversation_id: str) -> StreamSession:
        """
        新建一条 SSE 连接,登记到 conversation 的连接列表。
        API 端点收到 SSE 请求时调用。
        """
        session = StreamSession(
            session_id=gen_uuid(),
            conversation_id=conversation_id,
        )
        _sessions[conversation_id].append(session)
        return session

    def close(self, session: StreamSession) -> None:
        """
        关闭一条 SSE 连接(按对象引用移除)。
        API 端点 finally 块调用,确保关 tab 后清理。

        会往 session.queue 推 _SESSION_CLOSED sentinel,让正在 await queue.get()
        的消费端能正常退出循环(否则会孤儿挂起)。
        """
        sessions = _sessions.get(session.conversation_id, [])
        try:
            sessions.remove(session)
        except ValueError:
            return
        if not sessions:
            _sessions.pop(session.conversation_id, None)

        # 通知消费端退出
        try:
            session.queue.put_nowait(_SESSION_CLOSED)
        except asyncio.QueueFull:
            # 队列满,清空再推(确保 sentinel 一定能放进去)
            try:
                while True:
                    session.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            session.queue.put_nowait(_SESSION_CLOSED)

    def list_sessions(self, conversation_id: str) -> list[StreamSession]:
        """查某 conversation 当前活跃连接(调试 / 监控用)。"""
        return list(_sessions.get(conversation_id, []))

    # --------------------------------------------------------
    # 推送
    # --------------------------------------------------------

    async def push_event(self, conversation_id: str, event: StreamEvent) -> None:
        """
        把普通 AgentEvent 广播给该 conversation 的所有 SSE 连接。
        队列满时丢该连接的事件 + warning(防止慢消费者拖死广播)。

        信号性事件(RoundDoneEvent / QueueDrainedEvent)请走 push_round_done /
        push_queue_drained,它们走"必达"路径。
        """
        sessions = _sessions.get(conversation_id, [])
        for session in sessions:
            try:
                session.queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE session %s queue full, drop event type=%s",
                    session.session_id,
                    type(event).__name__,
                )

    async def push_round_done(self, conversation_id: str) -> None:
        """
        整轮结束信号,所有 Adapter 都 done 后调。
        必达广播:队列满时清空再推(信号丢失会导致前端永远等待)。
        """
        await self._push_signal(conversation_id, RoundDoneEvent())

    async def push_queue_drained(self, conversation_id: str) -> None:
        """
        会话排队全部处理完毕,前端可关 SSE。
        必达广播策略同 push_round_done。
        """
        await self._push_signal(conversation_id, QueueDrainedEvent())

    async def _push_signal(self, conversation_id: str, event: StreamEvent) -> None:
        """信号性事件必达广播:队列满时清空再推。"""
        sessions = _sessions.get(conversation_id, [])
        for session in sessions:
            try:
                session.queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE session %s queue full on signal %s, drain & retry",
                    session.session_id,
                    type(event).__name__,
                )
                try:
                    while True:
                        session.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                session.queue.put_nowait(event)

    # --------------------------------------------------------
    # 消费(API 端点用)
    # --------------------------------------------------------

    async def consume(self, session: StreamSession) -> AsyncIterator[StreamEvent]:
        """
        异步生成器:API 端点 `async for event in stream_service.consume(session)`。
        收到 _SESSION_CLOSED sentinel 时正常退出循环,端点应在 finally 中调 close。

        本方法只读,不暴露原始 queue 防止调用方直接 put 破坏广播语义。
        """
        while True:
            event = await session.queue.get()
            if isinstance(event, _SessionClosed):
                return
            yield event

    # --------------------------------------------------------
    # 中止(会话级)
    # --------------------------------------------------------

    def abort(self, conversation_id: str) -> None:
        """
        标记会话中止。Adapter / thread_service 周期性检查 is_aborted。
        实际取消 Thread 由 chat_service 调用 thread_service.cancel_all_in_conversation,
        本方法只负责设标志位 + 通知 Adapter。
        """
        event = _abort_events.setdefault(conversation_id, asyncio.Event())
        event.set()

    def clear_abort(self, conversation_id: str) -> None:
        """
        清除中止标志(下一轮开始前调)。

        重要时序:必须在 chat_service 拿到该 conversation 的新一轮锁**之后**调,
        否则可能在旧一轮 Adapter 还在检查 abort 时被过早清除,新事件被误判。
        """
        _abort_events.pop(conversation_id, None)

    def is_aborted(self, conversation_id: str) -> bool:
        event = _abort_events.get(conversation_id)
        return event.is_set() if event else False

    def get_abort_event(self, conversation_id: str) -> asyncio.Event:
        """
        拿到 conversation 的 abort Event,Adapter 可用 await event.wait() 配合
        asyncio.wait 实现"流式跑同时监听中止"。
        """
        return _abort_events.setdefault(conversation_id, asyncio.Event())


stream_service = StreamService()
