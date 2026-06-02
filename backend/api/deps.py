"""
api/deps.py —— FastAPI 依赖注入

提供给 api/v1/*.py 端点的依赖注入函数:

| 依赖              | 用途                               | 备注 |
|-------------------|------------------------------------|------|
| get_db            | SQLAlchemy Session(每请求一个)     | 复用 core/database.py 的 get_db,re-export |
| get_current_user  | 鉴权,返回 user_id                  | JWT 优先,X-User-Id header 兜底(开关) |
| get_chat_service  | 注入 ChatService 实例              | 依赖 get_db |

鉴权策略(post-Phase B):
1. Authorization: Bearer <jwt> → 解 JWT,通过则 sub 即 user_id
2. JWT 无效但 settings.AUTH_DEV_HEADER_FALLBACK=true 且带 X-User-Id header → 用 header
3. 没 token 又没 header → 401

为什么保留 X-User-Id 兜底?
- 现存 80+ 集成测试用 X-User-Id 写,逐个改成签 JWT 工作量翻倍。
- 前端联调早期可以不签 JWT,先把 SSE / WS 调通。
- 生产部署在 .env 设 AUTH_DEV_HEADER_FALLBACK=false,自动变严格模式。

队伍:咕嘎一辈子队
修改者:咕嘎(Phase B)
修改日期:2026-06-02
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.api.middleware.auth import jwt_bearer
from backend.config import settings
from backend.core.database import get_db
from backend.core.exceptions import TokenInvalidError
from backend.repositories.user_repo import UserRepository
from backend.services.auth_service import AuthService
from backend.services.chat_service import ChatService


logger = logging.getLogger(__name__)


# ============================================================
# user_id 注入(JWT 优先,X-User-Id header 兜底)
# ============================================================

async def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(jwt_bearer)],
    db: Annotated[Session, Depends(get_db)],
    x_user_id: Annotated[Optional[str], Header(alias="X-User-Id")] = None,
) -> str:
    """
    返回当前请求的 user_id 字符串。

    [改造点 / Phase B]:
    - 之前: 只读 X-User-Id header
    - 现在: JWT 优先;无 token / token 无效时,若 AUTH_DEV_HEADER_FALLBACK=true 且带
            X-User-Id,回退用 header(让现有集成测试零改动通过)

    返回值仍是 str,跟改造前一致;调用方端点签名不需要改。
    """
    # ---- 1. 尝试 JWT ----
    if creds is not None and creds.credentials:
        try:
            user = AuthService(db).user_from_access_token(creds.credentials)
            return user.id
        except TokenInvalidError as e:
            # JWT 解码失败时,如果开了 dev fallback 且带 X-User-Id,允许降级
            if settings.AUTH_DEV_HEADER_FALLBACK and x_user_id:
                logger.warning(
                    "JWT invalid (%s) but dev fallback active; using X-User-Id=%s",
                    e,
                    x_user_id,
                )
                return _resolve_user_id_from_header(db, x_user_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"无效的 token: {e}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    # ---- 2. 无 JWT, 走 dev header fallback ----
    if settings.AUTH_DEV_HEADER_FALLBACK and x_user_id:
        return _resolve_user_id_from_header(db, x_user_id)

    # ---- 3. 都没有, 401 ----
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证: 缺少 Authorization Bearer token"
        + ("(或 X-User-Id header)" if settings.AUTH_DEV_HEADER_FALLBACK else ""),
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_user_id_from_header(db: Session, x_user_id: str) -> str:
    """
    dev fallback 路径:把 X-User-Id 当 user_id 使用。

    宽松策略(MVP 兼容):
    - 如果 header 值是已存在的 users.id → 直接通过
    - 不是,但 users 表里有同名 username → 拿对应 id
    - 都不是 → 当成 user_id 直接返回(允许测试场景捏造一个 ID,跟改造前行为一致)

    上线时把 AUTH_DEV_HEADER_FALLBACK 关掉,本函数永远不会被走到。
    """
    repo = UserRepository(db)
    if repo.get(x_user_id) is not None:
        return x_user_id
    by_username = repo.get_by_username(x_user_id)
    if by_username is not None:
        return by_username.id
    # 兼容旧测试:返回原始字符串,让上层业务自决定如何处理
    return x_user_id


# ============================================================
# ChatService 注入
# ============================================================

def get_chat_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChatService:
    """
    构造 ChatService 实例,session 由 get_db 注入(FastAPI 自动管理 session 生命周期)。

    ChatService 风格是"实例 + 注入 session",跟 thread_service 一致。
    每次请求一个新 ChatService 实例,session 由 FastAPI 在 yield 之后自动 close。
    """
    return ChatService(session=db)


# 导出符号
__all__ = [
    "get_db",
    "get_current_user",
    "get_chat_service",
]
