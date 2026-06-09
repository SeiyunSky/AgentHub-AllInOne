"""
users — 用户表

存储登录用户的核心身份信息。
- username 是登录账号（英文唯一），display_name 是给前端展示的昵称（可中文）。
- password_hash 仅存 bcrypt 摘要，禁止明文；OAuth 用户无本地密码，该字段为 NULL。
- email 与 last_login_at 为可选信息，用于后续找回密码 / 安全审计扩展。
- oauth_provider / oauth_subject / oauth_tenant_id 支持第三方 OAuth2 登录（微软等）。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-06-08
"""

from sqlalchemy import Column, String

from backend.models.base import Base, UTCTimestamp, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, comment="UUID")
    username = Column(String(50), unique=True, nullable=False, comment="登录名")
    password_hash = Column(String(255), nullable=True, comment="bcrypt 哈希；OAuth 用户为 NULL")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    display_name = Column(String(100), nullable=True, comment="昵称，前端显示用")
    last_login_at = Column(UTCTimestamp, nullable=True, comment="上次登录时间")

    # ---- OAuth2 第三方登录 ----
    oauth_provider = Column(String(20), nullable=True, comment="OAuth 提供方，如 microsoft")
    oauth_subject = Column(String(100), nullable=True, comment="OAuth 提供方的用户唯一 ID (oid/sub)")
    oauth_tenant_id = Column(String(36), nullable=True, comment="AAD 租户 ID，multi-tenant 场景用")
