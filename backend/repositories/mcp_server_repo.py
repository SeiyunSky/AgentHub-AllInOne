"""
MCPServerRepository — mcp_servers 表 + agent_mcp_servers 关联表数据访问层

继承 BaseRepository[MCPServer] 通用 CRUD，补充：
- 按 author 或 public/active 过滤的列表查询
- agent_mcp_servers 挂载关系增删查（与 SkillRepository 接口对齐）

session 由调用方注入；repo 只 add / flush，commit 由 service / route 控制。

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""

from __future__ import annotations

from sqlalchemy import and_, desc, or_

from backend.models.mcp_server import AgentMCPServer, MCPServer
from backend.repositories.base import BaseRepository


class MCPServerRepository(BaseRepository[MCPServer]):
    model = MCPServer

    # --------------------------------------------------------
    # 列表查询
    # --------------------------------------------------------

    def list_visible_for_user(
        self,
        user_id: str,
        *,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MCPServer]:
        """用户可见：自己创建的 + 公开的，按 created_at 倒序。"""
        conds = [or_(MCPServer.author_id == user_id, MCPServer.is_public == 1)]
        if not include_inactive:
            conds.append(MCPServer.is_active == 1)
        return (
            self.session.query(MCPServer)
            .filter(and_(*conds))
            .order_by(desc(MCPServer.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    # --------------------------------------------------------
    # agent_mcp_servers 挂载关系
    # --------------------------------------------------------

    def list_servers_for_agent(self, agent_id: str) -> list[MCPServer]:
        """返回某 Agent 挂载的所有 MCP 服务器（按 name 升序，仅 active）。"""
        return (
            self.session.query(MCPServer)
            .join(AgentMCPServer, AgentMCPServer.mcp_server_id == MCPServer.id)
            .filter(AgentMCPServer.agent_id == agent_id, MCPServer.is_active == 1)
            .order_by(MCPServer.name.asc())
            .all()
        )

    def list_server_ids_for_agent(self, agent_id: str) -> list[str]:
        rows = (
            self.session.query(AgentMCPServer.mcp_server_id)
            .filter(AgentMCPServer.agent_id == agent_id)
            .all()
        )
        return [r.mcp_server_id for r in rows]

    def attach_server(self, agent_id: str, mcp_server_id: str) -> None:
        """挂载 MCP 服务器；已存在则 no-op。"""
        existing = (
            self.session.query(AgentMCPServer)
            .filter(
                AgentMCPServer.agent_id == agent_id,
                AgentMCPServer.mcp_server_id == mcp_server_id,
            )
            .first()
        )
        if existing is None:
            self.session.add(AgentMCPServer(agent_id=agent_id, mcp_server_id=mcp_server_id))
            self.session.flush()

    def detach_server(self, agent_id: str, mcp_server_id: str) -> None:
        """卸载 MCP 服务器；不存在则 no-op。"""
        self.session.query(AgentMCPServer).filter(
            AgentMCPServer.agent_id == agent_id,
            AgentMCPServer.mcp_server_id == mcp_server_id,
        ).delete()
        self.session.flush()

    def sync_agent_servers(self, agent_id: str, mcp_server_ids: list[str]) -> None:
        """替换 Agent 的全部挂载 MCP 服务器（增量 diff：新增 + 删除多余）。"""
        current = set(self.list_server_ids_for_agent(agent_id))
        target = set(mcp_server_ids)
        for sid in target - current:
            self.attach_server(agent_id, sid)
        for sid in current - target:
            self.detach_server(agent_id, sid)
