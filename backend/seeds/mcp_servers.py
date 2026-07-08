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

# bank-relationship-agent MCP server 的固定 ID（与 agent_mcp_servers 关联表对齐）
BRM_MCP_SERVER_ID = "bank-relationship-mcp"


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


async def seed_brm_mcp_server(db: Session) -> bool:
    """
    方案 A：启动时通过 SAP BTP Destination Service 解析 bank-relationship MCP 的
    URL + bearer token，写入 mcp_servers 表并关联到 bank-relationship-agent。

    每次启动都会刷新 token（覆盖 headers 字段），因为 token 有过期时间。
    如果环境变量未配置则静默跳过，不阻塞启动。

    Returns True if the server was upserted, False if skipped.
    """
    from backend.config import settings

    auth_url = settings.BRM_DESTINATION_AUTH_URL
    base_url = settings.BRM_DESTINATION_BASE_URL
    client_id = settings.BRM_DESTINATION_CLIENT_ID
    client_secret = settings.BRM_DESTINATION_CLIENT_SECRET
    destination_name = settings.BRM_MCP_DESTINATION_NAME
    server_id = settings.BRM_MCP_SERVER_ID

    if not all([auth_url, base_url, client_id, client_secret]):
        logger.info(
            "BRM_DESTINATION_* env vars not set — skipping bank-relationship MCP seed"
        )
        return False

    try:
        import httpx

        # Step 1: 获取 Destination Service 的 OAuth token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{auth_url}/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
        dest_service_token = resp.json()["access_token"]
        logger.info("BRM: obtained Destination Service token")

        # Step 2: 解析指定 Destination，拿到 MCP Hub base URL + bearer token
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{base_url}/destination-configuration/v1/destinations/{destination_name}",
                headers={"Authorization": f"Bearer {dest_service_token}"},
                timeout=15.0,
            )
            resp.raise_for_status()
        dest_data = resp.json()
        auth_tokens = dest_data.get("authTokens", [])
        if not auth_tokens:
            raise RuntimeError(f"No authTokens in destination '{destination_name}'")
        bearer_token = auth_tokens[0]["value"]
        mcp_base_url = dest_data["destinationConfiguration"]["URL"].rstrip("/")
        mcp_url = f"{mcp_base_url}/{server_id}"
        logger.info("BRM: resolved MCP URL → %s", mcp_url)

    except Exception:
        logger.exception(
            "BRM MCP seed failed — bank-relationship-agent will be unavailable"
        )
        return False

    # Step 3: 写入 mcp_servers 表（upsert：不存在则 INSERT，存在则更新 url/headers）
    existing = db.query(MCPServer).filter_by(id=BRM_MCP_SERVER_ID).first()
    if existing is None:
        db.add(MCPServer(
            id=BRM_MCP_SERVER_ID,
            name="Bank Relationship MCP",
            description="SAP bank-relationship-agent MCP Server，提供银行账户/余额/费用/信用额度查询",
            transport="streamable_http",
            url=mcp_url,
            headers={"Authorization": f"Bearer {bearer_token}"},
            author_id="GUGA",
            is_public=0,
            is_active=1,
        ))
        logger.info("BRM: inserted mcp_servers row (id=%s)", BRM_MCP_SERVER_ID)
    else:
        existing.url = mcp_url
        existing.headers = {"Authorization": f"Bearer {bearer_token}"}
        logger.info("BRM: refreshed token in mcp_servers (id=%s)", BRM_MCP_SERVER_ID)

    # Step 4: 关联到 bank-relationship-agent
    link = (
        db.query(AgentMCPServer)
        .filter_by(agent_id="agent-brm-builtin", mcp_server_id=BRM_MCP_SERVER_ID)
        .first()
    )
    if link is None:
        db.add(AgentMCPServer(
            agent_id="agent-brm-builtin",
            mcp_server_id=BRM_MCP_SERVER_ID,
        ))
        logger.info("BRM: linked mcp_server to agent-brm-builtin")

    db.commit()
    return True