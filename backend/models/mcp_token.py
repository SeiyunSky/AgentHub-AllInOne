"""
mcp_tokens — MCP 服务器 OAuth/OIDC token 存储表

每个用户对每个需要鉴权的 MCP 服务器存一行 token。
- Client Credentials 服务器：user_id="GUGA"（系统级，所有用户共用）
- OIDC 服务器：user_id=实际用户，每人独立授权

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.models.base import Base, UTCTimestamp


class MCPToken(Base):
    __tablename__ = "mcp_tokens"

    id           = Column(String(36),  primary_key=True)
    user_id      = Column(String(36),  nullable=False, comment="用户 ID；Client Credentials 用 'GUGA'")
    server_id    = Column(String(100), nullable=False, comment="mcp_servers.id")
    access_token = Column(Text,        nullable=False, comment="OAuth access token")
    expires_at   = Column(UTCTimestamp, nullable=False, comment="过期时间（UTC）")
    created_at   = Column(UTCTimestamp, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_mcp_tokens_user_server", "user_id", "server_id"),
        UniqueConstraint("user_id", "server_id", name="uq_mcp_tokens_user_server"),
    )
