"""
MCPTokenService — MCP 服务器 OAuth/OIDC token 管理

支持两种授权模式：
1. Client Credentials（自动）：sap-mcp-glorepo / solution-patterns
   - 使用 client_id + secret 自动换 token，存入 mcp_tokens 表
   - user_id 用 "GUGA"（系统级共用）
2. OIDC PKCE（需用户浏览器登录）：globalization-taxonomy / spec-to-code
   - 生成授权 URL + PKCE challenge，state 存 Redis
   - 用户登录后 callback 换 token，存入 mcp_tokens（关联实际 user_id）

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from backend.core.utils import gen_uuid

logger = logging.getLogger(__name__)

# ============================================================
# SAP IDP 参数（从环境变量读取，避免硬编码敏感信息）
# ============================================================

_SAP_OAUTH_BASE = os.environ.get("SAP_OAUTH_BASE", "")
_SAP_TOKEN_URL  = f"{_SAP_OAUTH_BASE}/oauth2/token"
_SAP_AUTH_URL   = f"{_SAP_OAUTH_BASE}/oauth2/authorize"

# Client Credentials：机器对机器，无需用户授权
_CLIENT_CREDENTIALS_SERVERS: dict[str, dict] = {
    "l2a-sap-mcp-glorepo": {
        "client_id":     os.environ.get("L2A_GLOREPO_CLIENT_ID", ""),
        "client_secret": os.environ.get("L2A_GLOREPO_CLIENT_SECRET", ""),
    },
    "l2a-solution-patterns": {
        "client_id":     os.environ.get("L2A_SOLUTION_PATTERNS_CLIENT_ID", ""),
        "client_secret": os.environ.get("L2A_SOLUTION_PATTERNS_CLIENT_SECRET", ""),
    },
}

# OIDC PKCE：需要用户浏览器登录
# client_id 需向 L2A 团队申请；此处预留占位符
# 临时方案：从环境变量读取静态 token
_OIDC_SERVERS: dict[str, dict] = {
    "l2a-globalization-taxonomy": {
        "client_id": os.environ.get("L2A_TAXONOMY_CLIENT_ID", ""),
        "env_token": "L2A_TAXONOMY_TOKEN",
    },
    "l2a-solution-patterns": {
        "client_id": os.environ.get("L2A_SOLUTION_PATTERNS_CLIENT_ID", ""),
        "env_token": "L2A_SOLUTION_PATTERNS_TOKEN",
    },
    "l2a-test-case-creator": {
        "client_id": os.environ.get("L2A_TEST_CASE_CLIENT_ID", ""),
        "env_token": "L2A_TEST_CASE_TOKEN",
    },
}

_SYSTEM_USER_ID = "GUGA"

# Redis key 前缀
_PKCE_STATE_PREFIX = "mcp:pkce:state:"
_PKCE_STATE_TTL    = 600  # 10 分钟


class MCPTokenService:
    """MCP token 管理服务。每次调用自起短事务，不依赖外部 session 注入。"""

    # --------------------------------------------------------
    # 公共接口
    # --------------------------------------------------------

    async def get_token(self, server_id: str, user_id: str) -> Optional[str]:
        """
        获取有效 token。优先查 DB，过期则尝试自动刷新（Client Credentials）。
        OIDC 服务器过期后返回 None，需用户重新授权。
        """
        # 先看 DB
        token_row = self._load_token(server_id, user_id)
        if token_row is None and server_id in _CLIENT_CREDENTIALS_SERVERS:
            # Client Credentials：user_id 退回系统用户
            token_row = self._load_token(server_id, _SYSTEM_USER_ID)

        if token_row is not None:
            now = datetime.now(timezone.utc)
            if token_row.expires_at > now + timedelta(seconds=30):
                return token_row.access_token
            # 过期了：Client Credentials 自动刷，OIDC 返回 None
            if server_id in _CLIENT_CREDENTIALS_SERVERS:
                return await self.ensure_client_credentials_token(server_id, _SYSTEM_USER_ID)
            return None

        # DB 没有：Client Credentials 现场换
        if server_id in _CLIENT_CREDENTIALS_SERVERS:
            return await self.ensure_client_credentials_token(server_id, _SYSTEM_USER_ID)

        # OIDC 静态 token fallback
        env_key = _OIDC_SERVERS.get(server_id, {}).get("env_token")
        if env_key:
            return os.environ.get(env_key) or None

        return None

    async def get_auth_status(self, server_id: str, user_id: str) -> dict:
        """前端查询授权状态：{"authorized": bool, "expires_at": str | null}"""
        token_row = self._load_token(server_id, user_id)
        if token_row is None and server_id in _CLIENT_CREDENTIALS_SERVERS:
            token_row = self._load_token(server_id, _SYSTEM_USER_ID)

        if token_row is None:
            # OIDC 静态 fallback
            env_key = _OIDC_SERVERS.get(server_id, {}).get("env_token")
            if env_key and os.environ.get(env_key):
                return {"authorized": True, "expires_at": None, "mode": "static_env"}
            return {"authorized": False, "expires_at": None}

        now = datetime.now(timezone.utc)
        authorized = token_row.expires_at > now
        return {
            "authorized": authorized,
            "expires_at": token_row.expires_at.isoformat() if token_row.expires_at else None,
        }

    # --------------------------------------------------------
    # Client Credentials
    # --------------------------------------------------------

    async def ensure_client_credentials_token(
        self, server_id: str, user_id: str = _SYSTEM_USER_ID
    ) -> Optional[str]:
        """自动换取 Client Credentials token 并存 DB。"""
        cfg = _CLIENT_CREDENTIALS_SERVERS.get(server_id)
        if not cfg:
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _SAP_TOKEN_URL,
                    data={
                        "grant_type":    "client_credentials",
                        "client_id":     cfg["client_id"],
                        "client_secret": cfg["client_secret"],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("Client Credentials token fetch failed for %s: %s", server_id, exc)
            return None

        access_token = data.get("access_token")
        expires_in   = int(data.get("expires_in", 3600))
        if not access_token:
            logger.error("Client Credentials response missing access_token for %s", server_id)
            return None

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        self._upsert_token(server_id, user_id, access_token, expires_at)
        logger.info("Client Credentials token refreshed for %s, expires_in=%d", server_id, expires_in)
        return access_token

    async def prefetch_client_credentials_tokens(self) -> None:
        """启动时预取所有 Client Credentials token（main.py lifespan 调用）。"""
        for server_id in _CLIENT_CREDENTIALS_SERVERS:
            token = await self.ensure_client_credentials_token(server_id)
            if token:
                logger.info("prefetch_client_credentials: %s token OK", server_id)
            else:
                logger.warning("prefetch_client_credentials: %s token FAILED", server_id)

    # --------------------------------------------------------
    # OIDC PKCE
    # --------------------------------------------------------

    def start_pkce_flow(self, server_id: str, user_id: str, redirect_uri: str) -> Optional[dict]:
        """
        生成 PKCE 授权 URL + state，state 存 Redis。
        返回 {"auth_url": str, "state": str}，或 None（server 不支持 OIDC）。
        """
        cfg = _OIDC_SERVERS.get(server_id)
        if not cfg or not cfg.get("client_id"):
            return None

        state         = secrets.token_hex(24)
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .decode()
            .rstrip("=")
        )

        # 把 code_verifier + user_id 存 Redis（state 是 key）
        from backend.core.redis import get_redis
        r = get_redis()
        if r is not None:
            import json
            r.set(
                _PKCE_STATE_PREFIX + state,
                json.dumps({"code_verifier": code_verifier, "user_id": user_id, "server_id": server_id}),
                ex=_PKCE_STATE_TTL,
            )

        params = urllib.parse.urlencode({
            "response_type":         "code",
            "client_id":             cfg["client_id"],
            "redirect_uri":          redirect_uri,
            "scope":                 "openid",
            "state":                 state,
            "code_challenge":        code_challenge,
            "code_challenge_method": "S256",
        })
        auth_url = f"{_SAP_AUTH_URL}?{params}"
        return {"auth_url": auth_url, "state": state}

    async def complete_pkce_flow(
        self, state: str, code: str, redirect_uri: str
    ) -> Optional[tuple[str, str]]:
        """
        PKCE 第二步：用 code + code_verifier 换 token。
        返回 (access_token, user_id) 或 None。
        """
        from backend.core.redis import get_redis
        import json

        r = get_redis()
        if r is None:
            logger.error("PKCE complete: Redis unavailable, cannot retrieve state")
            return None

        raw = r.get(_PKCE_STATE_PREFIX + state)
        if not raw:
            logger.warning("PKCE complete: state=%s not found or expired", state)
            return None
        r.delete(_PKCE_STATE_PREFIX + state)

        try:
            payload = json.loads(raw)
        except Exception:
            return None

        code_verifier = payload.get("code_verifier", "")
        user_id       = payload.get("user_id", "")
        server_id     = payload.get("server_id", "")

        cfg = _OIDC_SERVERS.get(server_id)
        if not cfg:
            return None

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    _SAP_TOKEN_URL,
                    data={
                        "grant_type":    "authorization_code",
                        "client_id":     cfg["client_id"],
                        "code":          code,
                        "redirect_uri":  redirect_uri,
                        "code_verifier": code_verifier,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("PKCE token exchange failed for %s: %s", server_id, exc)
            return None

        access_token = data.get("access_token")
        expires_in   = int(data.get("expires_in", 3600))
        if not access_token:
            return None

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        self._upsert_token(server_id, user_id, access_token, expires_at)
        logger.info("PKCE token stored for server=%s user=%s", server_id, user_id)
        return (access_token, user_id)

    # --------------------------------------------------------
    # DB 操作
    # --------------------------------------------------------

    def _load_token(self, server_id: str, user_id: str):
        from backend.core.database import SessionLocal
        from backend.models.mcp_token import MCPToken
        with SessionLocal() as s:
            return (
                s.query(MCPToken)
                .filter_by(server_id=server_id, user_id=user_id)
                .first()
            )

    def _upsert_token(
        self, server_id: str, user_id: str, access_token: str, expires_at: datetime
    ) -> None:
        from backend.core.database import SessionLocal
        from backend.models.mcp_token import MCPToken
        with SessionLocal() as s:
            row = s.query(MCPToken).filter_by(server_id=server_id, user_id=user_id).first()
            if row:
                row.access_token = access_token
                row.expires_at   = expires_at
            else:
                s.add(MCPToken(
                    id=gen_uuid(),
                    user_id=user_id,
                    server_id=server_id,
                    access_token=access_token,
                    expires_at=expires_at,
                ))
            s.commit()


# 模块级单例
mcp_token_service = MCPTokenService()
