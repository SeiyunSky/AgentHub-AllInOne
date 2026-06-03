"""
api/v1/auth.py —— 鉴权端点

5 个端点(prefix /api/v1/auth):
- POST   /register   注册新用户
- POST   /login      用户名密码换 access + refresh token
- POST   /logout     吊销当前 access token(写 Redis 黑名单;Redis 不可用降级 no-op)
- POST   /refresh    用 refresh token 换新 access
- GET    /me         查看当前登录用户信息

错误约定:
- 用户名 / 密码错 → 401 (统一错误信息,防枚举用户名)
- token 无效 / 过期 / 被吊销 → 401
- 注册重名 → 409 Conflict
- 校验失败(短密码 / 非法 username) → 422(由 RequestValidationError 自动处理)

队伍:咕嘎一辈子队
修改者:咕嘎(Phase B)
修改日期:2026-06-02
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.middleware.auth import jwt_bearer
from backend.core.exceptions import (
    AuthenticationError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from backend.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from backend.services.auth_service import AuthService


logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# 工具:从 Authorization header 拿 access token,无则 401
# ============================================================

def _require_token(
    creds: Optional[HTTPAuthorizationCredentials],
) -> str:
    """logout / me 这类必须带 token 的端点用它强制 401。"""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return creds.credentials


def _calc_expires_in(expire_at: datetime) -> int:
    """expire_at 是 aware UTC datetime;返回距离现在的剩余秒数(下限 1)。"""
    return max(1, int((expire_at - datetime.now(timezone.utc)).total_seconds()))


# ============================================================
# POST /api/v1/auth/register
# ============================================================

@router.post(
    "/auth/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="注册新用户",
)
async def register(
    body: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    """
    注册新用户。

    - username 唯一,4-50 字符,仅字母数字下划线短横
    - password 至少 8 字符,落库存 bcrypt 哈希
    - 重名返回 409 Conflict
    """
    try:
        user = AuthService(db).register(
            username=body.username,
            password=body.password,
            email=body.email,
            display_name=body.display_name,
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    return UserPublic.model_validate(user)


# ============================================================
# POST /api/v1/auth/login
# ============================================================

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="用户名 / 密码登录,换 access + refresh token",
)
async def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """登录成功返回双 token + 用户公开信息。失败统一返回 401(不区分用户名错 / 密码错)。"""
    try:
        user, access_token, access_expire, refresh_token, _ = AuthService(db).login(
            username=body.username,
            password=body.password,
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    # 算 access token 剩余秒数(给前端定刷新策略)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=_calc_expires_in(access_expire),
        user=UserPublic.model_validate(user),
    )


# ============================================================
# POST /api/v1/auth/logout
# ============================================================

@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="登出 / 吊销当前 token",
)
async def logout(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(jwt_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """
    把当前 access token 加入 Redis 黑名单。

    - Redis 不可用时降级:成功响应,但 token 仍能用到自然过期(前端应自行清掉)
    - 无 token 直接 401
    """
    token = _require_token(creds)
    try:
        added = AuthService(db).logout(token)
    except TokenInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token 无效: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if not added:
        # Redis 不可用,降级日志(不影响响应)
        logger.warning("logout fell back to no-op (redis unavailable)")
    return None


# ============================================================
# POST /api/v1/auth/refresh
# ============================================================

@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="用 refresh token 换新 access token",
)
async def refresh(
    body: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """
    refresh 不轮换(直到自然过期),只换新的 access。

    错误码:
    - 401: refresh token 无效 / 过期 / 被吊销 / 用户已删
    """
    try:
        user, access_token, access_expire = AuthService(db).refresh(body.refresh_token)
    except TokenInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"refresh token 无效: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    return TokenResponse(
        access_token=access_token,
        refresh_token=body.refresh_token,  # 沿用原 refresh,客户端无需更新
        expires_in=_calc_expires_in(access_expire),
        user=UserPublic.model_validate(user),
    )


# ============================================================
# GET /api/v1/auth/me
# ============================================================

@router.get(
    "/auth/me",
    response_model=UserPublic,
    summary="查看当前登录用户信息",
)
async def me(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(jwt_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    """
    跟 deps.get_current_user 不一样:本端点强制要求 JWT(不走 dev fallback),
    用来给前端确认"我现在登录的是谁"。
    """
    token = _require_token(creds)
    try:
        user = AuthService(db).user_from_access_token(token)
    except TokenInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token 无效: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    return UserPublic.model_validate(user)
