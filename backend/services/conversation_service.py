"""
ConversationService —— 会话生命周期管理 + 成员关系

封装 conversations 表 CRUD、置顶 / 归档 / 重命名状态切换、
conversation_agents 关联表的成员管理。

风格与 message_service 一致:**stateless façade**,模块级单例,
方法内自起 SessionLocal + 自管事务。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import HTTPException, status

from backend.core.database import SessionLocal
from backend.models.agent import Agent
from backend.models.conversation import Conversation
from backend.repositories.conversation_repo import ConversationRepository


logger = logging.getLogger(__name__)


ConversationMode = Literal["single", "group"]


class ConversationService:
    """无状态 façade,每方法自管 session + 事务。"""

    # --------------------------------------------------------
    # 创建
    # --------------------------------------------------------

    async def create(
        self,
        *,
        user_id: str,
        title: str,
        mode: ConversationMode,
        agent_ids: Optional[list[str]] = None,
    ) -> Conversation:
        """
        新建会话并挂载初始 Agent 列表。
        agent_ids 为空时是空会话(无成员),后续通过 add_agent 加入。

        重要约定:group 模式必须有 orchestrator(主 Agent),
        如果调用方没传,这里自动补上——主 Agent 是群聊的协调者,
        永远在场,用户不需要也不应该感知它的存在/管理。
        """
        # 群聊兜底:把 orchestrator 放在第一位,其它 agent_ids 跟在后面
        ids = list(agent_ids or [])
        if mode == "group" and "orchestrator" not in ids:
            ids = ["orchestrator", *ids]

        session = SessionLocal()
        try:
            repo = ConversationRepository(session)
            conv = repo.create(
                user_id=user_id,
                title=title,
                mode=mode,
                is_pinned=0,
                is_archived=0,
                message_count=0,
                unread_count=0,
            )
            for agent_id in ids:
                repo.add_agent(conv.id, agent_id)
            session.commit()
            session.refresh(conv)
            return conv
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------
    # 读
    # --------------------------------------------------------

    async def get(self, conversation_id: str) -> Optional[Conversation]:
        """单条会话读取。"""
        session = SessionLocal()
        try:
            return ConversationRepository(session).get(conversation_id)
        finally:
            session.close()

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        """某用户的会话列表(置顶 + 最近活跃排序)。"""
        session = SessionLocal()
        try:
            return ConversationRepository(session).list_for_user(
                user_id,
                limit=limit,
                offset=offset,
            )
        finally:
            session.close()

    async def get_active_agents(
        self,
        conversation_id: str,
    ) -> list[Agent]:
        """
        某会话挂载的所有活跃 Agent 完整对象。
        list_available_agents 工具(orchestrator 19 个工具之一)主调用方。
        """
        session = SessionLocal()
        try:
            return ConversationRepository(session).list_active_agents(conversation_id)
        finally:
            session.close()

    async def get_active_agents_batch(
        self,
        conversation_ids: list[str],
    ) -> dict[str, list[Agent]]:
        """
        批量查询多个会话的活跃 Agent，{conversation_id: [Agent]}。
        用于 list_for_user 场景，避免 N+1 查询。
        """
        session = SessionLocal()
        try:
            return ConversationRepository(session).list_active_agents_for_conversations(
                conversation_ids
            )
        finally:
            session.close()

    async def get_active_agent_ids(
        self,
        conversation_id: str,
    ) -> list[str]:
        """某会话挂载的所有活跃 Agent ID(轻量版,只查 ID)。"""
        session = SessionLocal()
        try:
            return ConversationRepository(session).list_active_agent_ids(conversation_id)
        finally:
            session.close()

    # --------------------------------------------------------
    # 元信息更新
    # --------------------------------------------------------

    async def rename(
        self,
        conversation_id: str,
        title: str,
    ) -> Optional[Conversation]:
        """重命名会话。"""
        session = SessionLocal()
        try:
            result = ConversationRepository(session).update(
                conversation_id,
                title=title,
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def set_pinned(
        self,
        conversation_id: str,
        is_pinned: bool,
    ) -> Optional[Conversation]:
        """置顶 / 取消置顶。"""
        session = SessionLocal()
        try:
            result = ConversationRepository(session).update(
                conversation_id,
                is_pinned=1 if is_pinned else 0,
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def set_archived(
        self,
        conversation_id: str,
        is_archived: bool,
    ) -> Optional[Conversation]:
        """归档 / 取消归档。"""
        session = SessionLocal()
        try:
            result = ConversationRepository(session).update(
                conversation_id,
                is_archived=1 if is_archived else 0,
            )
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------
    # 权限校验
    # --------------------------------------------------------

    async def assert_owned_by(
        self,
        conversation_id: str,
        user_id: str,
    ) -> Conversation:
        """
        校验 conversation 归属：不存在抛 404，归属不匹配抛 403。
        返回会话对象供调用方直接使用，避免二次查库。
        """
        conv = await self.get(conversation_id)
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话 {conversation_id} 不存在",
            )
        if conv.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该会话",
            )
        return conv

    # --------------------------------------------------------
    # 删除
    # --------------------------------------------------------

    async def delete(self, conversation_id: str) -> None:
        """
        硬删除会话及其全部关联数据。
        因为 DB 没有 FK 级联，需手动按顺序清：
        messages → threads → conversation_agents → conversation
        """
        from sqlalchemy import text

        session = SessionLocal()
        try:
            session.execute(
                text("DELETE FROM messages WHERE conversation_id = :id"),
                {"id": conversation_id},
            )
            session.execute(
                text("DELETE FROM threads WHERE conversation_id = :id"),
                {"id": conversation_id},
            )
            session.execute(
                text("DELETE FROM conversation_agents WHERE conversation_id = :id"),
                {"id": conversation_id},
            )
            conv = session.get(Conversation, conversation_id)
            if conv is not None:
                session.delete(conv)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------
    # 成员管理
    # --------------------------------------------------------

    async def add_agent(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> None:
        """把 Agent 加入会话(已存在的 is_active=0 行会被恢复为 1)。"""
        session = SessionLocal()
        try:
            ConversationRepository(session).add_agent(conversation_id, agent_id)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def remove_agent(
        self,
        conversation_id: str,
        agent_id: str,
    ) -> bool:
        """把 Agent 移出会话(软删 is_active=0,历史消息不受影响)。"""
        session = SessionLocal()
        try:
            ok = ConversationRepository(session).remove_agent(conversation_id, agent_id)
            session.commit()
            return ok
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


conversation_service = ConversationService()
