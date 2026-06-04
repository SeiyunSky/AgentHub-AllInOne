"""
workflows 相关 Pydantic DTO

对应数据结构:前端 stores/workflow.ts 的 WorkflowThread / WorkflowBlock。
后端只做透传存储,不解析嵌套数据形状(blocks 字段直接走 dict[str, Any])。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowBlock(BaseModel):
    """单个 block，对齐前端 WorkflowBlock。后端不强校验字段，扩展性留给前端。"""

    model_config = ConfigDict(extra="allow")

    block_id: str = Field(alias="blockId")
    type: str
    tool_name: Optional[str] = Field(default=None, alias="toolName")
    tool_input: Optional[dict[str, Any]] = Field(default=None, alias="toolInput")
    content: Optional[str] = None
    language: Optional[str] = None
    code: Optional[str] = None
    filename: Optional[str] = None
    status: str = "done"
    started_at: Optional[int] = Field(default=None, alias="startedAt")
    finished_at: Optional[int] = Field(default=None, alias="finishedAt")


class WorkflowThread(BaseModel):
    """单个 thread，对齐前端 WorkflowThread。"""

    model_config = ConfigDict(extra="allow")

    thread_id: str = Field(alias="threadId")
    agent_id: str = Field(alias="agentId")
    agent_name: str = Field(alias="agentName")
    message_id: str = Field(alias="messageId")
    status: str
    blocks: list[WorkflowBlock] = Field(default_factory=list)
    started_at: Optional[int] = Field(default=None, alias="startedAt")
    finished_at: Optional[int] = Field(default=None, alias="finishedAt")
    error: Optional[str] = None
    tokens_input: Optional[int] = Field(default=None, alias="tokensInput")
    tokens_output: Optional[int] = Field(default=None, alias="tokensOutput")


class WorkflowCreate(BaseModel):
    """POST /api/v1/workflows 请求体"""

    conversation_id: str
    trigger_message_id: Optional[str] = None
    threads: list[dict[str, Any]] = Field(
        description="原样存储的 WorkflowThread[]，后端不做强校验",
    )


class WorkflowResponse(BaseModel):
    """GET /api/v1/workflows 返回项"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    user_id: str
    trigger_message_id: Optional[str] = None
    threads: list[dict[str, Any]]
    created_at: datetime
