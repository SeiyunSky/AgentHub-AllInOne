"""
conversations 相关 Pydantic DTO

对应数据结构设计文档第五节 conversations 表 + 第六节 conversation_agents 关联表。

涵盖三类 DTO:
1. 枚举 —— ConversationMode(single / group)
2. 嵌套结构 —— AgentMember(挂载到会话的成员卡片,简化版)
3. API DTO —— ConversationCreate / ConversationUpdate / ConversationResponse /
              ConversationListItem(列表用,不带成员细节)

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================
# 枚举
# ============================================================

class ConversationMode(str, Enum):
    """会话模式 —— chat_service 路由分支用"""
    SINGLE = "single"
    GROUP = "group"


# ============================================================
# 嵌套结构
# ============================================================

class AgentMember(BaseModel):
    """会话成员卡片 —— 列详情时返回挂载的 Agent 简要信息"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="agent_id")
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    type: str = Field(description="claude / codex / opencode / custom")


# ============================================================
# API DTO —— 请求体
# ============================================================

class ConversationCreate(BaseModel):
    """POST /api/v1/conversations 请求体"""

    title: str = Field(
        min_length=1,
        max_length=200,
        description="会话标题,前端展示用",
    )
    mode: ConversationMode = Field(description="single 或 group")
    agent_ids: list[str] = Field(
        description="初始挂载的 Agent ID 列表",
    )

    @model_validator(mode="after")
    def _check_agent_ids(self) -> "ConversationCreate":
        # single 必须 1 个 / group 至少 1 个;空 Agent 创建出来后 chat_service
        # 派活会抛 ValueError,前端体验糟糕,这里直接 422 拦下
        if self.mode == ConversationMode.SINGLE and len(self.agent_ids) != 1:
            raise ValueError(
                f"single 模式必须挂载恰好 1 个 Agent,实际 {len(self.agent_ids)}"
            )
        if self.mode == ConversationMode.GROUP and len(self.agent_ids) < 1:
            raise ValueError("group 模式至少挂载 1 个 Agent")
        return self


class ConversationUpdate(BaseModel):
    """
    PATCH /api/v1/conversations/{id} 请求体。

    所有字段可选,只更新传入的非 None 字段;支持重命名 / 置顶 / 归档。
    成员变更走专门的 add_agent / remove_agent 端点。
    """

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


# ============================================================
# API DTO —— 响应体
# ============================================================

class ConversationListItem(BaseModel):
    """GET /api/v1/conversations 列表项，含挂载的 Agent 成员（用于前端拼接头像）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: Optional[str] = None
    mode: ConversationMode
    is_pinned: bool = False
    is_archived: bool = False
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    unread_count: int = 0
    agents: list[AgentMember] = Field(
        default_factory=list,
        description="当前 is_active=1 的成员 Agent 列表，按 joined_at 升序",
    )
    created_at: datetime
    updated_at: datetime


class ConversationResponse(BaseModel):
    """
    GET /api/v1/conversations/{id} 详情。
    比 ListItem 多 agents 字段:挂载的 Agent 成员列表。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: Optional[str] = None
    mode: ConversationMode
    is_pinned: bool = False
    is_archived: bool = False
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    message_count: int = 0
    unread_count: int = 0
    agents: list[AgentMember] = Field(
        default_factory=list,
        description="当前 is_active=1 的成员 Agent 列表,按 joined_at 升序",
    )
    created_at: datetime
    updated_at: datetime
