"""AdapterRegistry — maps agent_id to AgentAdapter instances.

Populated at FastAPI startup via seed_from_db(); updated by register()/unregister()
when agents are created or deleted through agent_service.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-22
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.adapters.base import AgentAdapter

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

    def seed_from_db(self, db: "Session") -> None:
        """Populate registry from the agents table at startup.

        Called during FastAPI lifespan startup. Accepts a plain sync Session
        (consistent with the rest of the service layer).
        """
        from sqlalchemy import select
        from backend.models.agent import Agent as AgentModel

        rows = db.execute(
            select(AgentModel).where(AgentModel.is_active == 1)
        ).scalars().all()
        for row in rows:
            try:
                adapter = _build_adapter(row)
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

def _build_adapter(row: "AgentModel") -> AgentAdapter:  # type: ignore[name-defined]
    """Build the correct adapter from an ORM Agent row."""
    agent_type: str = row.type

    if agent_type == "claude":
        from backend.adapters.claude import ClaudeAdapter
        return ClaudeAdapter()

    if agent_type == "codex":
        from backend.adapters.codex import CodexAdapter
        from backend.adapters.mcp_client import MCPRegistry
        mcp_client = MCPRegistry.get("codex")
        return CodexAdapter(mcp_client=mcp_client)

    if agent_type == "custom":
        from backend.adapters.custom import CustomAdapter
        capabilities: dict = row.capabilities or {}
        return CustomAdapter(
            model=capabilities.get("model"),
            api_key=capabilities.get("api_key"),
            base_url=capabilities.get("base_url"),
        )

    if agent_type == "opencode":
        from backend.adapters.opencode import OpencodeAdapter
        return OpencodeAdapter(bin_path=os.environ.get("OPENCODE_BIN_PATH", "opencode"))

    raise ValueError(f"Unknown agent type: {agent_type!r}")


# Module-level singleton consumed by service layer
registry = AdapterRegistry()
