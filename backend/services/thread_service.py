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
修改日期:2026-05-29
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.adapters.base import StreamInput
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.models.thread import Thread
from backend.repositories.thread_repo import ThreadRepository
from backend.schemas.thread import (
    TaskPlan,
    ThreadCheckpoint,
    ThreadStatus,
)
from backend.services.stream_service import stream_service


from backend.adapters.registry import registry as adapter_registry


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
# 辅助:ORM Message → MessageInHistory(子 Adapter 历史注入用)
# ============================================================

def _orm_message_to_history(orm_msg) -> "MessageInHistory":
    """
    ORM Message 转 schemas.MessageInHistory。

    ORM Message.content 是 JSON 列(list[dict]);MessageInHistory.blocks 期望
    list[ContentBlock](Pydantic discriminated union)。用 TypeAdapter 逐块反序列化。
    单块反序列化失败时跳过该块,不让一条坏消息把整轮 history 拖死。
    """
    from pydantic import TypeAdapter
    from backend.domain.message import ContentBlock as _ContentBlockUnion
    from backend.schemas.message import MessageInHistory, MessageRole

    adapter = TypeAdapter(_ContentBlockUnion)
    blocks = []
    for raw in (orm_msg.content or []):
        try:
            blocks.append(adapter.validate_python(raw))
        except Exception:
            logger.warning(
                "history block 反序列化失败,跳过 msg=%s block=%r",
                orm_msg.id, raw,
            )

    return MessageInHistory(
        role=MessageRole(orm_msg.role),
        blocks=blocks,
        sender=orm_msg.sender,
    )


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
        dispatch_prompt: Optional[str] = None,
        reuse_terminal: bool = False,
    ) -> Thread:
        """
        @个体特化:有可复用的 Thread 则返回,否则新建。
        组合 repo.find_latest_by_agent + create_thread,upsert 决策在 service 层。

        复用既有 Thread 时,如果传入 dispatch_prompt 则覆盖原值
        (单聊 / @个体特化每轮用户输入都要变成新的 dispatch_prompt,
        否则子 Adapter 永远拿到第一次创建时的 prompt)。
        """
        latest = self.repo.find_latest_by_agent(conversation_id, agent_id)
        if latest is not None:
            terminal = {
                ThreadStatus.DONE.value,
                ThreadStatus.ERROR.value,
                ThreadStatus.CANCELLED.value,
            }
            if reuse_terminal or latest.status not in terminal:
                if dispatch_prompt is not None:
                    latest.dispatch_prompt = dispatch_prompt
                    self.session.flush()
                return latest
        return self.create_thread(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            dispatch_prompt=dispatch_prompt,
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
        4. 没有父 orchestrator + 会话再无活跃 Thread → 推 round_done(单聊 / @个体特化路径
           本身就没有主 Agent 兜底,SSE 永远等不到关闭信号,必须由最后一个完成的 Thread 触发)
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

        # ---- 单聊 / @个体特化路径的 round_done 兜底 ----
        # 本 thread 不归 orchestrator 唤醒(parent_thread_id is None)+ 自己也不是 orchestrator,
        # 说明走的是 chat_service._single_chat_flow / _individual_mention_flow 直派路径。
        # 此时若会话里再无活跃 Thread,必须主动推 round_done,否则前端 SSE 永远等不到关闭信号。
        # 群聊主 Agent 路径不走这里,start_loop finally 自己调 chat_service.on_round_done。
        if parent_thread_id is None and thread.agent_id != "orchestrator":
            if not self._has_active_threads(thread.conversation_id):
                # lazy import 防循环依赖
                from backend.services.chat_service import on_round_done
                await on_round_done(thread.conversation_id)

    def _has_active_threads(self, conversation_id: str) -> bool:
        """会话里是否还有 init/running/suspended 的 Thread。"""
        # 用本 service 的 self.session;调用方是 _run_thread,该 session 是后台 Task 自起的
        self.session.expire_all()
        active = self.repo.list_active_in_conversation(conversation_id)
        return any(
            t.status in {
                ThreadStatus.INIT.value,
                ThreadStatus.RUNNING.value,
                ThreadStatus.SUSPENDED.value,
            }
            for t in active
        )

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

        自起独立 SessionLocal，与调用方的 self.session 完全解耦，避免 asyncio.Task
        并发场景下 Session 状态错乱（D7-blocker 已修）。
        """
        from backend.core.database import SessionLocal
        from backend.repositories.agent_repo import AgentRepository
        from backend.repositories.message_repo import MessageRepository
        from backend.repositories.thread_repo import ThreadRepository

        if adapter_registry is None:
            raise NotImplementedError(
                "[TODO/D5] adapters/registry 未实装,无法启动 Thread。"
            )

        own_session = SessionLocal()
        own_repo = ThreadRepository(own_session)

        def _mark(status: ThreadStatus, **kw) -> Optional[Thread]:
            t = own_repo.mark_status(thread.id, status, **kw)
            own_session.commit()
            return t

        try:
            _mark(ThreadStatus.RUNNING)

            adapter = adapter_registry.get(thread.agent_id)
            if adapter is None:
                t = _mark(ThreadStatus.ERROR, error_message=f"未注册的 agent_id: {thread.agent_id}")
                if t:
                    await self._on_thread_terminal(t, f"Thread {thread.id} 失败: 未注册的 agent_id", success=False)
                return

            # 从 DB 读取 agent.system_prompt，注入到 StreamInput
            agent_row = AgentRepository(own_session).get(thread.agent_id)
            agent_system_prompt: Optional[str] = agent_row.system_prompt if agent_row else None
            msg_repo = MessageRepository(own_session)
            raw_history = msg_repo.list_recent(thread.conversation_id, limit=20)
            # repo 返回倒序(最新在前),反转为正序送给 Adapter
            # ORM Message 没有 .blocks 字段(只有 .content JSON 列),
            # Adapter 期望的是 MessageInHistory schema,这里做转换
            history = [
                _orm_message_to_history(m)
                for m in reversed(raw_history)
            ]

            try:
                from backend.services.skill_service import SkillService
                agent_skills = SkillService(own_session).list_with_content_for_agent(thread.agent_id)
            except Exception:
                logger.exception(
                    "Thread %s 加载 agent_skills 失败，以空列表继续（Skill 功能不可用）",
                    thread.id,
                )
                agent_skills = []

            stream_input = StreamInput(
                agent_id=thread.agent_id,
                agent_name=agent_row.name if agent_row else thread.agent_id,
                thread_id=thread.id,
                message_id=thread.message_id,
                prompt=thread.dispatch_prompt or "",
                history=history,
                skills=agent_skills,
                system_prompt=agent_system_prompt,
                cancel_event=stream_service.get_abort_event(thread.conversation_id),
            )

            summary_parts: list[str] = []
            # block 累积状态:block_id -> 块字段 dict
            # BlockStart 时初始化(用 block.model_dump() 拿到完整字段),
            # BlockDelta 时按字段语义合并(content 累加 / 其他覆盖),
            # BlockStop 时用 final_fields 覆盖,
            # AgentDone 时按插入顺序反序列化成 ContentBlock 列表落 messages 表。
            block_states: dict[str, dict[str, Any]] = {}
            block_order: list[str] = []

            async for event in adapter.stream(stream_input):
                await stream_service.push_event(thread.conversation_id, event)
                summary_parts.extend(self._extract_summary(event))

                if isinstance(event, BlockStartEvent):
                    block_id = event.block.block_id
                    if block_id not in block_states:
                        block_order.append(block_id)
                    block_states[block_id] = event.block.model_dump()
                elif isinstance(event, BlockDeltaEvent):
                    state = block_states.get(event.block_id)
                    if state is not None:
                        self._apply_block_delta(state, event.delta or {})
                elif isinstance(event, BlockStopEvent):
                    state = block_states.get(event.block_id)
                    if state is not None and event.final_fields:
                        state.update(event.final_fields)

                if isinstance(event, AgentErrorEvent):
                    t = _mark(ThreadStatus.ERROR, error_message=event.error)
                    if t:
                        await self._on_thread_terminal(
                            t, f"Thread {thread.id} 失败: {event.error}", success=False
                        )
                    return
                if isinstance(event, AgentDoneEvent):
                    # 子 Thread 单轮 LLM 完成:把 Adapter 上报的 usage 累加到 threads.tokens_total。
                    # Adapter 未上报 usage 时(默认 0+0)跳过写库,避免无 delta 的事务。
                    # update_tokens 是累加语义,主 Agent 也用同一个方法,语义一致。
                    #
                    # 失败处理:token 累加是审计 / 计费用,不影响 Thread 主链路。
                    # 写库异常时只记日志 + rollback,**不**抛出,break 后正常走 mark_done。
                    # 后续维护时请保留这段 try/except,不要简化掉(否则一次 token 写库失败会
                    # 把整个 Thread 推到 ERROR 状态,与设计意图不符)。
                    delta = (event.tokens_input or 0) + (event.tokens_output or 0)
                    if delta > 0:
                        try:
                            own_repo.update_tokens(thread.id, delta)
                            own_session.commit()
                        except Exception:
                            logger.exception(
                                "Thread %s 累加 token 失败,delta=%d (不影响 Thread 状态)",
                                thread.id,
                                delta,
                            )
                            own_session.rollback()

                    # 把累积的 block_states 落成一条 assistant 消息(role=assistant,
                    # thread_id=本 thread,agent_id=本 agent),让主 Agent 通过
                    # read_thread_result 工具能读到子 Thread 的完整产出。
                    # 失败兜底:落库失败不阻塞主链路,只丢摘要回注那条路(摘要在
                    # _on_thread_terminal 里走,不受这里影响)。
                    logger.info(
                        "Thread %s AgentDone 收到,准备落 messages: block_count=%d, "
                        "block_order=%s, tokens=%d/%d",
                        thread.id, len(block_order), block_order,
                        event.tokens_input or 0, event.tokens_output or 0,
                    )
                    # adapter.stream 跑期间 own_session 上累积了未提交的只读事务
                    # (AgentRepository.get / list_recent / SkillService 等),
                    # 在调 _persist_assistant_message(内部起独立 SessionLocal 写 messages
                    # + conversations.last_message_at)之前必须先把这个长事务关掉,
                    # 否则 MVCC 快照锁 / 行锁会和写入者抢同一行,造成 MySQL 端等锁挂死。
                    own_session.rollback()
                    await self._persist_assistant_message(
                        thread=thread,
                        agent_row=agent_row,
                        block_order=block_order,
                        block_states=block_states,
                        tokens_input=event.tokens_input or 0,
                        tokens_output=event.tokens_output or 0,
                    )
                    break

            summary = " ".join(summary_parts)[:500] or "(无摘要)"
            t = _mark(ThreadStatus.DONE)
            if t:
                await self._on_thread_terminal(t, summary, success=True)

        except asyncio.CancelledError:
            own_session.rollback()
            t = _mark(ThreadStatus.CANCELLED)
            if t:
                await self._on_thread_terminal(t, f"Thread {thread.id} 已取消", success=False)
            raise
        except Exception as exc:
            logger.exception("Thread %s 运行异常", thread.id)
            try:
                own_session.rollback()
                t = _mark(ThreadStatus.ERROR, error_message=str(exc))
                if t:
                    await self._on_thread_terminal(t, f"Thread {thread.id} 失败: {exc}", success=False)
            except Exception:
                logger.exception("Thread %s 落错误态失败", thread.id)
        finally:
            own_session.close()

    @staticmethod
    def _apply_block_delta(state: dict[str, Any], delta: dict[str, Any]) -> None:
        """
        对累积的块 state 应用一次 BlockDelta。

        Anthropic / ClaudeAdapter 风格的"流式增量"协议:
        - content 字段 → 把 delta 里的字符串拼到 state 原字符串后(累加)
        - 其他字段 → delta 里的值直接覆盖 state(状态切换 / 字段补全)
        """
        for key, value in delta.items():
            if key == "content" and isinstance(value, str) and isinstance(state.get(key), str):
                state[key] = state[key] + value
            else:
                state[key] = value

    async def _persist_assistant_message(
        self,
        *,
        thread: Thread,
        agent_row: Optional[Any],
        block_order: list[str],
        block_states: dict[str, dict[str, Any]],
        tokens_input: int,
        tokens_output: int,
    ) -> None:
        """
        把 Adapter 流转累积出的 block_states 落成一条 assistant 消息。

        - role=assistant / thread_id=本 thread / agent_id=本 agent
        - content 是 ContentBlock 数组,通过 Pydantic discriminated union 反序列化保证字段合法
        - sender / model 取 agent 表快照,Agent 改名 / 升级模型后历史消息仍展示当时数据
        - tokens_input / tokens_output 走 message_service.update_message_tokens 写到 messages 表
          (Task #7 的 TODO[H1] 收尾:子 Thread 的 token 之前只累加到 threads.tokens_total)

        失败处理:落库 / token 写入异常都只记日志,不抛出 —— 不阻塞 Thread 进 done。
        """
        from pydantic import TypeAdapter

        from backend.domain.message import ContentBlock as _ContentBlockUnion
        from backend.services.message_service import message_service

        if not block_order:
            # 没有任何块产生(比如 Adapter 直接 yield AgentDone),不落空消息
            return

        # 反序列化:用 ContentBlock discriminated union 的 TypeAdapter 把 dict 转成
        # 具体子类(TextBlock / ToolUseBlock / ...),保证写库内容合法
        adapter = TypeAdapter(_ContentBlockUnion)
        blocks: list[Any] = []
        for block_id in block_order:
            state = block_states.get(block_id)
            if not state:
                continue
            try:
                blocks.append(adapter.validate_python(state))
            except Exception:
                logger.exception(
                    "Thread %s block %s 反序列化失败,跳过该块 state=%r",
                    thread.id, block_id, state,
                )

        if not blocks:
            logger.warning(
                "Thread %s 所有 block 反序列化都失败,不落消息(原始 block 数=%d)",
                thread.id, len(block_order),
            )
            return

        sender = getattr(agent_row, "name", None) if agent_row else None
        model = None  # TODO[F-msg-model]: agents 表加 model 字段后,这里取 agent_row.model 快照

        try:
            msg = await message_service.create_assistant_message(
                conversation_id=thread.conversation_id,
                agent_id=thread.agent_id,
                content_blocks=blocks,
                thread_id=thread.id,
                sender=sender,
                model=model,
            )
        except Exception:
            logger.exception(
                "Thread %s 落 assistant 消息失败,read_thread_result 将查不到产出",
                thread.id,
            )
            return

        # 子 Thread 的 token 同时写到 messages 表(Task #7 TODO[H1] 收尾)
        if (tokens_input or tokens_output) and msg is not None:
            try:
                await message_service.update_tokens(
                    msg.id,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                )
            except Exception:
                logger.exception(
                    "Thread %s message %s 写 token 失败 (in=%d out=%d)",
                    thread.id, msg.id, tokens_input, tokens_output,
                )

    @staticmethod
    def _extract_summary(event: AgentEvent) -> list[str]:
        """
        从事件里抽摘要文本。

        协议:Adapter 走块级流式协议(见 adapters/events.py):
        - BlockStartEvent  创建块,初始 content 可能为空(Anthropic / ClaudeAdapter 风格)
                           或一次性给完整文本(简化的 Adapter)
        - BlockDeltaEvent  对该块 content 字段做增量累加
        - BlockStopEvent   块结束

        所以摘要要同时收两类事件:
        - BlockStart 的 content(非空时直接取)
        - BlockDelta.delta['content'](逐片段累加;_run_thread 把 list 里所有片段
          ' '.join 后再 [:500] 截断,所以单 delta 取 80 字符已经够)
        """
        if isinstance(event, BlockStartEvent):
            block = event.block
            content = getattr(block, "content", None)
            if isinstance(content, str) and content:
                return [content[:80]]
        elif isinstance(event, BlockDeltaEvent):
            delta = event.delta or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                return [content[:80]]
        return []
