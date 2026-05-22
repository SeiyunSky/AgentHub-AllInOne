"""
agents — Agent 配置表

每一行代表一个可被用户调用的 AI Agent，包含其类型、人格定义、能力声明、可见性。
- type 决定后端调度时路由到哪个 Adapter（claude / codex / custom）。
- capabilities 用 JSON 声明能力开关（如是否支持 diff / 是否要审批），由前端按需展示。
- tags 是给联系人列表展示的能力标签数组。
- is_public + is_active 控制可见性：联系人列表查询条件为
  WHERE is_active = 1 AND (user_id = :me OR is_public = 1)
- user_id 为 NULL 表示系统内置 Agent（如内置 Claude / Codex）。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, Text, Enum, JSON, SmallInteger, Index

from backend.models.base import Base, TimestampMixin


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, comment="UUID")
    user_id = Column(String(36), nullable=True, comment="创建者，NULL=系统内置")
    name = Column(String(100), nullable=False, comment="联系人列表展示名")
    description = Column(String(500), nullable=True, comment="Agent 简介，联系人卡片副标题")
    type = Column(
        Enum("claude", "codex", "opencode", "custom", name="agent_type"),
        nullable=False,
        comment="路由到对应 Adapter",
    )
    system_prompt = Column(Text, nullable=True, comment="Agent 人格定义")
    capabilities = Column(
        JSON,
        nullable=True,
        comment='{"supports_diff":true,"supports_approval":true}',
    )
    tags = Column(JSON, nullable=True, comment='["python","code-review"]')
    is_public = Column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="公开/私有",
    )
    is_active = Column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
        comment="启用/停用",
    )

    __table_args__ = (
        Index("ix_agents_user_active", "user_id", "is_active"),
        Index("ix_agents_public_active", "is_public", "is_active"),
    )
