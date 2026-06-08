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

from backend.models.mcp_server import MCPServer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 预置 MCP Server 数据
# ---------------------------------------------------------------------------

PRESET_MCP_SERVERS: list[dict] = [
    {
        "id": "deepwiki",
        "name": "DeepWiki",
        "description": "DeepWiki MCP Server，提供 Wikipedia 知识库查询能力",
        "transport": "sse",
        "url": "https://mcp.deepwiki.com/mcp",
        "headers": {},
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
    {
        "id": "law-ai",
        "name": "LawAI",
        "description": "LawAI MCP Server，提供法律法规查询与法律知识服务",
        "transport": "sse",
        "url": "https://mcp.law.ai",
        "headers": {},
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
    {
        "id": "petstore-api",
        "name": "Petstore API",
        "description": "Petstore MCP Server，提供宠物商店 API 示例服务",
        "transport": "sse",
        "url": "https://petstore.run.mcp.com.ai/mcp",
        "headers": {},
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
    {
        "id": "jina-ai",
        "name": "Jina AI",
        "description": "Jina AI MCP Server，提供网页内容抓取、向量嵌入与搜索服务",
        "transport": "sse",
        "url": "https://mcp.jina.ai/v1",
        "headers": {},
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
    {
        "id": "mcp-registry",
        "name": "MCP Registry",
        "description": "MCP Registry Server，提供 MCP 服务发现与注册能力",
        "transport": "sse",
        "url": "https://registry.run.mcp.com.ai/mcp",
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