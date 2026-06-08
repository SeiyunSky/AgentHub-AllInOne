"""
ThreadRepository —— threads 表数据访问层

继承 BaseRepository[Thread] 的通用 CRUD,补充任务图调度 / 状态机迁移 /
checkpoint 序列化等业务专有方法。

session 由调用方注入;repo 只 add / flush,commit 由 service 控制。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import bindparam, func

from backend.core.utils import gen_uuid
from backend.models.thread import Thread
from backend.repositories.base import BaseRepository
from backend.schemas.thread import ThreadCheckpoint, ThreadStatus


_TERMINAL_STATUSES = {ThreadStatus.DONE, ThreadStatus.ERROR, ThreadStatus.CANCELLED}
_TERMINAL_STATUS_VALUES = {s.value for s in _TERMINAL_STATUSES}


class ThreadRepository(BaseRepository[Thread]):
    model = Thread

    # --------------------------------------------------------
    # 业务查询
    # --------------------------------------------------------

    def find_latest_by_agent(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> Optional[Thread]:
        """
        @个体特化用:找该会话里某 Agent 最近一个 Thread。
        按 updated_at 倒序取首条;无记录返回 None。
        """
        return (
            self.session.query(Thread)
            .filter(
                Thread.conversation_id == conversation_id,
                Thread.agent_id == agent_id,
            )
            .order_by(Thread.updated_at.desc())
            .first()
        )

    def resume_or_create(
        self,
        *,
        conversation_id: str,
        agent_id: str,
        message_id: str,
        reuse_terminal: bool = False,
    ) -> Thread:
        """
        @个体特化用:有可复用的 Thread 则返回,否则新建。

        复用判定:
        - reuse_terminal=False(默认):只复用未结束的 Thread(init/running/suspended)
        - reuse_terminal=True:也复用已结束的 Thread(适合"接着上次的对话继续问"场景)

        新建时 message_id 用本次用户消息的 id;复用时不动 message_id。
        """
        latest = self.find_latest_by_agent(conversation_id, agent_id)
        if latest is not None:
            if reuse_terminal or latest.status not in _TERMINAL_STATUS_VALUES:
                return latest
        return self.create_thread(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
        )

    def list_by_message(self, message_id: str) -> list[Thread]:
        """反向查:某条用户消息触发的所有 Thread(主 Agent + 各子 Thread)。"""
        return (
            self.session.query(Thread)
            .filter(Thread.message_id == message_id)
            .all()
        )

    def list_active_in_conversation(self, conversation_id: str) -> list[Thread]:
        """
        调度循环用:该会话所有未结束的 Thread(init / running / suspended)。
        按 created_at 升序,保证调度顺序稳定。
        """
        active = [
            ThreadStatus.INIT.value,
            ThreadStatus.RUNNING.value,
            ThreadStatus.SUSPENDED.value,
        ]
        return (
            self.session.query(Thread)
            .filter(
                Thread.conversation_id == conversation_id,
                Thread.status.in_(active),
            )
            .order_by(Thread.created_at.asc())
            .all()
        )

    def list_active_thread_ids(self, conversation_id: str) -> list[str]:
        """
        获取会话所有活跃 Thread 的 ID 列表(用于 SSE 回放)。
        只返回 ID,轻量查询。
        """
        active = [
            ThreadStatus.INIT.value,
            ThreadStatus.RUNNING.value,
            ThreadStatus.SUSPENDED.value,
        ]
        rows = (
            self.session.query(Thread.id)
            .filter(
                Thread.conversation_id == conversation_id,
                Thread.status.in_(active),
            )
            .all()
        )
        return [row[0] for row in rows]

    def list_dependents_of(self, thread_id: str) -> list[Thread]:
        """
        解锁判定用:找出 blocked_by 数组里包含 thread_id 的所有下游 Thread。
        用 MySQL JSON_CONTAINS(blocked_by, '"<id>"') 实现,thread_id 走绑定参数防注入。
        """
        return (
            self.session.query(Thread)
            .filter(
                func.json_contains(
                    Thread.blocked_by,
                    bindparam("tid", value=f'"{thread_id}"'),
                )
            )
            .all()
        )

    def all_blockers_done(self, thread: Thread) -> bool:
        """
        判定 thread.blocked_by 中所有依赖是否都已进入终态(done/error/cancelled)。
        无依赖时直接返回 True。
        """
        blockers: list[str] = thread.blocked_by or []
        if not blockers:
            return True
        rows = (
            self.session.query(Thread.id, Thread.status)
            .filter(Thread.id.in_(blockers))
            .all()
        )
        if len(rows) != len(blockers):
            # 引用了不存在的 thread_id,视为依赖未满足(避免误启动)
            return False
        return all(status in _TERMINAL_STATUS_VALUES for _, status in rows)

    # --------------------------------------------------------
    # 状态机迁移
    # --------------------------------------------------------

    def mark_status(
        self,
        id: str,
        status: ThreadStatus,
        *,
        error_message: Optional[str] = None,
    ) -> Optional[Thread]:
        """
        原子地迁移 Thread 状态,顺带写 started_at / finished_at / error_message。

        - status=running 且 started_at 为空 → 写入当前 UTC
        - status 进入终态(done/error/cancelled) → 写入 finished_at
        - status=error 时 error_message 必须传入,落到字段
        """
        thread = self.get(id)
        if thread is None:
            return None

        now = datetime.now(timezone.utc)
        thread.status = status.value

        if status == ThreadStatus.RUNNING and thread.started_at is None:
            thread.started_at = now

        if status in _TERMINAL_STATUSES:
            thread.finished_at = now

        if status == ThreadStatus.ERROR:
            thread.error_message = error_message or "(未提供错误信息)"

        self.session.flush()
        return thread

    # --------------------------------------------------------
    # checkpoint 序列化
    # --------------------------------------------------------

    def save_checkpoint(self, id: str, checkpoint: ThreadCheckpoint) -> Optional[Thread]:
        """把 ThreadCheckpoint 序列化成 dict 写入 threads.checkpoint 字段。"""
        thread = self.get(id)
        if thread is None:
            return None
        thread.checkpoint = checkpoint.model_dump(mode="json")
        self.session.flush()
        return thread

    def load_checkpoint(self, id: str) -> Optional[ThreadCheckpoint]:
        """读取 threads.checkpoint 字段并反序列化为 ThreadCheckpoint。无 checkpoint 返回 None。"""
        thread = self.get(id)
        if thread is None or thread.checkpoint is None:
            return None
        return ThreadCheckpoint.model_validate(thread.checkpoint)

    def update_tokens(self, id: str, tokens_total_delta: int) -> Optional[Thread]:
        """累加 tokens_total(Adapter / 主 Agent 每次 LLM 调用后调用)。"""
        thread = self.get(id)
        if thread is None:
            return None
        thread.tokens_total = (thread.tokens_total or 0) + tokens_total_delta
        self.session.flush()
        return thread

    def update_blocked_by(
        self,
        id: str,
        blocked_by: list[str],
    ) -> Optional[Thread]:
        """
        替换 thread.blocked_by 数组(add_task / remove_task 工具用)。
        传入空列表表示"立即可启动"。
        """
        thread = self.get(id)
        if thread is None:
            return None
        thread.blocked_by = list(blocked_by)
        self.session.flush()
        return thread

    # --------------------------------------------------------
    # 创建(覆盖父类,补 id 默认值)
    # --------------------------------------------------------

    def create_thread(
        self,
        *,
        conversation_id: str,
        message_id: str,
        agent_id: str,
        id: Optional[str] = None,
        blocked_by: Optional[list[str]] = None,
        dispatch_prompt: Optional[str] = None,
    ) -> Thread:
        """
        创建一行 Thread。id 缺省自动生成 UUID;blocked_by 缺省为空数组。
        新建的 Thread 状态为 init,等待调度器解锁后启动。
        """
        return self.create(
            id=id or gen_uuid(),
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            status=ThreadStatus.INIT.value,
            blocked_by=blocked_by or [],
            dispatch_prompt=dispatch_prompt,
            tokens_total=0,
        )
