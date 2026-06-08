"""AdapterRegistry — maps agent_id to AgentAdapter instances.

Populated at FastAPI startup via seed_from_db(); updated by register()/unregister()
when agents are created or deleted through agent_service.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.adapters.base import AgentAdapter
from backend.adapters.mcp_client import MCPClient, MCPRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Maps agent_id → AgentAdapter instance.

    This is a module-level singleton (see ``registry`` at bottom of file).
    Service layer calls registry.get_or_raise(agent_id) before streaming.
    """

    def __init__(self) -> None:
        self._registry: dict[str, AgentAdapter] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent_id: str, adapter: AgentAdapter) -> None:
        self._registry[agent_id] = adapter
        logger.debug("Registered adapter for agent_id=%s (%s)", agent_id, type(adapter).__name__)

    def unregister(self, agent_id: str) -> None:
        self._registry.pop(agent_id, None)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentAdapter | None:
        return self._registry.get(agent_id)

    def get_or_raise(self, agent_id: str) -> AgentAdapter:
        adapter = self.get(agent_id)
        if adapter is None:
            from backend.core.exceptions import AgentNotFoundError
            raise AgentNotFoundError(f"No adapter registered for agent_id={agent_id!r}")
        return adapter

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def seed_from_db(self, db: "Session") -> None:
        """Populate registry from the agents table at startup.

        Called during FastAPI lifespan startup. async because building adapters
        may connect to MCP servers (MCPClient.connect_stdio/sse are coroutines).
        """
        from sqlalchemy import select
        from backend.models.agent import Agent as AgentModel

        rows = db.execute(
            select(AgentModel).where(AgentModel.is_active == 1)
        ).scalars().all()
        for row in rows:
            try:
                adapter = await _build_adapter(row, db)
                self.register(row.id, adapter)
            except Exception as exc:
                logger.error("Failed to build adapter for agent %s (%s): %s", row.id, row.type, exc)

        logger.info("AdapterRegistry seeded: %d agents loaded", len(self._registry))

    async def shutdown(self) -> None:
        """Clear the registry on shutdown."""
        self._registry.clear()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

async def connect_mcp_clients_for_agent(agent_id: str, db: "Session") -> list[MCPClient]:
    """Load and connect MCP servers for the given agent_id.

    Public helper used by OrchestratorService at startup so the orchestrator
    can call MCP tools directly (without going through an AgentAdapter).
    """
    mcp_servers = _load_mcp_servers(agent_id, db)
    return await _connect_mcp_clients(agent_id, mcp_servers)


async def _connect_mcp_clients(agent_id: str, mcp_servers) -> list[MCPClient]:
    """Connect MCP servers and return live MCPClient instances (for API-based adapters)."""
    clients: list[MCPClient] = []
    for srv in mcp_servers:
        try:
            if srv.transport == "stdio":
                if not srv.command:
                    logger.warning("Agent %s: stdio MCP server '%s' missing command — skipped", agent_id, srv.id)
                    continue
                client = await MCPRegistry.get_or_connect_stdio(
                    srv.id, srv.command, list(srv.args or []), env=dict(srv.env) if srv.env else None,
                )
            else:
                if not srv.url:
                    logger.warning("Agent %s: sse MCP server '%s' missing url — skipped", agent_id, srv.id)
                    continue
                client = await MCPRegistry.get_or_connect_sse(
                    srv.id, srv.url, headers=dict(srv.headers) if srv.headers else None,
                )
            clients.append(client)
        except Exception as exc:
            logger.error("Agent %s: failed to connect MCP server '%s': %s", agent_id, srv.id, exc)
    return clients


def _load_mcp_servers(agent_id: str, db: "Session"):
    """Load MCPServer ORM rows for an agent via the relation table."""
    from backend.repositories.mcp_server_repo import MCPServerRepository
    return MCPServerRepository(db).list_servers_for_agent(agent_id)


def _to_mcp_configs(mcp_servers):
    """Convert MCPServer ORM rows to MCPServerConfig domain objects."""
    from backend.domain.agent import MCPServerConfig
    configs = []
    for srv in mcp_servers:
        try:
            configs.append(MCPServerConfig(
                server_id=srv.id,
                transport=srv.transport,
                command=srv.command,
                args=list(srv.args or []),
                env=dict(srv.env or {}),
                url=srv.url,
                headers=dict(srv.headers or {}),
            ))
        except Exception as exc:
            logger.warning("Agent: invalid MCPServer row %r — skipped (%s)", srv.id, exc)
    return configs


async def _build_adapter(row, db: "Session") -> AgentAdapter:  # type: ignore[name-defined]
    """Build the correct adapter from an ORM Agent row."""
    agent_type: str = row.type

    mcp_servers = _load_mcp_servers(row.id, db)
    mcp_configs = _to_mcp_configs(mcp_servers)

    # CLI adapters (claude, opencode) receive raw configs so they can write
    # temp config files. API adapters (custom) receive live MCPClient connections.
    if agent_type == "claude":
        from backend.adapters.claude import ClaudeAdapter
        return ClaudeAdapter(mcp_configs=mcp_configs)

    if agent_type == "codex":
        from backend.adapters.codex import CodexAdapter
        codex_mcp = MCPRegistry.get("codex")
        return CodexAdapter(mcp_client=codex_mcp)

    if agent_type == "custom":
        from backend.adapters.custom import CustomAdapter
        mcp_clients = await _connect_mcp_clients(row.id, mcp_servers)
        capabilities: dict = row.capabilities or {}
        return CustomAdapter(
            model=capabilities.get("model"),
            api_key=capabilities.get("api_key"),
            base_url=capabilities.get("base_url"),
            mcp_clients=mcp_clients,
        )

    if agent_type == "opencode":
        from backend.adapters.opencode import OpencodeAdapter
        return OpencodeAdapter(
            bin_path=os.environ.get("OPENCODE_BIN_PATH", "opencode"),
            mcp_configs=mcp_configs,
        )

    raise ValueError(f"Unknown agent type: {agent_type!r}")


# Module-level singleton consumed by service layer
registry = AdapterRegistry()
