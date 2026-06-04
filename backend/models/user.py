"""
users — 用户表

存储登录用户的核心身份信息。
- username 是登录账号（英文唯一），display_name 是给前端展示的昵称（可中文）。
- password_hash 仅存 bcrypt 摘要，禁止明文。
- email 与 last_login_at 为可选信息，用于后续找回密码 / 安全审计扩展。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, TIMESTAMP

from backend.models.base import Base, UTCTimestamp, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, comment="UUID")
    username = Column(String(50), unique=True, nullable=False, comment="登录名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    display_name = Column(String(100), nullable=True, comment="昵称，前端显示用")
    last_login_at = Column(UTCTimestamp, nullable=True, comment="上次登录时间")
