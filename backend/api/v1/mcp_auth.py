"""
api/v1/mcp_auth.py — MCP 服务器 OAuth/OIDC 授权端点

GET /api/v1/mcp-auth/{server_id}/start   启动授权（Client Credentials 立即完成，OIDC 返回 auth_url）
GET /api/v1/mcp-auth/callback             OIDC 回调（由 SAP IDP 重定向）
GET /api/v1/mcp-auth/status/{server_id}  查询授权状态

队伍：咕嘎一辈子队
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from backend.api.deps import get_current_user
from backend.services.mcp_token_service import mcp_token_service

router = APIRouter()


@router.get(
    "/mcp-auth/{server_id}/start",
    summary="启动 MCP 服务器授权",
)
async def mcp_auth_start(
    server_id: str,
    request: Request,
    user_id: Annotated[str, Depends(get_current_user)],
) -> dict:
    """
    Client Credentials 服务器：立即换 token，返回 {"status": "authorized"}。
    OIDC 服务器：生成 PKCE 授权 URL，返回 {"auth_url": str, "status": "pending"}。
    """
    from backend.services.mcp_token_service import _CLIENT_CREDENTIALS_SERVERS, _OIDC_SERVERS

    if server_id in _CLIENT_CREDENTIALS_SERVERS:
        token = await mcp_token_service.ensure_client_credentials_token(server_id)
        if token:
            return {"status": "authorized", "server_id": server_id}
        return {"status": "error", "server_id": server_id, "message": "Token fetch failed"}

    if server_id in _OIDC_SERVERS:
        # 构造回调 URL（指向服务器，不是本地浏览器）
        redirect_uri = str(request.base_url).rstrip("/") + "/api/v1/mcp-auth/callback"
        result = mcp_token_service.start_pkce_flow(server_id, user_id, redirect_uri)
        if result:
            return {"status": "pending", "server_id": server_id, "auth_url": result["auth_url"]}
        return {"status": "error", "message": "OIDC not configured for this server"}

    return {"status": "unknown", "server_id": server_id, "message": "Server not found in auth config"}


@router.get(
    "/mcp-auth/callback",
    summary="OIDC 回调（SAP IDP 重定向至此）",
    response_class=HTMLResponse,
)
async def mcp_auth_callback(
    request: Request,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    """
    SAP IDP 授权后回调。换 token 存 DB，返回关闭窗口的 HTML。
    """
    if error or not code or not state:
        msg = error or "missing code or state"
        return HTMLResponse(content=f"""
<html><body>
<p style="color:red">授权失败：{msg}</p>
<script>
  if(window.opener) window.opener.postMessage({{type:'mcp-auth-error',error:{repr(msg)}}}, '*');
  setTimeout(()=>window.close(), 3000);
</script>
</body></html>""")

    redirect_uri = str(request.base_url).rstrip("/") + "/api/v1/mcp-auth/callback"
    result = await mcp_token_service.complete_pkce_flow(state, code, redirect_uri)

    if not result:
        return HTMLResponse(content="""
<html><body>
<p style="color:red">Token 换取失败，请重试</p>
<script>
  if(window.opener) window.opener.postMessage({type:'mcp-auth-error',error:'token_exchange_failed'}, '*');
  setTimeout(()=>window.close(), 3000);
</script>
</body></html>""")

    return HTMLResponse(content="""
<html><body>
<p style="color:green">授权成功，此页面将自动关闭</p>
<script>
  if(window.opener) window.opener.postMessage({type:'mcp-auth-success'}, '*');
  window.close();
</script>
</body></html>""")


@router.get(
    "/mcp-auth/status/{server_id}",
    summary="查询 MCP 服务器授权状态",
)
async def mcp_auth_status(
    server_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
) -> dict:
    """返回 {"authorized": bool, "expires_at": str | null}"""
    status = await mcp_token_service.get_auth_status(server_id, user_id)
    return {"server_id": server_id, **status}
