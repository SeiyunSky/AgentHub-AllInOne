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
    MessageAppendedEvent,
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
# 辅助:运行环境 header(注入子 Agent system_prompt 顶部)
# ============================================================
#
# 所有子 Agent (单聊 / 群聊普通派活 / @个体) 都需要知道自己在 AgentHub 平台
# 运行的最基本事实:身份 / 会话 / 工作方式。这些是**事实**而不是人格,所以由后端
# 注入,不应靠每个 Agent 提示词自己声明(容易漂、容易遗漏)。
#
# 架构事实(写进 header 让 Agent 明白):
# - 子 Agent 没有任何工具权限,只输出文本
# - 真实操作(写文件 / 部署 / 改数据库)由主 Agent 调工具走 ApprovalHook
# - 单聊场景表面上"用户直接对子 Agent 说话",底层仍走主 Agent loop

def _build_runtime_context_header(
    *,
    agent_id: str,
    agent_name: str,
    agent_description: Optional[str],
    conversation_id: str,
    conversation_mode: str,           # "single" | "group" | "broadcast"
    member_lines: list[str],          # 群聊/broadcast 时的成员简介列表;单聊为空
) -> str:
    """组装注入子 Agent system_prompt 顶部的运行环境 header。"""
    role_line = f"- 角色: {agent_description}" if agent_description else ""

    members_section = ""
    if conversation_mode in ("group", "broadcast") and member_lines:
        members_section = "\n【群聊成员】\n" + "\n".join(member_lines)

    if conversation_mode == "broadcast":
        meme_map = _load_meme_map()
        meme_list = ""
        if meme_map:
            meme_lines = "\n".join(
                f"  - {mid}: {info['description'][:40]}..." if len(info['description']) > 40 else f"  - {mid}: {info['description']}"
                for mid, info in meme_map.items()
            )
            meme_list = f"""
【表情包】
你可以在回复里插入表情包，格式：[MEME:表情包ID]
可用表情包：
{meme_lines}
例：哈哈哈[MEME:pepe_laugh]这也太好笑了"""

        collab_section = f"""【协作】
这是 broadcast 闲聊模式。没有主 Agent 统筹，你直接面对用户消息，自己决定要不要回复。

回复规则：
- 消息与你相关、你有话说 → 直接用你的角色身份回复，正常输出。
- 消息与你无关、你不想参与 → 只输出以下这一行，不要加任何其他文字：
  __READ_RECEIPT__
- 若消息里有"[用户在群聊中直接 @ 了你，你必须回复]"前缀 → 必须回复，不得发已读。

已读回执的判断准则（参考，不是硬规则）：
- 这条消息是问某个特定人的问题，明显不是在问你
- 这条消息是纯任务指令，和你的角色/擅长领域毫无关系
- 你作为角色，此刻不在场或没有动机开口
只要消息有一点你能自然接上的，就正常回复。{meme_list}"""
    else:
        collab_section = """【协作】
- 单聊场景: 整个会话只有你和主 Agent,完成用户的事即可
- 群聊场景: 主 Agent 已决定派给你,专注做你擅长的部分;
  需要其他 Agent 配合时,在回答里说"还需要 X 处理 Y",主 Agent 决定是否再派"""

    return f"""=== 运行环境 ===
你在 AgentHub 平台运行,身份是子 Agent。

【你是谁】
- Agent ID: {agent_id}
- 名字: {agent_name}
{role_line}

【当前会话】
- 会话 ID: {conversation_id}
- 模式: {conversation_mode}{members_section}

【工作方式】
你是无工具的子 Agent。所有真实操作(写文件、改代码、部署等)都由主 Agent 执行。
你的产出是**文本** —— 主 Agent 读你的回答后,决定调什么工具、怎么落地、是否找用户审批。

需要文件落地时:在回答里给出完整内容(代码块,首行 filepath 注释),
主 Agent 会通过 create_file / edit_file 工具写入,触发用户审批流程。

【沙箱】
你的"工作目录"概念上是会话级沙箱: sandbox/{conversation_id}/
涉及文件路径时用相对路径(基于沙箱根),不要写绝对路径。

{collab_section}
================"""


# ============================================================
# 表情包库(broadcast 模式)
# ============================================================

import json as _json_lib
import re as _re
from pathlib import Path as _Path

_MEME_LIBRARY_PATH = _Path(__file__).parent.parent / "skills" / "meme_library.json"
_MEME_MAP: dict[str, dict] = {}


def _load_meme_map() -> dict[str, dict]:
    global _MEME_MAP
    if _MEME_MAP:
        return _MEME_MAP
    try:
        data = _json_lib.loads(_MEME_LIBRARY_PATH.read_text(encoding="utf-8"))
        _MEME_MAP = {m["id"]: m for m in data.get("memes", [])}
    except Exception:
        logger.warning("meme_library.json 加载失败,表情包功能不可用")
        _MEME_MAP = {}
    return _MEME_MAP


_MEME_PATTERN = _re.compile(r'\[MEME:([a-z0-9_]+)\]', _re.IGNORECASE)


def _process_meme_markers(blocks: list) -> list:
    """
    扫描 blocks 里 TextBlock 的 content，把 [MEME:xxx] 标记拆出来变成独立 MemeBlock。
    一个 TextBlock 内可能有多个标记，处理后文本里的标记被移除，MemeBlock 紧接其后插入。
    """
    from backend.domain.message import MemeBlock, TextBlock
    from backend.core.utils import gen_uuid

    meme_map = _load_meme_map()
    if not meme_map:
        return blocks

    result = []
    for block in blocks:
        if getattr(block, "type", None) != "text":
            result.append(block)
            continue

        content: str = block.content
        matches = list(_MEME_PATTERN.finditer(content))
        if not matches:
            result.append(block)
            continue

        # 移除文本里的所有 [MEME:xxx] 标记
        cleaned_text = _MEME_PATTERN.sub("", content).strip()
        if cleaned_text:
            result.append(TextBlock(block_id=block.block_id, content=cleaned_text))
        # 为每个 meme 标记插入 MemeBlock
        for m in matches:
            meme_id = m.group(1).lower()
            meme_info = meme_map.get(meme_id)
            if meme_info:
                result.append(MemeBlock(
                    block_id=gen_uuid(),
                    meme_id=meme_id,
                    url=f"/memes/{meme_info['filename']}",
                    description=meme_info["description"],
                ))
            else:
                logger.warning("未知 meme_id=%r，跳过", meme_id)

    return result


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
            # expunge 前先 refresh,确保所有字段加载到 instance dict,
            # Task 启动时 session 已关闭也能安全访问字段
            self.repo.session.refresh(thread)
            self.repo.session.expunge(thread)
            self._launch_thread_task(thread)
            started.append(thread)
        return started

    async def schedule_conversation_staggered(
        self,
        conversation_id: str,
        max_delay: float = 8.0,
    ) -> list[Thread]:
        """
        broadcast 模式专用：同 schedule_conversation，但每个 Thread 随机延迟启动，
        模拟群聊中各人打字速度不同、回复时间错开的效果。
        第一个 Thread 延迟 0（让群聊感觉立刻有人回），其余随机散布在 (0, max_delay] 秒内。
        """
        import random
        threads = self.repo.list_active_in_conversation(conversation_id)
        started: list[Thread] = []
        first = True
        for thread in threads:
            if thread.status != ThreadStatus.INIT.value:
                continue
            if not self.repo.all_blockers_done(thread):
                continue
            if thread.id in _running_tasks:
                continue
            self.repo.session.refresh(thread)
            self.repo.session.expunge(thread)
            delay = 0.0 if first else round(random.uniform(0.5, max_delay), 1)
            first = False
            self._launch_thread_task(thread, delay=delay)
            started.append(thread)
        return started

    async def cancel_thread(self, thread_id: str) -> Optional[Thread]:
        """
        主动取消单个 Thread。

        策略：只 task.cancel() 触发 _run_thread 内部 CancelledError 路径，
        让那里统一负责 mark_cancelled + push agent_error('cancelled')。
        本方法不再写库，避免与 _run_thread 争同一行触发 MySQL 1205。

        如果 thread 没有对应 task（已终态 / 未启动），则直接 mark_cancelled 兜底。
        """
        task = _running_tasks.pop(thread_id, None)
        if task and not task.done():
            task.cancel()
            # 等 task 走完 CancelledError 分支再返回，确保数据库已落 cancelled 终态
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
            # 重新读取最新状态
            return self.repo.get(thread_id)
        # 没有 task 在跑 → 自己写终态
        return await self.mark_cancelled(thread_id)

    async def cancel_all_in_conversation(self, conversation_id: str) -> list[Thread]:
        """
        流式中止 / 队列抢占:取消该会话所有未结束 Thread。

        【session 策略】用独立短 session 立刻 commit。
        关键:不能用 self.session(HTTP 请求级 session,不 commit 不释放行锁),
        否则 orchestrator 的 finally 块抢同一行会撞 1205,等满 innodb_lock_wait_timeout(10s)
        × 重试 N 次 = 几十秒 → 用户点 stop 后前端卡住。
        每个 thread 独立短事务:cancel asyncio.Task + UPDATE + commit + close,瞬间释锁。
        """
        from backend.core.database import db_session

        # 拿待取消列表用短 session(只读)
        with db_session() as s:
            threads = ThreadRepository(s).list_active_in_conversation(conversation_id)
            thread_ids = [t.id for t in threads]

        cancelled: list[Thread] = []
        for tid in thread_ids:
            # 1. cancel asyncio.Task(瞬间)
            task = _running_tasks.pop(tid, None)
            if task and not task.done():
                task.cancel()
            # 2. 独立短事务写终态 + 立即 commit 释锁
            with db_session() as s:
                t = ThreadRepository(s).mark_status(tid, ThreadStatus.CANCELLED)
                s.commit()
                if t is not None:
                    s.refresh(t)
                    s.expunge(t)
                    cancelled.append(t)
            # 3. 触发父 Agent 唤醒等后续(用本 service 的 self,但 _on_thread_terminal
            # 内部也走短 session,不依赖 self.session 的事务状态)
            if cancelled and cancelled[-1].id == tid:
                await self._on_thread_terminal(
                    cancelled[-1],
                    f"Thread {tid} 已取消",
                    success=False,
                )
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

        【session 策略】用短 session 自查,不依赖 self.repo(后者绑的可能是已关闭的旧 session)。
        """
        if thread.agent_id == "orchestrator":
            return None
        from backend.core.database import db_session
        with db_session() as s:
            siblings = ThreadRepository(s).list_by_message(thread.message_id)
            for sib in siblings:
                if sib.agent_id == "orchestrator" and sib.id != thread.id:
                    return sib.id
            return None

    # --------------------------------------------------------
    # 内部:启动 Thread(异步运行 Adapter.stream)
    # --------------------------------------------------------

    def _launch_thread_task(self, thread: Thread, *, delay: float = 0.0) -> None:
        """把 Thread 启动包装为 asyncio.Task,登记到 _running_tasks。"""
        task = asyncio.create_task(self._run_thread(thread, delay=delay))
        _running_tasks[thread.id] = task

    async def _run_thread(self, thread: Thread, *, delay: float = 0.0) -> None:
        """
        启动单个 Thread:mark_running → 调 Adapter.stream → 处理事件 → 落终态。
        """
        from backend.core.database import db_session
        from backend.repositories.agent_repo import AgentRepository
        from backend.repositories.message_repo import MessageRepository
        from backend.repositories.thread_repo import ThreadRepository

        logger.info("_run_thread started thread=%s agent=%s", thread.id, thread.agent_id)

        if adapter_registry is None:
            raise NotImplementedError(
                "[TODO/D5] adapters/registry 未实装,无法启动 Thread。"
            )

        # 短 session 写状态:每次开 / commit / close,绝不长持
        # 返回的 ORM Thread 已用 expunge 从 session 解绑,外层访问字段不会触发 lazy load
        # 关键:commit 后 SQLAlchemy 默认让所有 attr expire,直接 expunge 后访问
        # thread.agent_id 等字段会触发 DetachedInstanceError(session 已关无法 refresh)。
        # 所以 expunge 前要先 refresh,把当前所有列加载到 instance dict,断 session 也能用。
        def _mark(status: ThreadStatus, **kw) -> Optional[Thread]:
            with db_session() as s:
                t = ThreadRepository(s).mark_status(thread.id, status, **kw)
                s.commit()
                if t is not None:
                    s.refresh(t)   # 把所有字段从 DB 加载到 t 的属性 dict
                    s.expunge(t)   # 然后再解绑,后续访问字段不再触发 lazy load
                return t

        try:
            if delay > 0:
                await asyncio.sleep(delay)
            _mark(ThreadStatus.RUNNING)

            adapter = adapter_registry.get(thread.agent_id)
            if adapter is None:
                t = _mark(ThreadStatus.ERROR, error_message=f"未注册的 agent_id: {thread.agent_id}")
                if t:
                    await self._on_thread_terminal(t, f"Thread {thread.id} 失败: 未注册的 agent_id", success=False)
                return

            # 一次性把 stream 期间需要的东西全读出来,session 立刻 close。
            # adapter.stream() 跑期间不持有任何 session。
            with db_session() as s:
                agent_row = AgentRepository(s).get(thread.agent_id)
                # 解耦 ORM:把后续要用的字段当场抠出来当纯数据
                agent_name = agent_row.name if agent_row else thread.agent_id
                agent_avatar: Optional[str] = agent_row.avatar if agent_row else None
                agent_description: Optional[str] = agent_row.description if agent_row else None
                agent_system_prompt_raw: Optional[str] = agent_row.system_prompt if agent_row else None

                # 查会话 + 群聊成员,组装运行环境 header
                from backend.repositories.conversation_repo import ConversationRepository
                conv_row = ConversationRepository(s).get(thread.conversation_id)
                conv_mode = (conv_row.mode if conv_row else "single") or "single"
                member_lines: list[str] = []
                if conv_mode in ("group", "broadcast") and conv_row is not None:
                    other_agent_ids = ConversationRepository(s).list_active_agent_ids(thread.conversation_id)
                    for aid in other_agent_ids:
                        # 自己不放进成员列表(避免"你是 X,成员有 X")
                        if aid == thread.agent_id:
                            continue
                        member = AgentRepository(s).get(aid)
                        if member is None:
                            continue
                        # 简介取 description,没有就 fallback agent name
                        brief = (member.description or "").strip()
                        if brief:
                            member_lines.append(f"- {member.name}: {brief}")
                        else:
                            member_lines.append(f"- {member.name}")

                msg_repo = MessageRepository(s)
                raw_history = msg_repo.list_recent(thread.conversation_id, limit=20)
                # repo 返回倒序(最新在前),反转为正序送给 Adapter
                # 立刻把 ORM Message 转成 MessageInHistory(纯数据 schema),session 关了不会失效
                history = [
                    _orm_message_to_history(m)
                    for m in reversed(raw_history)
                ]

                try:
                    from backend.services.skill_service import SkillService
                    agent_skills = SkillService(s).list_with_content_for_agent(thread.agent_id)
                except Exception:
                    logger.exception(
                        "Thread %s 加载 agent_skills 失败,以空列表继续",
                        thread.id,
                    )
                    agent_skills = []
                # 只读 session,db_session() finally 会兜底 rollback + close

            # 拼接最终 system_prompt:运行环境 header + Agent 自身人格 prompt
            # header 在前,确保 Agent 第一眼看到的是"自己是谁、在哪、能干啥"这些事实;
            # 人格 prompt 在后,叠加专业职责。
            runtime_header = _build_runtime_context_header(
                agent_id=thread.agent_id,
                agent_name=agent_name,
                agent_description=agent_description,
                conversation_id=thread.conversation_id,
                conversation_mode=conv_mode,
                member_lines=member_lines,
            )
            if agent_system_prompt_raw:
                agent_system_prompt: Optional[str] = runtime_header + "\n\n" + agent_system_prompt_raw
            else:
                agent_system_prompt = runtime_header

            # 把 agent_row 的关键字段拷到 dict,后续 _persist_assistant_message 不依赖 ORM
            # (它原签名收 agent_row,内部读 agent_row.name / model 等;改后只用 dict 兼容)
            agent_snapshot = {
                "id": thread.agent_id,
                "name": agent_name,
                # model 字段未来可能加;目前 message_service 内部 model=None 兜底
            }

            stream_input = StreamInput(
                agent_id=thread.agent_id,
                agent_name=agent_name,
                agent_avatar=agent_avatar,
                thread_id=thread.id,
                message_id=thread.message_id,
                prompt=thread.dispatch_prompt or "",
                history=history,
                skills=agent_skills,
                system_prompt=agent_system_prompt,
                cancel_event=stream_service.get_abort_event(thread.conversation_id),
            )

            summary_parts: list[str] = []
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
                    # 子 Thread 单轮 LLM 完成,Adapter 上报 usage 累加到 threads.tokens_total。
                    # 失败处理:token 累加是审计 / 计费用,不影响 Thread 主链路。
                    delta = (event.tokens_input or 0) + (event.tokens_output or 0)
                    if delta > 0:
                        try:
                            with db_session() as s:
                                ThreadRepository(s).update_tokens(thread.id, delta)
                                s.commit()
                        except Exception:
                            logger.exception(
                                "Thread %s 累加 token 失败,delta=%d (不影响 Thread 状态)",
                                thread.id,
                                delta,
                            )

                    logger.info(
                        "Thread %s AgentDone 收到,准备落 messages: block_count=%d, "
                        "block_order=%s, tokens=%d/%d",
                        thread.id, len(block_order), block_order,
                        event.tokens_input or 0, event.tokens_output or 0,
                    )

                    # ---- broadcast 模式 sentinel 检测 ----
                    # 如果 LLM 输出的全部文本恰好是 BROADCAST_NO_REPLY_SENTINEL，
                    # 说明 Agent 决定不回复：跳过落消息，写 read_receipt + 推 SSE。
                    if self._is_read_receipt_sentinel(block_order, block_states):
                        await self._handle_read_receipt(thread, agent_name)
                        break

                    await self._persist_assistant_message(
                        thread=thread,
                        agent_row=agent_snapshot,
                        block_order=block_order,
                        block_states=block_states,
                        tokens_input=event.tokens_input or 0,
                        tokens_output=event.tokens_output or 0,
                    )
                    # broadcast 模式下回复了也写已读（回复了 = 也已读）
                    await self._handle_read_receipt(thread, agent_name)
                    break

            summary = " ".join(summary_parts)[:500] or "(无摘要)"
            t = _mark(ThreadStatus.DONE)
            if t:
                await self._on_thread_terminal(t, summary, success=True)

        except asyncio.CancelledError:
            t = _mark(ThreadStatus.CANCELLED)
            # 推 agent_error('cancelled')，前端 workflow store 据此把 thread 状态切到 cancelled
            try:
                await stream_service.push_event(
                    thread.conversation_id,
                    AgentErrorEvent(
                        agent_id=thread.agent_id,
                        thread_id=thread.id,
                        message_id=thread.message_id,
                        error="cancelled",
                    ),
                )
            except Exception:
                logger.exception("Thread %s push cancelled event failed", thread.id)
            if t:
                await self._on_thread_terminal(t, f"Thread {thread.id} 已取消", success=False)
            raise
        except Exception as exc:
            logger.exception("Thread %s 运行异常", thread.id)
            try:
                t = _mark(ThreadStatus.ERROR, error_message=str(exc))
                if t:
                    await self._on_thread_terminal(t, f"Thread {thread.id} 失败: {exc}", success=False)
            except Exception:
                logger.exception("Thread %s 落错误态失败", thread.id)

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

        # meme 后处理:把 text block 里的 [MEME:xxx] 标记替换成独立 MemeBlock
        blocks = _process_meme_markers(blocks)

        # agent_row 现在是 dict 快照(_run_thread 已 expunge ORM,改成纯数据传过来)
        # 兼容老 ORM 路径:有 .name 属性时也走;两条路径都拿 sender 名字
        if isinstance(agent_row, dict):
            sender = agent_row.get("name")
        else:
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
            # meme 处理过 blocks 后，用 message_appended 让前端用落库版本覆盖 streaming 气泡
            if msg is not None and any(getattr(b, "type", None) == "meme" for b in blocks):
                try:
                    msg_dict = {
                        "id": thread.message_id,
                        "conversation_id": thread.conversation_id,
                        "thread_id": thread.id,
                        "agent_id": thread.agent_id,
                        "agent_avatar": None,
                        "role": "assistant",
                        "blocks": [b.model_dump() for b in blocks],
                        "status": "done",
                        "sender": sender,
                        "model": model,
                        "tokens_input": tokens_input,
                        "tokens_output": tokens_output,
                        "latency_ms": None,
                        "feedback": None,
                        "is_deleted": False,
                        "created_at": msg.created_at.isoformat() if hasattr(msg, "created_at") else "",
                    }
                    await stream_service.push_event(
                        thread.conversation_id,
                        MessageAppendedEvent(
                            conversation_id=thread.conversation_id,
                            message=msg_dict,
                        ),
                    )
                except Exception:
                    logger.exception("Thread %s push message_appended (meme) 失败", thread.id)
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

        # broadcast 互聊：记录本轮回复，on_round_done 据此判断是否触发下一轮
        try:
            from backend.services.chat_service import record_broadcast_reply
            # 提取文本摘要（只取 text block 内容）
            text_content = " ".join(
                getattr(b, "content", "") for b in blocks if getattr(b, "type", None) == "text"
            ).strip()
            if text_content:
                record_broadcast_reply(
                    conversation_id=thread.conversation_id,
                    agent_id=thread.agent_id,
                    agent_name=sender or thread.agent_id,
                    content=text_content,
                )
        except Exception:
            logger.exception("Thread %s record_broadcast_reply 失败（不影响消息落库）", thread.id)

    @staticmethod
    def _is_read_receipt_sentinel(
        block_order: list[str],
        block_states: dict[str, dict],
    ) -> bool:
        """
        判断 LLM 输出内容是否是已读回执 sentinel。
        只收集所有 text 类型块的 content，拼起来去首尾空白后：
        - 精确等于 sentinel，或
        - 去掉标点/空白后包含 sentinel（兼容 LLM 在前后加换行/引号的情况）
        """
        from backend.services.chat_service import BROADCAST_NO_REPLY_SENTINEL
        parts: list[str] = []
        for block_id in block_order:
            state = block_states.get(block_id, {})
            if state.get("type") == "text":
                parts.append(state.get("content", ""))
        full_text = "".join(parts).strip()
        logger.debug("broadcast sentinel check: full_text=%r", full_text)
        return BROADCAST_NO_REPLY_SENTINEL in full_text

    async def _handle_read_receipt(self, thread: Thread, agent_name: str) -> None:
        """
        broadcast 模式下 Agent 发出已读回执：
        1. 写 read_receipts 表
        2. 推 ReadReceiptEvent 给前端
        不落 assistant 消息，不创建气泡。
        非 broadcast 模式下直接跳过。
        """
        from backend.adapters.events import ReadReceiptEvent
        from backend.core.database import db_session
        from backend.repositories.read_receipt_repo import ReadReceiptRepository
        from backend.repositories.agent_repo import AgentRepository
        from backend.repositories.conversation_repo import ConversationRepository

        # 只在 broadcast 模式下写已读
        with db_session() as s:
            conv = ConversationRepository(s).get(thread.conversation_id)
            if conv is None or conv.mode != "broadcast":
                return

        try:
            with db_session() as s:
                ReadReceiptRepository(s).save(
                    conversation_id=thread.conversation_id,
                    message_id=thread.message_id,
                    agent_id=thread.agent_id,
                )
                agent_row = AgentRepository(s).get(thread.agent_id)
                agent_avatar = agent_row.avatar if agent_row else None
                s.commit()
        except Exception:
            logger.exception("Thread %s 写 read_receipt 失败", thread.id)
            return

        try:
            await stream_service.push_event(
                thread.conversation_id,
                ReadReceiptEvent(
                    conversation_id=thread.conversation_id,
                    message_id=thread.message_id,
                    agent_id=thread.agent_id,
                    agent_name=agent_name,
                    agent_avatar=agent_avatar,
                ),
            )
        except Exception:
            logger.exception("Thread %s 推 ReadReceiptEvent 失败", thread.id)

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
