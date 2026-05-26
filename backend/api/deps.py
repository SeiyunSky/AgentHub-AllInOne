"""
api/deps.py —— FastAPI 依赖注入

提供给 api/v1/*.py 端点的依赖注入函数:

| 依赖              | 用途                               | 备注 |
|-------------------|------------------------------------|------|
| get_db            | SQLAlchemy Session(每请求一个)     | 复用 core/database.py 的 get_db,re-export |
| get_current_user  | 从请求拿 user_id                   | MVP 阶段读 X-User-Id header(auth 后续由专人接) |
| get_chat_service  | 注入 ChatService 实例              | 依赖 get_db |

鉴权约定:
- MVP 不做 JWT / session,只读 X-User-Id header 当作 user_id
- 没传 X-User-Id 时返回 401
- 真实鉴权由 auth_service / JWT 中间件后续实装(归专人负责),
  到时把本文件 get_current_user 改成解 JWT 即可,api 层调用方不需要改

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.chat_service import ChatService


# ============================================================
# user_id 注入(MVP:X-User-Id header)
# ============================================================

async def get_current_user(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    """
    从 X-User-Id header 拿 user_id。

    MVP 阶段无鉴权,客户端必须显式传 X-User-Id;没传 → 401。
    [TODO/auth]: auth_service / JWT 中间件落地后,本函数改成从 token claims 解 user_id,
    端点签名不变。
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-User-Id header(MVP 阶段必填,等 auth 接通后改用 JWT)",
        )
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
