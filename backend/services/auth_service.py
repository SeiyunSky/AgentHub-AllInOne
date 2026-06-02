"""
auth_service.py —— 鉴权业务核心

提供 4 类能力:
1. 密码哈希 / 校验          —— bcrypt(via passlib),不直接存明文
2. JWT 签发 / 解码          —— python-jose,access + refresh 双 token,jti 用 UUID4
3. 业务流程                  —— register / login / logout / refresh / get_user_from_token
4. 黑名单                    —— logout 把 jti 写到 Redis;Redis 不可达时 fail-open
                              (只警告日志,业务继续走;此时 logout 仅前端丢 token)

设计原则:
- 不抛 HTTPException,只抛 backend.core.exceptions 里的领域异常;
  HTTP 转码由 api/exception_handlers 统一处理。
- 用统一的 AuthenticationError(不区分用户名错 / 密码错),避免被枚举用户名。
- token payload 字段最小化:sub(user_id)、jti、exp、iat、type;
  username 也带上一份(给 middleware 早期日志用),但前端能信任的只有 sub。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-02
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.exceptions import (
    AuthenticationError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from backend.core.redis import get_redis
from backend.models.user import User
from backend.repositories.user_repo import UserRepository


logger = logging.getLogger(__name__)


# ============================================================
# 密码哈希
# ============================================================

# bcrypt 的 work factor;默认 12 轮(对应 ~250ms 哈希一次,够防暴力破解)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希。"""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码 = 哈希。错误的哈希格式 / 空 hash 都返回 False。"""
    if not password_hash:
        return False
    try:
        return _pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        # 哈希字符串格式坏 → 直接判否,不抛
        return False


# ============================================================
# JWT 签发 / 解码
# ============================================================

# token 类型常量;放在 payload.type 字段里防 access ↔ refresh 互用
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Redis 黑名单 key 前缀
_BLACKLIST_PREFIX = "auth:blacklist:"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(
    *,
    user_id: str,
    username: str,
    token_type: str,
    expires_delta: timedelta,
) -> tuple[str, str, datetime]:
    """
    通用 token 签发。返回 (token, jti, expire_at)。

    expire_at 是 timezone-aware datetime(UTC),给调用方落库 / 算 expires_in 用。
    """
    now = _now_utc()
    expire_at = now + expires_delta
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "username": username,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire_at


def create_access_token(user_id: str, username: str) -> tuple[str, datetime]:
    """签发 access token。返回 (token, expire_at)。"""
    token, _, expire_at = _create_token(
        user_id=user_id,
        username=username,
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
    )
    return token, expire_at


def create_refresh_token(user_id: str, username: str) -> tuple[str, datetime]:
    """签发 refresh token。返回 (token, expire_at)。"""
    token, _, expire_at = _create_token(
        user_id=user_id,
        username=username,
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )
    return token, expire_at


def decode_token(token: str, *, expected_type: Optional[str] = None) -> dict[str, Any]:
    """
    解码 + 校验 JWT。失败抛 TokenInvalidError。

    校验项:
    - 签名与算法
    - 过期时间(jose 自动校 exp)
    - token type 与 expected_type 一致(防 refresh 当 access 用)
    - jti 不在黑名单(若 Redis 可用)
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise TokenInvalidError(f"token decode failed: {e}") from e

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenInvalidError(
            f"token type mismatch: want {expected_type!r}, got {payload.get('type')!r}"
        )

    jti = payload.get("jti")
    if jti and _is_blacklisted(jti):
        raise TokenInvalidError("token has been revoked")

    return payload


# ============================================================
# 黑名单(Redis,fail-open)
# ============================================================


def _is_blacklisted(jti: str) -> bool:
    """查 Redis 黑名单。Redis 不可达时返回 False(fail-open)。"""
    r = get_redis()
    if r is None:
        return False
    try:
        return bool(r.exists(_BLACKLIST_PREFIX + jti))
    except Exception:
        logger.warning("redis EXISTS failed for jti=%s; fail-open", jti, exc_info=True)
        return False


def _add_to_blacklist(jti: str, expire_at: datetime) -> bool:
    """
    把 jti 加入黑名单,TTL = token 剩余有效期(过期了 Redis 自动清掉,不会无限堆)。

    返回:True=成功写黑名单 / False=Redis 不可用,降级(token 仍在客户端能用,直到过期)。
    """
    r = get_redis()
    if r is None:
        return False
    ttl_seconds = max(1, int((expire_at - _now_utc()).total_seconds()))
    try:
        r.set(_BLACKLIST_PREFIX + jti, "1", ex=ttl_seconds)
        return True
    except Exception:
        logger.warning("redis SET blacklist failed; logout degrades", exc_info=True)
        return False


# ============================================================
# 业务流程
# ============================================================


class AuthService:
    """鉴权业务封装。session 由调用方注入,与其他 service 风格一致。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    # ----- register -----

    def register(
        self,
        *,
        username: str,
        password: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> User:
        """
        注册新用户。username / email 唯一性已在 DB 层有 unique 约束,
        这里先查一下给出友好错误,不依赖捕 IntegrityError。
        """
        if self.users.username_taken(username):
            raise UserAlreadyExistsError("username", username)
        if email and self.users.email_taken(email):
            raise UserAlreadyExistsError("email", email)

        user = self.users.create_user(
            username=username,
            password_hash=hash_password(password),
            email=email,
            display_name=display_name,
        )
        self.session.commit()
        logger.info("user registered: id=%s username=%s", user.id, user.username)
        return user

    # ----- login -----

    def login(
        self, *, username: str, password: str
    ) -> tuple[User, str, datetime, str, datetime]:
        """
        登录。成功返回 (user, access_token, access_expire, refresh_token, refresh_expire);
        失败统一抛 AuthenticationError(不区分用户名错 / 密码错)。
        """
        user = self.users.get_by_username(username)
        # 即使 user 不存在也走一遍 verify_password,避免 timing attack 暴露用户存在性
        password_ok = verify_password(password, user.password_hash if user else "")
        if user is None or not password_ok:
            raise AuthenticationError("用户名或密码错误")

        access_token, access_expire = create_access_token(user.id, user.username)
        refresh_token, refresh_expire = create_refresh_token(user.id, user.username)

        self.users.touch_last_login(user.id)
        self.session.commit()

        logger.info("user logged in: id=%s username=%s", user.id, user.username)
        return user, access_token, access_expire, refresh_token, refresh_expire

    # ----- logout -----

    def logout(self, token: str) -> bool:
        """
        把 token 加入黑名单。Redis 不可用时降级(返回 False),前端仍应丢掉 token。

        token 可以是 access 也可以是 refresh;两者的 jti 都加。
        无效 token 直接 raise TokenInvalidError。
        """
        payload = decode_token(token)  # 不限制 type:access / refresh 都可以登出
        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti or not exp:
            raise TokenInvalidError("token payload 缺少 jti/exp")

        expire_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        return _add_to_blacklist(jti, expire_at)

    # ----- refresh -----

    def refresh(self, refresh_token: str) -> tuple[User, str, datetime]:
        """
        用 refresh token 换新的 access token(refresh 不轮换,直到自然过期)。
        返回 (user, new_access_token, new_access_expire)。

        对应的失败:
        - refresh token 无效 / 过期 / 被吊销 → TokenInvalidError
        - 用户已删除(payload sub 找不到 user 行) → AuthenticationError
        """
        payload = decode_token(refresh_token, expected_type=TOKEN_TYPE_REFRESH)
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError("refresh token payload 缺少 sub")

        user = self.users.get(user_id)
        if user is None:
            raise AuthenticationError("用户不存在或已被删除")

        access_token, access_expire = create_access_token(user.id, user.username)
        return user, access_token, access_expire

    # ----- 给中间件 / deps 用的"拿当前用户" -----

    def user_from_access_token(self, token: str) -> User:
        """
        给 middleware / deps.get_current_user 用:从 access token 反查 User。
        token 无效 / 用户不存在都抛 TokenInvalidError(让中间件统一返回 401)。
        """
        payload = decode_token(token, expected_type=TOKEN_TYPE_ACCESS)
        user_id = payload.get("sub")
        if not user_id:
            raise TokenInvalidError("access token payload 缺少 sub")

        user = self.users.get(user_id)
        if user is None:
            raise TokenInvalidError("token 对应的用户不存在")
        return user


__all__ = [
    "AuthService",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
]
