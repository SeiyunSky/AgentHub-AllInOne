"""MCP (Model Context Protocol) client with lifecycle management.

Supports both stdio (subprocess MCP servers, e.g. Codex CLI) and SSE/HTTP transports.
MCPRegistry is a module-level singleton that manages all active connections and is
shut down during FastAPI lifespan teardown.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-22
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import anyio
import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Normalized tool descriptor from an MCP server."""

    name: str
    description: str | None
    input_schema: dict[str, Any]
    # Derived from ToolAnnotations.readOnlyHint; True means tool has side effects
    has_side_effects: bool = True


class MCPClient:
    """Manages a single persistent MCP server connection.

    Do not instantiate directly — use the class-method factories:
        await MCPClient.connect_stdio(...)
        await MCPClient.connect_sse(...)
    """

    def __init__(self, server_id: str) -> None:
        self.server_id = server_id
        self._session: ClientSession | None = None
        self._tools_cache: list[MCPTool] | None = None
        # anyio.Event must be created inside an anyio task context (i.e. inside _run),
        # not here — creating it outside causes backend mismatch under uvicorn/anyio.run().
        self._stop_event: anyio.Event | None = None
        self._ready_event = asyncio.Event()
        self._background_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    async def connect_stdio(
        cls,
        server_id: str,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout: float = 15.0,
    ) -> "MCPClient":
        """Create and connect an MCP client via stdio (subprocess) transport."""
        instance = cls(server_id)
        params = StdioServerParameters(command=command, args=args, env=env, cwd=cwd)

        async def _run() -> None:
            try:
                instance._stop_event = anyio.Event()
                async with stdio_client(params) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        instance._session = session
                        instance._ready_event.set()
                        # Hold connection open until stop() is called
                        await instance._stop_event.wait()
            except Exception as exc:
                logger.error("MCP stdio client %s crashed: %s", server_id, exc, exc_info=True)
                instance._ready_event.set()  # Unblock waiters even on failure

        instance._background_task = asyncio.create_task(_run())
        try:
            await asyncio.wait_for(instance._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            instance._background_task.cancel()
            raise RuntimeError(
                f"MCP stdio connection to '{server_id}' timed out after {timeout}s."
            )

        if instance._session is None:
            raise RuntimeError(
                f"MCP stdio connection to '{server_id}' failed — "
                "check that the command is installed and accessible."
            )
        logger.info("MCP stdio client connected: %s", server_id)
        return instance

    @classmethod
    async def connect_sse(
        cls,
        server_id: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> "MCPClient":
        """Create and connect an MCP client via SSE/HTTP transport."""
        instance = cls(server_id)

        async def _run() -> None:
            try:
                instance._stop_event = anyio.Event()
                async with sse_client(url, headers=headers or {}) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        instance._session = session
                        instance._ready_event.set()
                        await instance._stop_event.wait()
            except Exception as exc:
                logger.error("MCP SSE client %s crashed: %s", server_id, exc)
                instance._ready_event.set()

        instance._background_task = asyncio.create_task(_run())
        try:
            await asyncio.wait_for(instance._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            instance._background_task.cancel()
            raise RuntimeError(
                f"MCP SSE connection to '{server_id}' at {url} timed out after {timeout}s."
            )

        if instance._session is None:
            raise RuntimeError(
                f"MCP SSE connection to '{server_id}' at {url} failed."
            )
        logger.info("MCP SSE client connected: %s → %s", server_id, url)
        return instance

    @classmethod
    async def connect_streamable_http(
        cls,
        server_id: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> "MCPClient":
        """Create and connect an MCP client via Streamable HTTP transport (MCP spec 2025-03-26+)."""
        instance = cls(server_id)

        async def _run() -> None:
            try:
                instance._stop_event = anyio.Event()
                import httpx
                http_client = httpx.AsyncClient(headers=headers or {})
                async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        instance._session = session
                        instance._ready_event.set()
                        await instance._stop_event.wait()
            except Exception as exc:
                logger.error("MCP streamable-http client %s crashed: %s", server_id, exc)
                instance._ready_event.set()

        instance._background_task = asyncio.create_task(_run())
        try:
            await asyncio.wait_for(instance._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            instance._background_task.cancel()
            raise RuntimeError(
                f"MCP streamable-http connection to '{server_id}' at {url} timed out after {timeout}s."
            )

        if instance._session is None:
            raise RuntimeError(
                f"MCP streamable-http connection to '{server_id}' at {url} failed."
            )
        logger.info("MCP streamable-http client connected: %s → %s", server_id, url)
        return instance

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[MCPTool]:
        """Fetch and cache the tools exposed by this MCP server."""
        if self._tools_cache is not None:
            return self._tools_cache
        if self._session is None:
            raise RuntimeError(f"MCP client '{self.server_id}' is not connected.")
        result: mcp_types.ListToolsResult = await self._session.list_tools()
        self._tools_cache = [
            MCPTool(
                name=t.name,
                description=t.description,
                input_schema=t.inputSchema if isinstance(t.inputSchema, dict) else {},
                has_side_effects=not (
                    t.annotations is not None
                    and getattr(t.annotations, "readOnlyHint", False) is True
                ),
            )
            for t in result.tools
        ]
        logger.info("MCP '%s': collected %d tool(s): %s", self.server_id, len(self._tools_cache), [t.name for t in self._tools_cache])
        return self._tools_cache

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> mcp_types.CallToolResult:
        """Call a tool on the MCP server and return its result."""
        if self._session is None:
            raise RuntimeError(f"MCP client '{self.server_id}' is not connected.")
        return await self._session.call_tool(name=name, arguments=arguments)

    def invalidate_tools_cache(self) -> None:
        """Force re-fetch of tools on next list_tools() call."""
        self._tools_cache = None

    async def stop(self) -> None:
        """Disconnect from the MCP server and clean up resources."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._background_task is not None:
            try:
                await asyncio.wait_for(self._background_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._background_task.cancel()
        self._session = None
        logger.info("MCP client disconnected: %s", self.server_id)


class MCPRegistry:
    """Singleton registry of all active MCP server connections.

    Adapters request connections by server_id.  The registry keeps connections
    alive and shares them across adapter instances.

    Usage:
        client = await MCPRegistry.get_or_connect_stdio("codex", "codex", ["--mcp-server"])
        await MCPRegistry.shutdown_all()   # called in FastAPI lifespan shutdown
    """

    _connections: dict[str, MCPClient] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def get_or_connect_stdio(
        cls,
        server_id: str,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> MCPClient:
        async with cls._lock:
            if server_id not in cls._connections:
                cls._connections[server_id] = await MCPClient.connect_stdio(
                    server_id, command, args, env=env, cwd=cwd
                )
            return cls._connections[server_id]

    @classmethod
    async def get_or_connect_sse(
        cls,
        server_id: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> MCPClient:
        async with cls._lock:
            if server_id not in cls._connections:
                cls._connections[server_id] = await MCPClient.connect_sse(
                    server_id, url, headers=headers
                )
            return cls._connections[server_id]

    @classmethod
    async def get_or_connect_streamable_http(
        cls,
        server_id: str,
        url: str,
        headers: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> MCPClient:
        # 如果 user_id 传入，先从 mcp_token_service 取最新 token 注入 Authorization header
        # 这样 SAP MCP 服务器（Client Credentials）能在每次连接时拿到有效 token
        if user_id:
            try:
                from backend.services.mcp_token_service import mcp_token_service
                token = await mcp_token_service.get_token(server_id, user_id)
                if token:
                    headers = {**(headers or {}), "Authorization": f"Bearer {token}"}
                    # token 有效，需要重连以携带最新 token（不复用旧连接）
                    cache_key = f"{server_id}:{token[:16]}"
                else:
                    cache_key = server_id
            except Exception:
                cache_key = server_id
        else:
            cache_key = server_id

        async with cls._lock:
            if cache_key not in cls._connections:
                cls._connections[cache_key] = await MCPClient.connect_streamable_http(
                    server_id, url, headers=headers
                )
            return cls._connections[cache_key]

    @classmethod
    def get(cls, server_id: str) -> MCPClient | None:
        return cls._connections.get(server_id)

    @classmethod
    async def shutdown_all(cls) -> None:
        """Stop all connections. Call this during FastAPI lifespan shutdown."""
        for client in list(cls._connections.values()):
            try:
                await client.stop()
            except Exception as exc:
                logger.warning("Error stopping MCP client %s: %s", client.server_id, exc)
        cls._connections.clear()
