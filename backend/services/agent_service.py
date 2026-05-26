"""
AgentService —— Agent CRUD + 联系人视图 + 能力探测

封装 agents 表的读写,提供给前端联系人列表 / orchestrator 工具
(list_available_agents / get_agent_capabilities) / chat_service 路由调用。

风格:**stateless façade**,模块级单例,方法内自起 SessionLocal + 自管事务。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from backend.core.database import SessionLocal
from backend.models.agent import Agent
from backend.repositories.agent_repo import AgentRepository


logger = logging.getLogger(__name__)


AgentType = Literal["claude", "codex", "opencode", "custom"]


class AgentService:
    """无状态 façade,每方法自管 session + 事务。"""

    # --------------------------------------------------------
    # 创建 / 编辑
    # --------------------------------------------------------

    async def create(
        self,
        *,
        user_id: str,
        name: str,
        type: AgentType,
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        capabilities: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        is_public: bool = False,
        avatar: Optional[str] = None,
    ) -> Agent:
        """
        新建 Agent 配置。
        - user_id:创建者(系统内置 Agent 用 'GUGA')
        - capabilities:JSON dict,如 {"supports_diff": True, "supports_approval": True}
        - tags:JSON list,联系人标签
        """
        session = SessionLocal()
        try:
            agent = AgentRepository(session).create(
                user_id=user_id,
                name=name,
                type=type,
                description=description,
                system_prompt=system_prompt,
                capabilities=capabilities,
                tags=tags,
                avatar=avatar,
                is_public=1 if is_public else 0,
                is_active=1,
            )
            session.commit()
            session.refresh(agent)
            return agent
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def update(
        self,
        agent_id: str,
        **fields: Any,
    ) -> Optional[Agent]:
        """
        编辑 Agent 配置。
        允许的字段:name / description / system_prompt / capabilities / tags / avatar。
        is_public / is_active 走专门的 set_* 方法,不在这里改。
        """
        forbidden = {"is_public", "is_active", "user_id", "type", "id"}
        bad = forbidden & fields.keys()
        if bad:
            raise ValueError(
                f"AgentService.update 不允许改这些字段:{bad}。"
                "is_public 走 set_public,is_active 走 set_active,"
                "type / user_id / id 不可变更。"
            )
        session = SessionLocal()
        try:
            result = AgentRepository(session).update(agent_id, **fields)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def set_active(
        self,
        agent_id: str,
        is_active: bool,
    ) -> Optional[Agent]:
        """启用 / 停用。"""
        session = SessionLocal()
        try:
            result = AgentRepository(session).set_active(agent_id, is_active)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def set_public(
        self,
        agent_id: str,
        is_public: bool,
    ) -> Optional[Agent]:
        """切换公开 / 私有。"""
        session = SessionLocal()
        try:
            result = AgentRepository(session).set_public(agent_id, is_public)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --------------------------------------------------------
    # 读
    # --------------------------------------------------------

    async def get(self, agent_id: str) -> Optional[Agent]:
        """单条 Agent 读取。"""
        session = SessionLocal()
        try:
            return AgentRepository(session).get(agent_id)
        finally:
            session.close()

    async def list_by_ids(
        self,
        ids: list[str],
        *,
        include_inactive: bool = False,
    ) -> list[Agent]:
        """
        批量按 ID 查 Agent。返回顺序不保证(按 DB 默认),调用方需要保序时自行排序。
        list_available_agents 工具(orchestrator)的核心调用方。
        """
        session = SessionLocal()
        try:
            return AgentRepository(session).list_by_ids(
                ids,
                include_inactive=include_inactive,
            )
        finally:
            session.close()

    async def list_visible_for_user(
        self,
        user_id: str,
        *,
        include_inactive: bool = False,
    ) -> list[Agent]:
        """
        某用户的联系人列表:自己创建的 + 公开的(去重)。
        前端联系人页面调用方。
        """
        session = SessionLocal()
        try:
            return AgentRepository(session).list_visible_for_user(
                user_id,
                include_inactive=include_inactive,
            )
        finally:
            session.close()


agent_service = AgentService()
