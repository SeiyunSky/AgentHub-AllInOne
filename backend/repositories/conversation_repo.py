"""
ConversationRepository —— conversations 表数据访问层

继承 BaseRepository[Conversation] 通用 CRUD,补充用户视角列表查询、
冗余字段同步更新(last_message_*  / message_count)、conversation_agents
关联表读写等业务专有方法。

session 由调用方注入;repo 只 add / flush,commit 由 service 控制。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc

from backend.models.agent import Agent
from backend.models.conversation import Conversation
from backend.models.conversation_agent import ConversationAgent
from backend.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    # --------------------------------------------------------
    # 业务查询
    # --------------------------------------------------------

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Conversation]:
        """
        某用户的会话列表，按置顶 + last_message_at 倒序，返回全部（含归档）。
        """
        query = self.session.query(Conversation).filter(
            Conversation.user_id == user_id,
        )
        query = query.order_by(
            desc(Conversation.is_pinned),
            desc(Conversation.last_message_at),
            desc(Conversation.updated_at),
        )
        query = query.offset(offset).limit(limit)
        return query.all()

    # --------------------------------------------------------
    # 冗余字段更新(每次发消息时由 message_service 同步调)
    # --------------------------------------------------------

    def touch_last_message(
        self,
        id: str,
        *,
        preview: str,
        at: datetime,
    ) -> Optional[Conversation]:
        """
        发新消息时刷新冲余字段:
        - last_message_preview:摘要,前 200 字符
        - last_message_at:消息时间
        - message_count:+1
        """
        conv = self.get(id)
        if conv is None:
            return None
        conv.last_message_preview = preview[:200]
        conv.last_message_at = at
        conv.message_count = (conv.message_count or 0) + 1
        self.session.flush()
        return conv

    # --------------------------------------------------------
    # conversation_agents 关联表
    # --------------------------------------------------------

    def list_active_agent_ids(self, conversation_id: str) -> list[str]:
        """
        某会话挂载的所有活跃(is_active=1)Agent ID,按 joined_at 升序。
        """
        rows = (
            self.session.query(ConversationAgent.agent_id)
            .filter(
                ConversationAgent.conversation_id == conversation_id,
                ConversationAgent.is_active == 1,
            )
            .order_by(ConversationAgent.joined_at.asc())
            .all()
        )
        return [r[0] for r in rows]

    def list_active_agents(self, conversation_id: str) -> list[Agent]:
        """
        某会话挂载的所有活跃 Agent 完整对象。
        join conversation_agents + agents,按 joined_at 升序。
        """
        return (
            self.session.query(Agent)
            .join(
                ConversationAgent,
                ConversationAgent.agent_id == Agent.id,
            )
            .filter(
                ConversationAgent.conversation_id == conversation_id,
                ConversationAgent.is_active == 1,
                Agent.is_active == 1,
            )
            .order_by(ConversationAgent.joined_at.asc())
            .all()
        )

    def add_agent(self, conversation_id: str, agent_id: str) -> ConversationAgent:
        """
        把 Agent 加入会话。
        - 已存在(is_active=0 或 1)→ 把 is_active 置 1 并返回(语义:重新加入)
        - 不存在 → 新建一行
        """
        existing = (
            self.session.query(ConversationAgent)
            .filter(
                ConversationAgent.conversation_id == conversation_id,
                ConversationAgent.agent_id == agent_id,
            )
            .first()
        )
        if existing is not None:
            existing.is_active = 1
            self.session.flush()
            return existing
        row = ConversationAgent(
            conversation_id=conversation_id,
            agent_id=agent_id,
            is_active=1,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def remove_agent(self, conversation_id: str, agent_id: str) -> bool:
        """
        把 Agent 移出会话(软删:is_active=0,保留历史消息关联)。
        返回是否实际改动了行(原本就 is_active=0 / 不存在 → False)。
        """
        existing = (
            self.session.query(ConversationAgent)
            .filter(
                ConversationAgent.conversation_id == conversation_id,
                ConversationAgent.agent_id == agent_id,
                ConversationAgent.is_active == 1,
            )
            .first()
        )
        if existing is None:
            return False
        existing.is_active = 0
        self.session.flush()
        return True

    def list_active_agents_for_conversations(
        self, conversation_ids: list[str]
    ) -> dict[str, list[Agent]]:
        """
        批量查询多个会话的活跃 Agent，返回 {conversation_id: [Agent, ...]}。
        1 次 IN 查询代替 N 次单独查询，消除 conversation list 的 N+1 问题。
        """
        if not conversation_ids:
            return {}
        rows = (
            self.session.query(ConversationAgent.conversation_id, Agent)
            .join(Agent, Agent.id == ConversationAgent.agent_id)
            .filter(
                ConversationAgent.conversation_id.in_(conversation_ids),
                ConversationAgent.is_active == 1,
                Agent.is_active == 1,
            )
            .order_by(ConversationAgent.conversation_id, ConversationAgent.joined_at.asc())
            .all()
        )
        result: dict[str, list[Agent]] = {cid: [] for cid in conversation_ids}
        for conv_id, agent in rows:
            result[conv_id].append(agent)
        return result
