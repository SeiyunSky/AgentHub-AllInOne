"""
WorkflowRepository —— workflows 表数据访问层

只暴露 list / create 两个核心方法,外加按 id 查询的 BaseRepository.get。
session 由调用方注入,commit 由 service 控制。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from sqlalchemy import desc

from backend.models.workflow import Workflow
from backend.repositories.base import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    model = Workflow

    def list_for_conversation(
        self,
        conversation_id: str,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Workflow]:
        """
        某用户某会话的 workflow 列表，按 created_at 倒序（最新在前）。
        前端拿到后可自行 reverse 让"最新在下"。
        """
        return (
            self.session.query(Workflow)
            .filter(
                Workflow.conversation_id == conversation_id,
                Workflow.user_id == user_id,
            )
            .order_by(desc(Workflow.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
