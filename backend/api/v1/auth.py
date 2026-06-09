"""
api/v1/auth.py —— 鉴权端点

5 个本地鉴权端点(prefix /api/v1/auth):
- POST   /register   注册新用户
- POST   /login      用户名密码换 access + refresh token
- POST   /logout     吊销当前 access token(写 Redis 黑名单;Redis 不可用降级 no-op)
- POST   /refresh    用 refresh token 换新 access
- GET    /me         查看当前登录用户信息

2 个 Microsoft OAuth2 端点:
- GET    /oauth/microsoft            返回微软授权 URL(含 state,写 Redis 防 CSRF)
- GET    /oauth/microsoft/callback   接收 code,换 token,重定向前端并携带 JWT

错误约定:
- 用户名 / 密码错 → 401 (统一错误信息,防枚举用户名)
- token 无效 / 过期 / 被吊销 → 401
- 注册重名 → 409 Conflict
- 校验失败(短密码 / 非法 username) → 422(由 RequestValidationError 自动处理)
- OAuth 配置未填 → 501 Not Implemented
- OAuth state 校验失败 → 400

队伍:咕嘎一辈子队
修改者:咕嘎(Phase C)
修改日期:2026-06-08
"""

from __future__ import annotations

import logging
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.middleware.auth import jwt_bearer
from backend.config import settings
from backend.core.exceptions import (
    AuthenticationError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from backend.core.redis import get_redis
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
# Azure AD 常量
# ============================================================

_AZURE_AUTHORITY = "https://login.microsoftonline.com"
_AZURE_SCOPE = "openid profile email User.Read"
_OAUTH_STATE_PREFIX = "auth:oauth:state:"


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


# ============================================================
# OAuth2 工具函数
# ============================================================

def _check_oauth_configured() -> None:
    """检查 Azure OAuth2 配置是否填写,未填则 501。"""
    if not settings.AZURE_CLIENT_ID or not settings.AZURE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Microsoft OAuth2 未配置,请在 .env 中填写 AZURE_CLIENT_ID 和 AZURE_CLIENT_SECRET。",
        )


def _save_oauth_state(state: str) -> None:
    """把 state 写入 Redis,TTL = AZURE_OAUTH_STATE_TTL。Redis 不可用时降级(CSRF 防护失效,记录警告)。"""
    r = get_redis()
    if r is None:
        logger.warning("redis unavailable: oauth state not persisted, CSRF protection degraded")
        return
    try:
        r.set(_OAUTH_STATE_PREFIX + state, "1", ex=settings.AZURE_OAUTH_STATE_TTL)
    except Exception:
        logger.warning("redis SET oauth state failed; CSRF protection degraded", exc_info=True)


def _verify_and_consume_oauth_state(state: str) -> bool:
    """验证 state 存在并删除(一次性消费)。Redis 不可用时 fail-open(返回 True)。"""
    r = get_redis()
    if r is None:
        logger.warning("redis unavailable: oauth state not verified, fail-open")
        return True
    try:
        key = _OAUTH_STATE_PREFIX + state
        deleted = r.delete(key)
        return bool(deleted)
    except Exception:
        logger.warning("redis DELETE oauth state failed; fail-open", exc_info=True)
        return True


# ============================================================
# GET /api/v1/auth/oauth/microsoft
# ============================================================

@router.get(
    "/auth/oauth/microsoft",
    summary="获取微软 OAuth2 授权 URL",
)
async def microsoft_oauth_start() -> dict:
    """
    生成微软授权跳转 URL。前端收到后用 window.location.href 跳转。

    - state 随机生成,写 Redis(TTL 5min)防 CSRF
    - 未配置 AZURE_CLIENT_ID / SECRET 返回 501
    """
    _check_oauth_configured()

    state = uuid.uuid4().hex
    _save_oauth_state(state)

    params = {
        "client_id": settings.AZURE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "response_mode": "query",
        "scope": _AZURE_SCOPE,
        "state": state,
    }
    url = (
        f"{_AZURE_AUTHORITY}/{settings.AZURE_TENANT_ID}/oauth2/v2.0/authorize"
        f"?{urllib.parse.urlencode(params)}"
    )
    return {"url": url}


# ============================================================
# GET /api/v1/auth/oauth/microsoft/callback
# ============================================================

@router.get(
    "/auth/oauth/microsoft/callback",
    summary="微软 OAuth2 回调 — 换 token,重定向前端",
)
async def microsoft_oauth_callback(
    code: Annotated[Optional[str], Query()] = None,
    state: Annotated[Optional[str], Query()] = None,
    error: Annotated[Optional[str], Query()] = None,
    error_description: Annotated[Optional[str], Query()] = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    微软授权服务器回调此端点。

    成功路径:
    1. 校验 state 防 CSRF
    2. 用 code 向微软换 id_token + access_token
    3. 解析用户信息(email / oid / display_name)
    4. login_or_register_oauth → 拿到 JWT
    5. 重定向前端 /auth/microsoft/callback?access_token=...&refresh_token=...

    失败路径(微软返回 error,或 state 不匹配):
    → 重定向前端 /login?error=...
    """
    frontend_callback = "/auth/microsoft/callback"
    frontend_login = "/login"

    # 微软侧返回错误(用户拒绝授权等)
    if error:
        logger.warning("microsoft oauth error: %s - %s", error, error_description)
        params = urllib.parse.urlencode({"error": error_description or error})
        return RedirectResponse(url=f"{frontend_login}?{params}", status_code=302)

    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_login}?error=missing+code+or+state", status_code=302
        )

    # 校验 state
    if not _verify_and_consume_oauth_state(state):
        logger.warning("microsoft oauth: invalid or expired state=%s", state)
        return RedirectResponse(
            url=f"{frontend_login}?error=invalid+state", status_code=302
        )

    _check_oauth_configured()

    # 用 code 换 token
    token_url = f"{_AZURE_AUTHORITY}/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"
    token_data = {
        "client_id": settings.AZURE_CLIENT_ID,
        "client_secret": settings.AZURE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            token_resp = await client.post(token_url, data=token_data)
            token_resp.raise_for_status()
            token_json = token_resp.json()
        except Exception as exc:
            logger.error("microsoft token exchange failed: %s", exc, exc_info=True)
            return RedirectResponse(
                url=f"{frontend_login}?error=token+exchange+failed", status_code=302
            )

        ms_access_token = token_json.get("access_token")
        if not ms_access_token:
            return RedirectResponse(
                url=f"{frontend_login}?error=no+access+token", status_code=302
            )

        # 拿用户信息
        try:
            profile_resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {ms_access_token}"},
            )
            profile_resp.raise_for_status()
            profile = profile_resp.json()
        except Exception as exc:
            logger.error("microsoft graph /me failed: %s", exc, exc_info=True)
            return RedirectResponse(
                url=f"{frontend_login}?error=profile+fetch+failed", status_code=302
            )

    # 提取关键字段
    oid: str = profile.get("id") or profile.get("oid", "")
    email: Optional[str] = profile.get("mail") or profile.get("userPrincipalName")
    display_name: Optional[str] = profile.get("displayName")
    tenant_id: Optional[str] = token_json.get("tid")  # id_token 中的 tid

    if not oid:
        return RedirectResponse(
            url=f"{frontend_login}?error=no+user+id", status_code=302
        )

    # 登录/注册
    try:
        user, access_token, access_expire, refresh_token, _ = AuthService(
            db
        ).login_or_register_oauth(
            provider="microsoft",
            subject=oid,
            email=email,
            display_name=display_name,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("login_or_register_oauth failed: %s", exc, exc_info=True)
        return RedirectResponse(
            url=f"{frontend_login}?error=login+failed", status_code=302
        )

    # 重定向前端,携带 JWT
    params = urllib.parse.urlencode(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": _calc_expires_in(access_expire),
            "username": user.username,
            "display_name": user.display_name or user.username,
        }
    )
    return RedirectResponse(url=f"{frontend_callback}?{params}", status_code=302)
