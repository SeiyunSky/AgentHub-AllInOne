"""
Agent 领域实体

定义跟数据库 / 框架无关的 Agent 核心概念,供 schemas / adapters / models 三方共享:
- AgentType:Agent 类型枚举(决定 Adapter 路由)
- AgentCapabilities:Agent 能力声明(决定 UI 是否展示对应交互)
为了让 schemas(DTO 传输)、adapters(基础设施)、models(ORM)三方共用同一份定义,
本模块虽然位于 domain 层,但允许使用 pydantic 作为基础设施。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from enum import Enum

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent 类型,决定 Adapter 路由(claude / codex / opencode / custom)"""
    CLAUDE = "claude"
    CODEX = "codex"
    OPENCODE = "opencode"
    CUSTOM = "custom"


class AgentCapabilities(BaseModel):
    """
    Agent 能力声明。

    用途:
    - 数据库 agents.capabilities JSON 字段反序列化目标
    - Adapter.get_capabilities() 返回类型
    - 前端按字段决定是否渲染对应 UI(如 supports_diff=False 时不显示 Diff 卡片应用按钮)
    """

    supports_diff: bool = Field(
        default=False,
        description="是否能产出 artifact_diff 卡片",
    )
    supports_approval: bool = Field(
        default=False,
        description="是否会触发 approval_request 审批事件",
    )
