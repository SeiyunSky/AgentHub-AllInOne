"""
内置 MCP Server seed 数据

在服务启动时自动创建预置的 MCP Server 配置。

幂等策略：
  - 记录不存在 → INSERT
  - 记录存在 → SKIP（尊重用户的手动修改）

新增内置 MCP Server：
  1. 在 PRESET_MCP_SERVERS 中追加一条记录

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.models.mcp_server import MCPServer, AgentMCPServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 预置 MCP Server 数据
# ---------------------------------------------------------------------------

PRESET_MCP_SERVERS: list[dict] = [
    {
        "id": "deepwiki",
        "name": "DeepWiki",
        "description": "DeepWiki MCP Server，提供 Wikipedia 知识库查询能力",
        "transport": "streamable_http",
        "url": "https://mcp.deepwiki.com/mcp",
        "headers": {},
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
]


def seed_mcp_servers(db: Session) -> int:
    """
    幂等写入内置 MCP Server。返回实际插入的行数。

    策略：
      - 不存在 → INSERT
      - 存在 → SKIP（尊重用户的手动修改）
    """
    affected = 0
    for spec in PRESET_MCP_SERVERS:
        existing = db.query(MCPServer).filter_by(id=spec["id"]).first()

        if existing is None:
            db.add(MCPServer(**spec))
            logger.info("Seeded MCP Server (insert): %s", spec["name"])
            affected += 1
        else:
            # 存在则跳过，尊重用户的修改
            logger.debug("MCP Server already exists: %s (skip)", spec["name"])

    if affected:
        db.commit()
        logger.info("Seed MCP Servers committed (%d server(s) affected)", affected)

    return affected


def seed_orchestrator_mcp_links(db: Session) -> int:
    """幂等地把所有预置 MCP Server 关联到 orchestrator agent。

    策略：
      - 关联不存在 → INSERT
      - 关联存在    → SKIP
    """
    affected = 0
    for spec in PRESET_MCP_SERVERS:
        existing = (
            db.query(AgentMCPServer)
            .filter_by(agent_id="orchestrator", mcp_server_id=spec["id"])
            .first()
        )
        if existing is None:
            db.add(AgentMCPServer(agent_id="orchestrator", mcp_server_id=spec["id"]))
            logger.info("Seeded orchestrator MCP link: %s", spec["id"])
            affected += 1
        else:
            logger.debug("orchestrator MCP link already exists: %s (skip)", spec["id"])

    if affected:
        db.commit()
        logger.info("Seed orchestrator MCP links committed (%d link(s) affected)", affected)

    return affected