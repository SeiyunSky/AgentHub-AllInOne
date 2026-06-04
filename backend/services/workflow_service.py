"""
WorkflowService —— workflow 视图持久化业务层

风格与 message_service / conversation_service 一致：stateless façade,
模块级单例,方法内自管 SessionLocal + 事务。

职责:
1. save(user_id, conversation_id, trigger_message_id, threads) — 落库一行
2. list_for_conversation(user_id, conversation_id, limit, offset) — 查询历史

不做数据校验/聚合,前端给什么 threads JSON 就存什么。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.database import SessionLocal
from backend.models.workflow import Workflow
from backend.repositories.workflow_repo import WorkflowRepository

logger = logging.getLogger(__name__)


class WorkflowService:
    async def save(
        self,
        *,
        user_id: str,
        conversation_id: str,
        trigger_message_id: str | None,
        threads: list[dict[str, Any]],
    ) -> Workflow:
        """落一行 workflow，threads JSON 原样存储。"""
        session = SessionLocal()
        try:
            repo = WorkflowRepository(session)
            wf = repo.create(
                conversation_id=conversation_id,
                user_id=user_id,
                trigger_message_id=trigger_message_id,
                threads=threads,
            )
            session.commit()
            session.refresh(wf)
            logger.info(
                "WorkflowService: saved id=%s conv=%s threads=%d",
                wf.id, conversation_id, len(threads),
            )
            return wf
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def list_for_conversation(
        self,
        *,
        user_id: str,
        conversation_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Workflow]:
        """某会话最近 N 份 workflow，按 created_at 倒序。"""
        session = SessionLocal()
        try:
            return WorkflowRepository(session).list_for_conversation(
                conversation_id,
                user_id,
                limit=limit,
                offset=offset,
            )
        finally:
            session.close()


workflow_service = WorkflowService()
