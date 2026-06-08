"""
mcp_servers — MCP 服务器配置表

每行是一个独立的 MCP 服务器定义，可被多个 Agent 挂载（多对多，通过 agent_mcp_servers）。
与 skills 表结构对齐：独立实体 + 关联表，支持跨 agent 复用同一配置。

- author_id: 创建者；'GUGA' 表示系统内置
- transport: stdio（子进程）或 sse（HTTP 长连接）
- command/args/env: stdio 专用
- url/headers: sse 专用
- is_public/is_active: 可见性控制，与 Skill 一致

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-08
"""

from sqlalchemy import Column, String, JSON, SmallInteger, Enum, Index, TIMESTAMP, func

from backend.models.base import Base, TimestampMixin, UTCTimestamp


class MCPServer(Base, TimestampMixin):
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True, comment="UUID")
    name = Column(String(100), nullable=False, comment="名称")
    description = Column(String(500), nullable=True, comment="功能简介")
    transport = Column(
        Enum("stdio", "sse", name="mcp_transport"),
        nullable=False,
        comment="连接方式",
    )
    command = Column(String(500), nullable=True, comment="stdio: 可执行文件路径")
    args = Column(JSON, nullable=True, comment='stdio: ["--arg1","val1"]')
    env = Column(JSON, nullable=True, comment='stdio: {"KEY":"value"}')
    url = Column(String(500), nullable=True, comment="sse: 端点 URL")
    headers = Column(JSON, nullable=True, comment='sse: {"Authorization":"Bearer ..."}')
    author_id = Column(String(36), nullable=False, comment="创建者 user_id；'GUGA'=系统内置")
    is_public = Column(SmallInteger, nullable=False, default=0, server_default="0", comment="公开/私有")
    is_active = Column(SmallInteger, nullable=False, default=1, server_default="1", comment="启用/停用")

    __table_args__ = (
        Index("ix_mcp_servers_public_active", "is_public", "is_active"),
    )


class AgentMCPServer(Base):
    __tablename__ = "agent_mcp_servers"

    agent_id = Column(String(36), primary_key=True, comment="agents.id")
    mcp_server_id = Column(String(36), primary_key=True, comment="mcp_servers.id")
    created_at = Column(
        UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        Index("ix_agent_mcp_servers_mcp", "mcp_server_id"),
    )
