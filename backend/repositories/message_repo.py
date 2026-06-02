"""
MessageRepository —— messages 表数据访问层

继承 BaseRepository[Message] 的通用 CRUD,补充按会话 / Thread 反查、
软删除、token 字段写入等业务专有方法。

session 由调用方注入;repo 只 add / flush,commit 由 service 控制。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, or_

from backend.models.message import Message
from backend.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    # --------------------------------------------------------
    # 业务查询
    # --------------------------------------------------------

    def list_recent(
        self,
        conversation_id: str,
        *,
        limit: int = 20,
        before: Optional[str] = None,
    ) -> list[Message]:
        """
        按会话取最近 N 条消息，不含已软删除。

        **返回结果按 created_at ASC（从旧到新）**，与时间线展示顺序一致，调用方无需反转。

        before：游标分页，传消息 id 时只返回该消息**之前**（更早）的记录。
        游标用 (created_at, id) 复合比较破平：同毫秒下按 id 字典序破平，
        防止单纯 created_at < anchor 时遗漏同时刻消息。
        游标 id 必须属于同一会话，否则抛 ValueError。
        """
        query = (
            self.session.query(Message)
            .filter(
                Message.conversation_id == conversation_id,
                Message.is_deleted == 0,
            )
        )
        if before is not None:
            # 验证 cursor 归属：必须来自同一会话，防止跨会话游标泄露
            anchor = (
                self.session.query(Message)
                .filter(
                    Message.id == before,
                    Message.conversation_id == conversation_id,
                    Message.is_deleted == 0,
                )
                .first()
            )
            if anchor is None:
                raise ValueError(f"无效的分页游标：消息 {before} 不属于会话 {conversation_id}")
            query = query.filter(
                or_(
                    Message.created_at < anchor.created_at,
                    and_(
                        Message.created_at == anchor.created_at,
                        Message.id < anchor.id,
                    ),
                )
            )
        # 先取最近 N 条（DESC），再用子查询翻转成 ASC 返回给调用方
        # 等价于：SELECT * FROM (SELECT ... ORDER BY created_at DESC LIMIT N) t ORDER BY created_at ASC
        # 用 Python 侧反转简化实现
        rows = (
            query.order_by(desc(Message.created_at), desc(Message.id))
            .limit(limit)
            .all()
        )
        rows.reverse()
        return rows

    def list_by_thread(self, thread_id: str) -> list[Message]:
        """反查某 Thread 产出的所有消息(用于审计 / 复盘子 Thread 的完整产出)。"""
        return (
            self.session.query(Message)
            .filter(
                Message.thread_id == thread_id,
                Message.is_deleted == 0,
            )
            .order_by(Message.created_at.asc())
            .all()
        )

    # --------------------------------------------------------
    # 字段更新
    # --------------------------------------------------------

    def update_tokens(
        self,
        id: str,
        *,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        latency_ms: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Optional[Message]:
        """
        子 Adapter 跑完后回写 token / 延迟 / 模型快照。
        只更新非 None 的字段,避免无意覆盖。
        """
        msg = self.get(id)
        if msg is None:
            return None
        if tokens_input is not None:
            msg.tokens_input = tokens_input
        if tokens_output is not None:
            msg.tokens_output = tokens_output
        if latency_ms is not None:
            msg.latency_ms = latency_ms
        if model is not None:
            msg.model = model
        self.session.flush()
        return msg

    def soft_delete(self, id: str) -> bool:
        """软删除:is_deleted=1。返回是否成功(消息不存在时返回 False)。"""
        msg = self.get(id)
        if msg is None:
            return False
        msg.is_deleted = 1
        self.session.flush()
        return True

    def set_feedback(
        self,
        id: str,
        feedback: Optional[str],
    ) -> Optional[Message]:
        """设置 / 清除 feedback("up" / "down" / None)。"""
        msg = self.get(id)
        if msg is None:
            return None
        msg.feedback = feedback
        self.session.flush()
        return msg

    def update_status(
        self,
        id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
    ) -> Optional[Message]:
        """
        更新 streaming → done / error 状态。
        status=error 时 error_message 必填,会落到字段。
        """
        msg = self.get(id)
        if msg is None:
            return None
        msg.status = status
        if status == "error" and error_message:
            msg.error_message = error_message
        self.session.flush()
        return msg
