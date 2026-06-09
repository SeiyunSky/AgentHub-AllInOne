"""
MCP 服务器管理 API

MCP 服务器是独立实体（与 Skill 对齐），可跨 Agent 复用。

--- 独立 CRUD ---
GET    /mcp-servers                     列出当前用户可见的 MCP 服务器
POST   /mcp-servers                     创建 MCP 服务器
GET    /mcp-servers/{id}                详情
PATCH  /mcp-servers/{id}                更新
DELETE /mcp-servers/{id}                删除

--- Agent 挂载管理（与 skill_ids 对齐）---
GET    /agents/{agent_id}/mcp-servers              列出该 Agent 挂载的 MCP 服务器
POST   /agents/{agent_id}/mcp-servers/{id}         挂载
DELETE /agents/{agent_id}/mcp-servers/{id}         卸载

--- 可用性测试 ---
POST   /mcp-servers/{id}/test           测试连通性，返回工具列表

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""
from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_db
from backend.repositories.mcp_server_repo import MCPServerRepository
from backend.repositories.agent_repo import AgentRepository
from backend.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MCPTestResult,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_writable(server, user_id: str) -> None:
    if server.author_id != user_id:
        if server.author_id == "GUGA":
            raise HTTPException(status_code=403, detail="内置 MCP 服务器不可修改")
        raise HTTPException(status_code=403, detail="无权修改他人创建的 MCP 服务器")


def _assert_agent_writable(agent, user_id: str) -> None:
    if agent.user_id != user_id:
        if agent.user_id == "GUGA":
            raise HTTPException(status_code=403, detail="内置 Agent 不可修改")
        raise HTTPException(status_code=403, detail="无权修改他人创建的 Agent")


async def _rebuild_adapter(agent_id: str, agent, db) -> None:
    if agent_id == "orchestrator":
        from backend.services.orchestrator.service import reload_orchestrator_mcp_clients
        try:
            await reload_orchestrator_mcp_clients(db)
        except Exception:
            logger.warning("mcp_servers change: reload orchestrator MCP clients failed")
        return
    from backend.adapters.registry import registry, _build_adapter
    try:
        registry.register(agent_id, await _build_adapter(agent, db))
    except Exception:
        logger.warning("mcp_servers change: rebuild adapter failed for agent %s", agent_id)


# ---------------------------------------------------------------------------
# MCP 服务器独立 CRUD
# ---------------------------------------------------------------------------

@router.get("/mcp-servers", response_model=list[MCPServerResponse])
def list_mcp_servers(
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    repo = MCPServerRepository(db)
    return repo.list_visible_for_user(user_id, limit=limit, offset=offset)


@router.post("/mcp-servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
def create_mcp_server(
    data: MCPServerCreate,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = MCPServerRepository(db)
    fields = data.model_dump()
    fields["author_id"] = user_id
    fields["is_public"] = 1 if fields.pop("is_public") else 0
    server = repo.create(**fields)
    db.commit()
    db.refresh(server)
    return server


@router.get("/mcp-servers/{mcp_server_id}", response_model=MCPServerResponse)
def get_mcp_server(
    mcp_server_id: str,
    db: Session = Depends(get_db),
    _: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = MCPServerRepository(db)
    server = repo.get(mcp_server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    return server


@router.patch("/mcp-servers/{mcp_server_id}", response_model=MCPServerResponse)
def update_mcp_server(
    mcp_server_id: str,
    data: MCPServerUpdate,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = MCPServerRepository(db)
    server = repo.get(mcp_server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    _assert_writable(server, user_id)

    fields = data.model_dump(exclude_unset=True)
    if "is_public" in fields:
        fields["is_public"] = 1 if fields["is_public"] else 0
    if "is_active" in fields:
        fields["is_active"] = 1 if fields["is_active"] else 0

    for key, val in fields.items():
        setattr(server, key, val)
    db.commit()
    db.refresh(server)
    return server


@router.delete("/mcp-servers/{mcp_server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server(
    mcp_server_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = MCPServerRepository(db)
    server = repo.get(mcp_server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    _assert_writable(server, user_id)
    db.delete(server)
    db.commit()


# ---------------------------------------------------------------------------
# Agent 挂载管理
# ---------------------------------------------------------------------------

@router.get("/agents/{agent_id}/mcp-servers", response_model=list[MCPServerResponse])
def list_agent_mcp_servers(
    agent_id: str,
    db: Session = Depends(get_db),
    _: Annotated[str, Depends(get_current_user)] = ...,
):
    """列出该 Agent 挂载的所有 MCP 服务器。"""
    agent = AgentRepository(db).get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return MCPServerRepository(db).list_servers_for_agent(agent_id)


@router.post(
    "/agents/{agent_id}/mcp-servers/{mcp_server_id}",
    response_model=MCPServerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_mcp_server(
    agent_id: str,
    mcp_server_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    """将 MCP 服务器挂载到 Agent。"""
    agent_repo = AgentRepository(db)
    mcp_repo = MCPServerRepository(db)

    agent = agent_repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    _assert_agent_writable(agent, user_id)

    server = mcp_repo.get(mcp_server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")

    mcp_repo.attach_server(agent_id, mcp_server_id)
    db.commit()

    await _rebuild_adapter(agent_id, agent, db)
    return server


@router.delete(
    "/agents/{agent_id}/mcp-servers/{mcp_server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_mcp_server(
    agent_id: str,
    mcp_server_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    """从 Agent 卸载 MCP 服务器。"""
    agent_repo = AgentRepository(db)
    mcp_repo = MCPServerRepository(db)

    agent = agent_repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    _assert_agent_writable(agent, user_id)

    ids = mcp_repo.list_server_ids_for_agent(agent_id)
    if mcp_server_id not in ids:
        raise HTTPException(status_code=404, detail="该 MCP 服务器未挂载到此 Agent")

    mcp_repo.detach_server(agent_id, mcp_server_id)
    db.commit()

    await _rebuild_adapter(agent_id, agent, db)


# ---------------------------------------------------------------------------
# 可用性测试
# ---------------------------------------------------------------------------

@router.post("/mcp-servers/{mcp_server_id}/test", response_model=MCPTestResult)
async def test_mcp_server(
    mcp_server_id: str,
    db: Session = Depends(get_db),
    _: Annotated[str, Depends(get_current_user)] = ...,
):
    """测试 MCP 服务器连通性，返回工具列表。超时 10s。"""
    repo = MCPServerRepository(db)
    server = repo.get(mcp_server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")

    from backend.adapters.mcp_client import MCPClient

    try:
        if server.transport == "stdio":
            if not server.command:
                return MCPTestResult(server_id=mcp_server_id, ok=False, error="stdio 配置缺少 command")
            client = await asyncio.wait_for(
                MCPClient.connect_stdio(
                    f"_test_{mcp_server_id}",
                    server.command,
                    list(server.args or []),
                    env=dict(server.env) if server.env else None,
                ),
                timeout=10,
            )
        elif server.transport == "streamable_http":
            if not server.url:
                return MCPTestResult(server_id=mcp_server_id, ok=False, error="streamable_http 配置缺少 url")
            client = await asyncio.wait_for(
                MCPClient.connect_streamable_http(
                    f"_test_{mcp_server_id}",
                    server.url,
                    headers=dict(server.headers) if server.headers else None,
                ),
                timeout=10,
            )
        else:
            if not server.url:
                return MCPTestResult(server_id=mcp_server_id, ok=False, error="sse 配置缺少 url")
            client = await asyncio.wait_for(
                MCPClient.connect_sse(
                    f"_test_{mcp_server_id}",
                    server.url,
                    headers=dict(server.headers) if server.headers else None,
                ),
                timeout=10,
            )

        tools = await asyncio.wait_for(client.list_tools(), timeout=5)
        await client.stop()
        return MCPTestResult(server_id=mcp_server_id, ok=True, tools=[t.name for t in tools])

    except asyncio.TimeoutError:
        return MCPTestResult(server_id=mcp_server_id, ok=False, error="连接超时（>10s）")
    except Exception as exc:
        return MCPTestResult(server_id=mcp_server_id, ok=False, error=str(exc))
