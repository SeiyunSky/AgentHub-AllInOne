"""
ThreadService —— Thread 生命周期 + 任务图调度 + 子 Thread 事件回注

职责:
- 创建 Thread / 状态机迁移 / checkpoint 持久化
- 任务图调度:blocked_by 解锁 → 启动对应 Adapter
- 子 Thread done/error 时,把摘要事件写入主 Agent 的 pending_events 队列
- 主 Agent loop 通过 register_event_listener 注册回调,Thread 完成时被唤醒

并发模型:
- 单进程内 asyncio,事件触发驱动调度(不轮询)
- pending_events 用 dict[parent_thread_id, list[Event]] 存内存
- 上线时切 Redis 即可,接口不变

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Optional

from sqlalchemy.orm import Session

from backend.adapters.base import StreamInput
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    BlockStartEvent,
)
from backend.models.thread import Thread
from backend.repositories.thread_repo import ThreadRepository
from backend.schemas.thread import (
    TaskPlan,
    ThreadCheckpoint,
    ThreadStatus,
)
from backend.services.stream_service import stream_service


# TODO[D5]: 等无履生 adapters/registry.py 实装后,删掉 try 块直接 import registry
try:
    from backend.adapters.registry import registry as adapter_registry  # type: ignore
except ImportError:
    adapter_registry = None  # 占位:_start_thread 调用时显式报错


logger = logging.getLogger(__name__)


# ============================================================
# 类型别名
# ============================================================

# 主 Agent loop 注册的"子 Thread 事件"回调
# 入参:子 thread_id + 事件摘要文本 + 是否成功
ThreadEventListener = Callable[[str, str, bool], Awaitable[None]]


# ============================================================
# 模块级全局调度状态
# ============================================================
# 这三个是**进程内全局共享**状态(不是 ThreadService 实例属性):
# - 多个 ThreadService 实例(每个 HTTP 请求一个)共用同一份调度数据
# - 单进程内 asyncio 调度,通过事件循环串行,无锁竞争
# - 多进程部署时需要换成 Redis,接口不变
# 显式放模块级避免误读为"实例状态"。

_listeners: dict[str, ThreadEventListener] = {}
_pending_events: dict[str, list[str]] = defaultdict(list)
_running_tasks: dict[str, asyncio.Task] = {}


# ============================================================
# ThreadService
# ============================================================

class ThreadService:
    """业务编排层。session 由调用方注入,commit 由调用方控制。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = ThreadRepository(session)

    # --------------------------------------------------------
    # 创建
    # --------------------------------------------------------

    def create_thread(
        self,
        *,
        conversation_id: str,
        message_id: str,
        agent_id: str,
        blocked_by: Optional[list[str]] = None,
        dispatch_prompt: Optional[str] = None,
    ) -> Thread:
        """创建一行 Thread(状态 init)。"""
        return self.repo.create_thread(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            blocked_by=blocked_by or [],
            dispatch_prompt=dispatch_prompt,
        )

    def create_task_plan(
        self,
        plan: TaskPlan,
        *,
        conversation_id: str,
        message_id: str,
    ) -> list[Thread]:
        """
        把 TaskPlan 落地为 N 行 Thread。
        TaskPlanItem.id 作为 thread_id 直接使用(主 Agent 提前生成,blocked_by 引用稳定)。
        """
        threads: list[Thread] = []
        for item in plan.tasks:
            thread = self.repo.create_thread(
                id=item.id,
                conversation_id=conversation_id,
                message_id=message_id,
                agent_id=item.agent_id,
                blocked_by=item.blocked_by,
                dispatch_prompt=item.prompt,
            )
            threads.append(thread)
        return threads

    def add_task(
        self,
        *,
        conversation_id: str,
        message_id: str,
        agent_id: str,
        blocked_by: Optional[list[str]] = None,
        dispatch_prompt: Optional[str] = None,
    ) -> Thread:
        """运行中追加任务节点(create_thread 的别名,语义清晰)。"""
        return self.create_thread(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            blocked_by=blocked_by,
            dispatch_prompt=dispatch_prompt,
        )

    def remove_task(self, thread_id: str) -> bool:
        """运行中移除尚未启动的任务。仅支持 status=init,其他状态返回 False。"""
        thread = self.repo.get(thread_id)
        if thread is None or thread.status != ThreadStatus.INIT.value:
            return False
        return self.repo.delete(thread_id)

    def resume_or_create(
        self,
        *,
        conversation_id: str,
        agent_id: str,
        message_id: str,
        reuse_terminal: bool = False,
    ) -> Thread:
        """
        @个体特化:有可复用的 Thread 则返回,否则新建。
        组合 repo.find_latest_by_agent + create_thread,upsert 决策在 service 层。
        """
        latest = self.repo.find_latest_by_agent(conversation_id, agent_id)
        if latest is not None:
            terminal = {
                ThreadStatus.DONE.value,
                ThreadStatus.ERROR.value,
                ThreadStatus.CANCELLED.value,
            }
            if reuse_terminal or latest.status not in terminal:
                return latest
        return self.create_thread(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
        )

    # --------------------------------------------------------
    # 状态机迁移(写库 + 触发调度 / 唤醒)
    # --------------------------------------------------------

    async def mark_running(self, thread_id: str) -> Optional[Thread]:
        return self.repo.mark_status(thread_id, ThreadStatus.RUNNING)

    async def mark_done(
        self,
        thread_id: str,
        result_summary: str = "",
    ) -> Optional[Thread]:
        """子 Thread 完成,写库 + 触发下游解锁 + 唤醒父 Agent。"""
        thread = self.repo.mark_status(thread_id, ThreadStatus.DONE)
        if thread is None:
            return None
        await self._on_thread_terminal(thread, result_summary or "(无摘要)", success=True)
        return thread

    async def mark_error(
        self,
        thread_id: str,
        error_message: str,
    ) -> Optional[Thread]:
        thread = self.repo.mark_status(
            thread_id,
            ThreadStatus.ERROR,
            error_message=error_message,
        )
        if thread is None:
            return None
        await self._on_thread_terminal(
            thread,
            f"Thread {thread_id} 失败: {error_message}",
            success=False,
        )
        return thread

    async def mark_cancelled(self, thread_id: str) -> Optional[Thread]:
        thread = self.repo.mark_status(thread_id, ThreadStatus.CANCELLED)
        if thread is None:
            return None
        # 取消时也唤醒父 Agent,让它知道任务被砍了
        await self._on_thread_terminal(
            thread,
            f"Thread {thread_id} 已取消",
            success=False,
        )
        return thread

    async def mark_suspended(self, thread_id: str) -> Optional[Thread]:
        return self.repo.mark_status(thread_id, ThreadStatus.SUSPENDED)

    async def resume_from_suspended(self, thread_id: str) -> Optional[Thread]:
        """审批通过后从 suspended 恢复执行。"""
        thread = self.repo.get(thread_id)
        if thread is None or thread.status != ThreadStatus.SUSPENDED.value:
            return None
        # 重新启动该 Thread(异步)
        self._launch_thread_task(thread)
        return thread

    # --------------------------------------------------------
    # checkpoint
    # --------------------------------------------------------

    def save_checkpoint(
        self,
        thread_id: str,
        checkpoint: ThreadCheckpoint,
    ) -> Optional[Thread]:
        return self.repo.save_checkpoint(thread_id, checkpoint)

    def load_checkpoint(self, thread_id: str) -> Optional[ThreadCheckpoint]:
        return self.repo.load_checkpoint(thread_id)

    # --------------------------------------------------------
    # 调度
    # --------------------------------------------------------

    async def schedule_conversation(self, conversation_id: str) -> list[Thread]:
        """
        扫该会话所有 init Thread,blocked_by 满足的启动。
        每次 Thread 状态变化时调用一次。
        返回本次启动的 Thread 列表。
        """
        threads = self.repo.list_active_in_conversation(conversation_id)
        started: list[Thread] = []
        for thread in threads:
            if thread.status != ThreadStatus.INIT.value:
                continue
            if not self.repo.all_blockers_done(thread):
                continue
            if thread.id in _running_tasks:
                continue
            self._launch_thread_task(thread)
            started.append(thread)
        return started

    async def cancel_thread(self, thread_id: str) -> Optional[Thread]:
        """主动取消单个 Thread。"""
        task = _running_tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()
        return await self.mark_cancelled(thread_id)

    async def cancel_all_in_conversation(self, conversation_id: str) -> list[Thread]:
        """流式中止 / 队列抢占:取消该会话所有未结束 Thread。"""
        threads = self.repo.list_active_in_conversation(conversation_id)
        cancelled: list[Thread] = []
        for thread in threads:
            result = await self.cancel_thread(thread.id)
            if result is not None:
                cancelled.append(result)
        return cancelled

    async def cancel_dependents(
        self,
        thread_id: str,
        _visited: Optional[set[str]] = None,
    ) -> list[Thread]:
        """
        失败传播策略:取消所有依赖 thread_id 的下游 Thread(递归)。
        _visited 防环:DAG 校验漏过 / 数据被改坏时,避免无限递归栈溢出。
        """
        visited = _visited if _visited is not None else set()
        if thread_id in visited:
            return []
        visited.add(thread_id)

        cancelled: list[Thread] = []
        for downstream in self.repo.list_dependents_of(thread_id):
            if downstream.status in {
                ThreadStatus.DONE.value,
                ThreadStatus.ERROR.value,
                ThreadStatus.CANCELLED.value,
            }:
                continue
            if downstream.id in visited:
                continue
            result = await self.cancel_thread(downstream.id)
            if result is not None:
                cancelled.append(result)
                cancelled.extend(await self.cancel_dependents(downstream.id, visited))
        return cancelled

    # --------------------------------------------------------
    # 主 Agent 唤醒机制(操作模块级全局状态)
    # --------------------------------------------------------

    @staticmethod
    def register_event_listener(
        parent_thread_id: str,
        listener: ThreadEventListener,
    ) -> None:
        """主 Agent loop 启动时注册:子 Thread 完成时被回调唤醒。"""
        _listeners[parent_thread_id] = listener

    @staticmethod
    def unregister_event_listener(parent_thread_id: str) -> None:
        _listeners.pop(parent_thread_id, None)

    @staticmethod
    def pop_pending_events(parent_thread_id: str) -> list[str]:
        """主 Agent loop 每轮开头调:取出累积的事件摘要,清空队列。"""
        return _pending_events.pop(parent_thread_id, [])

    # --------------------------------------------------------
    # 内部:子 Thread 进入终态时的处理
    # --------------------------------------------------------

    async def _on_thread_terminal(
        self,
        thread: Thread,
        summary: str,
        *,
        success: bool,
    ) -> None:
        """
        子 Thread 进入终态(done/error/cancelled)的统一后处理:
        1. 把摘要写入父 Agent 的 pending_events 队列
        2. 调注册的 listener 唤醒父 Agent loop
        3. 触发该会话的调度(下游可能解锁)
        """
        parent_thread_id = self._find_parent_orchestrator(thread)

        if parent_thread_id is not None:
            _pending_events[parent_thread_id].append(summary)
            listener = _listeners.get(parent_thread_id)
            if listener is not None:
                try:
                    await listener(thread.id, summary, success)
                except Exception:
                    logger.exception(
                        "ThreadEventListener for %s raised on child %s",
                        parent_thread_id,
                        thread.id,
                    )

        if not success:
            await self.cancel_dependents(thread.id)
        else:
            await self.schedule_conversation(thread.conversation_id)

        _running_tasks.pop(thread.id, None)

    def _find_parent_orchestrator(self, thread: Thread) -> Optional[str]:
        """
        反查触发本 Thread 的主 Agent Thread ID。
        约定:同一 message_id 下 agent_id='orchestrator' 的 Thread 是主 Agent。
        本身就是主 Agent 时返回 None。
        """
        if thread.agent_id == "orchestrator":
            return None
        siblings = self.repo.list_by_message(thread.message_id)
        for s in siblings:
            if s.agent_id == "orchestrator" and s.id != thread.id:
                return s.id
        return None

    # --------------------------------------------------------
    # 内部:启动 Thread(异步运行 Adapter.stream)
    # --------------------------------------------------------

    def _launch_thread_task(self, thread: Thread) -> None:
        """把 Thread 启动包装为 asyncio.Task,登记到 _running_tasks。"""
        task = asyncio.create_task(self._run_thread(thread))
        _running_tasks[thread.id] = task

    async def _run_thread(self, thread: Thread) -> None:
        """
        启动单个 Thread:mark_running → 调 Adapter.stream → 处理事件 → 落终态。

        TODO[D7-blocker / 上线前必须修]:
        本方法在 asyncio.Task 里跑,跟主流程共享 self.session。SQLAlchemy Session
        不是协程安全的,并发场景会出现 session 状态错乱。
        修法:本方法内部用 SessionLocal() 起新 session,与传入 session 解耦。
        MVP 阶段单线程串行调度暂时不会触发,但上线前必须修。
        """
        if adapter_registry is None:
            raise NotImplementedError(
                "[TODO/D5] adapters/registry 未实装,无法启动 Thread。"
            )

        try:
            await self.mark_running(thread.id)
            adapter = adapter_registry.get(thread.agent_id)
            if adapter is None:
                await self.mark_error(thread.id, f"未注册的 agent_id: {thread.agent_id}")
                return

            stream_input = StreamInput(
                agent_id=thread.agent_id,
                thread_id=thread.id,
                message_id=thread.message_id,
                prompt=thread.dispatch_prompt or "",
                history=[],  # TODO[D6]: 从 message_repo 加载会话历史
                skills=[],   # TODO[D6]: 从 skill_service 按 agent_id 加载挂载 Skill
                cancel_event=stream_service.get_abort_event(thread.conversation_id),
            )

            summary_parts: list[str] = []
            errored = False

            async for event in adapter.stream(stream_input):
                # 推给前端 SSE(广播给该 conversation 所有 tab)
                await stream_service.push_event(thread.conversation_id, event)
                summary_parts.extend(self._extract_summary(event))
                if isinstance(event, AgentErrorEvent):
                    errored = True
                    await self.mark_error(thread.id, event.error)
                    return
                if isinstance(event, AgentDoneEvent):
                    break

            if not errored:
                summary = " ".join(summary_parts)[:500] or "(无摘要)"
                await self.mark_done(thread.id, summary)
        except asyncio.CancelledError:
            await self.mark_cancelled(thread.id)
            raise
        except Exception as exc:
            logger.exception("Thread %s 运行异常", thread.id)
            await self.mark_error(thread.id, str(exc))

    @staticmethod
    def _extract_summary(event: AgentEvent) -> list[str]:
        """从事件里抽摘要文本(MVP 简化:取 BlockStart 的初始内容)。"""
        if isinstance(event, BlockStartEvent):
            block = event.block
            content = getattr(block, "content", None)
            if isinstance(content, str) and content:
                return [content[:80]]
        return []
