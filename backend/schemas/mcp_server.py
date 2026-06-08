"""
mcp_servers 相关 Pydantic DTO

与 skills 对齐：独立实体，支持跨 Agent 复用。

涵盖：
1. MCPServerResponse — 列表/详情返回
2. MCPServerCreate   — POST /mcp-servers
3. MCPServerUpdate   — PATCH /mcp-servers/{id}
4. MCPTestResult     — POST /mcp-servers/{id}/test 返回

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str = Field(description="名称")
    description: Optional[str] = None
    transport: Literal["stdio", "sse"]
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)
    author_id: str
    is_public: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def _coerce_list(cls, v):
        return [] if v is None else v

    @classmethod
    def _coerce_dict(cls, v):
        return {} if v is None else v

    # Pydantic v2: use model_validator or field_validator for None → default coercion
    from pydantic import field_validator

    @field_validator("args", mode="before")
    @classmethod
    def _args_none(cls, v):
        return [] if v is None else v

    @field_validator("env", "headers", mode="before")
    @classmethod
    def _dict_none(cls, v):
        return {} if v is None else v


class MCPServerCreate(BaseModel):
    name: str = Field(description="名称", min_length=1, max_length=100)
    description: Optional[str] = None
    transport: Literal["stdio", "sse"]
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)
    is_public: bool = False


class MCPServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    transport: Optional[Literal["stdio", "sse"]] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class MCPTestResult(BaseModel):
    server_id: str
    ok: bool
    tools: list[str] = []
    error: Optional[str] = None
