"""
auth Pydantic DTO —— 登录 / 注册 / 刷新 / 用户公开信息

设计要点:
1. password 字段在 model_dump() 时不会出现在响应里(只用于 RegisterRequest / LoginRequest 入参)。
2. UserPublic 不含 password_hash,前端只能看到 id / username / display_name / email。
3. TokenResponse 同时返回 access + refresh,前端按场景选用。
4. username 限定 [a-zA-Z0-9_-]{4,50},password 至少 8 字符;严格校验靠正则,LLM 注入也无法绕过。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-02
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============================================================
# 入参 DTO
# ============================================================


class RegisterRequest(BaseModel):
    """注册请求体。username + password 必填,email + display_name 可选。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(
        min_length=4,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="登录名,4-50 字符,仅允许字母数字下划线短横",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="密码,至少 8 字符;不会落库,只存 bcrypt 哈希",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="可选,后续找回密码用",
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="可选,前端展示昵称(可中文);未填时回退到 username",
    )


class LoginRequest(BaseModel):
    """登录请求体。用 username + password 换 access + refresh token。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """用 refresh token 换新的 access(可选地 + refresh) token。"""

    refresh_token: str = Field(min_length=1, description="登录时拿到的 refresh token")


# ============================================================
# 响应 DTO
# ============================================================


class TokenResponse(BaseModel):
    """登录 / 刷新成功时返回的 token 对。"""

    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer", description="OAuth2 习惯,固定 bearer")
    expires_in: int = Field(description="access_token 剩余有效期(秒);前端可据此决定何时 refresh")
    user: "UserPublic" = Field(description="便利字段,免得前端登录后再调一次 /me")


class UserPublic(BaseModel):
    """用户公开信息。绝不包含 password_hash 字段。"""

    model_config = ConfigDict(from_attributes=True)  # 支持从 ORM User 直接构造

    id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# pydantic v2 forward ref 解析
TokenResponse.model_rebuild()


__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    "UserPublic",
]
