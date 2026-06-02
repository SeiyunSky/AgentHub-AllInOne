"""
AgentRepository —— agents 表数据访问层

继承 BaseRepository[Agent] 通用 CRUD,补充用户视角可见性查询、
批量按 ID 查询、停用/启用切换等业务专有方法。

session 由调用方注入;repo 只 add / flush,commit 由 service 控制。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, or_

from backend.models.agent import Agent
from backend.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    model = Agent

    # --------------------------------------------------------
    # 业务查询
    # --------------------------------------------------------

    def list_visible_for_user(
        self,
        user_id: str,
        *,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Agent]:
        """
        某用户的联系人列表:自己创建的 + 公开的(去重)。

        条件:WHERE is_active=1 AND (user_id=:me OR is_public=1)
        include_inactive=True 时不过滤 is_active(管理后台用)。
        按 created_at 倒序(新建的排在前)。
        """
        conds = [
            or_(Agent.user_id == user_id, Agent.is_public == 1),
        ]
        if not include_inactive:
            conds.append(Agent.is_active == 1)

        return (
            self.session.query(Agent)
            .filter(and_(*conds))
            .order_by(desc(Agent.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_by_ids(
        self,
        ids: list[str],
        *,
        include_inactive: bool = False,
    ) -> list[Agent]:
        """
        按 ID 列表批量查 Agent。返回顺序不保证(按 DB 默认),调用方需要保序时自己排。
        """
        if not ids:
            return []
        query = self.session.query(Agent).filter(Agent.id.in_(ids))
        if not include_inactive:
            query = query.filter(Agent.is_active == 1)
        return query.all()

    # --------------------------------------------------------
    # 状态切换
    # --------------------------------------------------------

    def set_active(self, id: str, is_active: bool) -> Optional[Agent]:
        """启用 / 停用 Agent。停用后联系人列表不可见、不可发消息。"""
        agent = self.get(id)
        if agent is None:
            return None
        agent.is_active = 1 if is_active else 0
        self.session.flush()
        return agent

    def set_public(self, id: str, is_public: bool) -> Optional[Agent]:
        """切换公开 / 私有可见性。"""
        agent = self.get(id)
        if agent is None:
            return None
        agent.is_public = 1 if is_public else 0
        self.session.flush()
        return agent
