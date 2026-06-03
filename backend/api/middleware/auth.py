"""
api/middleware/auth.py —— JWT 鉴权辅助

提供两个工具,供 api/deps.py 组合使用:

1. JWTBearer  —— FastAPI HTTPBearer 子类,声明在端点上 / 依赖里就能从 Authorization
                 header 抽出 Bearer token。可选(auto_error=False),让 deps 层决定怎么
                 处理"没带 token"的情况(走 dev fallback 还是直接 401)。
2. extract_token_from_request(request) —— 不走依赖,从 Request 直接抠 token;给
                 WebSocket / SSE 这类不能挂依赖的路径备用。

注意:本文件不直接 raise 401。401 / 403 都由 api/deps.py:get_current_user 抛 HTTPException,
让"未带 token"和"token 无效"两种 401 走同一处理逻辑、统一被 envelope 包装。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-02
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class JWTBearer(HTTPBearer):
    """
    HTTPBearer 子类,关掉 auto_error,让 deps 层决定 401 时机。

    用法:
        bearer = JWTBearer()

        async def get_current_user(
            creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
            ...
        ): ...

    返回值:
    - HTTPAuthorizationCredentials 实例(scheme="Bearer", credentials="<token>")
    - None,当请求没带 Authorization header 或不是 Bearer 类型
    """

    def __init__(self) -> None:
        # auto_error=False:没带 header 也不立刻 raise,留给 deps 层处理 dev fallback
        super().__init__(auto_error=False, bearerFormat="JWT")


# 进程级共享实例;FastAPI 依赖的对象身份要稳定才能命中缓存
jwt_bearer = JWTBearer()


def extract_token_from_request(request: Request) -> Optional[str]:
    """
    从 Request 手抠 Bearer token。供 SSE / WebSocket 这种不挂依赖的路径用。

    优先级:
    1. Authorization: Bearer <token>      标准
    2. ?token=<token>                     query 兜底(给浏览器 EventSource 用,它不能加自定义 header)
    """
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()

    # query 兜底(SSE / EventSource 走这条)
    token = request.query_params.get("token")
    if token:
        return token.strip() or None
    return None


__all__ = ["JWTBearer", "jwt_bearer", "extract_token_from_request"]
