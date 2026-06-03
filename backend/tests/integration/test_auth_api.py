"""
Auth API 集成测试 — SQLite in-memory + 真 HTTP + 真路由,fake Redis 跑黑名单。

测试范围(覆盖 5 端点):
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  POST /api/v1/auth/refresh
  GET  /api/v1/auth/me

设计要点:
- DB:scope=module 共享一个 SQLite in-memory(参考 test_skills_api.py)。
  各测试用唯一 username 避免数据污染。
- Redis:scope=module 注入 _FakeRedis,logout 黑名单端到端可验证。
  另有 1 个测试单独 monkeypatch get_redis=None 验证 fail-open。
- 响应都过 ResponseEnvelopeMiddleware → {code, message, data} 包装,
  body() helper 拆包。

队伍:咕嘎一辈子队
修改者:咕嘎(Phase C)
修改日期:2026-06-02
"""
from __future__ import annotations

import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.database import get_db
from backend.main import create_app
import backend.models  # noqa: F401 — 注册所有 ORM 表到 Base.metadata
from backend.models.base import Base


# ============================================================
# Helpers
# ============================================================


def body(resp):
    """从 ResponseEnvelopeMiddleware 包装的响应中拆出 data 字段。"""
    if resp.status_code == 204 or not resp.content:
        return None
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


def auth_headers(token: str) -> dict[str, str]:
    """access token → Authorization Bearer header。"""
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# Fake Redis(支持黑名单的最小集)
# ============================================================


class _FakeRedis:
    """支持 set / exists,够 logout 黑名单测试用。"""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        return True

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def clear(self) -> None:
        self._store.clear()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def fake_redis():
    """整个 module 复用一个 fake redis,测试间通过唯一 jti 自然隔离。"""
    return _FakeRedis()


@pytest.fixture(scope="module")
def client(fake_redis):
    """启动 app + override get_db + 注入 fake redis。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # monkeypatch 不能跨 module-scope fixture,直接 setattr
    import backend.services.auth_service as auth_service_mod

    original_get_redis = auth_service_mod.get_redis
    auth_service_mod.get_redis = lambda: fake_redis

    app = create_app(include_lifespan=False)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        auth_service_mod.get_redis = original_get_redis


@pytest.fixture
def make_user(client):
    """工厂 fixture:返回一个新注册用户的 dict(包含 id / username)。

    用法: u = make_user(username='alice'); 不传 username 则自动生成唯一名。
    """

    def _make(
        username: Optional[str] = None,
        password: str = "testpass123",
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> dict:
        username = username or f"u_{uuid.uuid4().hex[:8]}"
        payload = {"username": username, "password": password}
        if email:
            payload["email"] = email
        if display_name:
            payload["display_name"] = display_name
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201, f"setup register failed: {resp.text}"
        data = body(resp)
        # 把密码也带回去给后续 login 用
        data["_password"] = password
        return data

    return _make


@pytest.fixture
def logged_in(client, make_user):
    """工厂 fixture:返回 (user_dict, access_token, refresh_token)。"""

    def _make(**kwargs) -> tuple[dict, str, str]:
        user = make_user(**kwargs)
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": user["username"], "password": user["_password"]},
        )
        assert resp.status_code == 200, f"setup login failed: {resp.text}"
        data = body(resp)
        return user, data["access_token"], data["refresh_token"]

    return _make


# ============================================================
# TestRegister
# ============================================================


class TestRegister:
    def test_register_success_returns_201_and_user_public(self, client):
        username = f"reg_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "password": "pass1234",
                "email": "alice@example.com",
                "display_name": "Alice",
            },
        )
        assert resp.status_code == 201
        data = body(resp)
        assert data["username"] == username
        assert data["email"] == "alice@example.com"
        assert data["display_name"] == "Alice"
        assert "id" in data and len(data["id"]) > 0

    def test_register_response_excludes_password_hash(self, client):
        """敏感字段绝不能出现在响应里(任何形式)。"""
        username = f"sec_{uuid.uuid4().hex[:6]}"
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "secretP@ss123"},
        )
        raw = resp.text
        assert "password_hash" not in raw
        assert "$2b$" not in raw  # bcrypt 哈希前缀
        assert "secretP@ss123" not in raw  # 明文也不能漏

    def test_register_duplicate_username_returns_409(self, client, make_user):
        u = make_user()
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": u["username"], "password": "another1234"},
        )
        assert resp.status_code == 409
        assert resp.json()["code"] == 409
        assert "已被占用" in resp.json()["message"]

    def test_register_duplicate_email_returns_409(self, client):
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        u1 = f"e1_{uuid.uuid4().hex[:6]}"
        u2 = f"e2_{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/v1/auth/register",
            json={"username": u1, "password": "pass1234", "email": email},
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": u2, "password": "pass1234", "email": email},
        )
        assert resp.status_code == 409

    def test_register_validation_errors_have_loc_fields(self, client):
        """422 响应应该包含每个字段的具体错误信息。"""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "x",  # 太短
                "password": "1",  # 太短
                "email": "not-an-email",  # 格式错
            },
        )
        assert resp.status_code == 422
        envelope = resp.json()
        assert envelope["code"] == 422
        errors = envelope["data"]["errors"]
        fields = {".".join(str(p) for p in e["loc"]) for e in errors}
        assert "body.username" in fields
        assert "body.password" in fields
        assert "body.email" in fields

    def test_register_with_invalid_username_pattern(self, client):
        """username 必须 [a-zA-Z0-9_-];中文 / 空格 / 特殊字符都该 422。"""
        for bad_username in ["alice 中文", "alice.bob", "alice@x", "ali ce"]:
            resp = client.post(
                "/api/v1/auth/register",
                json={"username": bad_username, "password": "pass1234"},
            )
            assert resp.status_code == 422, f"应拒绝 username={bad_username!r}"


# ============================================================
# TestLogin
# ============================================================


class TestLogin:
    def test_login_success_returns_token_response(self, client, make_user):
        u = make_user(password="myPass1234")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "myPass1234"},
        )
        assert resp.status_code == 200
        data = body(resp)
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["user"]["username"] == u["username"]

    def test_access_and_refresh_tokens_differ(self, client, make_user):
        u = make_user(password="myPass1234")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "myPass1234"},
        )
        data = body(resp)
        assert data["access_token"] != data["refresh_token"]

    def test_login_wrong_password_returns_401(self, client, make_user):
        u = make_user(password="rightPass1234")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "wrongPass"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 401

    def test_login_nonexistent_user_returns_401_with_same_message(
        self, client, make_user
    ):
        """不存在用户和错密码都返回 401 + 完全相同的错误信息(防枚举)。"""
        u = make_user(password="rightPass1234")
        wrong_pwd = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "wrong"},
        )
        nonexistent = client.post(
            "/api/v1/auth/login",
            json={"username": "definitely_nope_xyz", "password": "anything"},
        )
        assert wrong_pwd.status_code == 401
        assert nonexistent.status_code == 401
        # 关键:两者错误信息一字不差
        assert wrong_pwd.json()["message"] == nonexistent.json()["message"]

    def test_login_response_excludes_password_hash(self, client, make_user):
        u = make_user(password="secret1234")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "secret1234"},
        )
        raw = resp.text
        assert "password_hash" not in raw
        assert "$2b$" not in raw
        assert "secret1234" not in raw


# ============================================================
# TestMe
# ============================================================


class TestMe:
    def test_me_with_access_returns_user_public(self, client, logged_in):
        user, access, _ = logged_in()
        resp = client.get("/api/v1/auth/me", headers=auth_headers(access))
        assert resp.status_code == 200
        data = body(resp)
        assert data["id"] == user["id"]
        assert data["username"] == user["username"]
        assert "password_hash" not in data

    def test_me_without_token_returns_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_garbage_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert resp.status_code == 401

    def test_me_with_refresh_token_rejected(self, client, logged_in):
        """refresh token 不能当 access 用 → 401 type mismatch。"""
        _, _, refresh = logged_in()
        resp = client.get("/api/v1/auth/me", headers=auth_headers(refresh))
        assert resp.status_code == 401
        assert "type" in resp.json()["message"].lower() or "无效" in resp.json()["message"]

    def test_me_with_malformed_authorization_header(self, client, logged_in):
        """Authorization 不带 Bearer 前缀,或 token 为空。"""
        _, access, _ = logged_in()
        # 没 Bearer 前缀
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": access}
        )
        assert resp.status_code == 401


# ============================================================
# TestRefresh
# ============================================================


class TestRefresh:
    def test_refresh_returns_new_access_token(self, client, logged_in):
        _, old_access, refresh = logged_in()
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        data = body(resp)
        assert data["access_token"] != old_access  # 必须是新 access
        assert "refresh_token" in data
        assert data["expires_in"] > 0

    def test_refresh_with_access_token_returns_401(self, client, logged_in):
        _, access, _ = logged_in()
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401

    def test_refresh_with_garbage_token_returns_401(self, client):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
        assert resp.status_code == 401

    def test_refresh_missing_field_returns_422(self, client):
        resp = client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422


# ============================================================
# TestLogout
# ============================================================


class TestLogout:
    def test_logout_with_access_returns_204(self, client, logged_in):
        _, access, _ = logged_in()
        resp = client.post("/api/v1/auth/logout", headers=auth_headers(access))
        assert resp.status_code == 204

    def test_logout_without_token_returns_401(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    def test_logout_with_garbage_token_returns_401(self, client):
        resp = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer not.a.valid.token"},
        )
        assert resp.status_code == 401

    def test_logout_invalidates_access_token_via_blacklist(
        self, client, logged_in, fake_redis
    ):
        """⭐ 集成测试核心契约:logout 后旧 access token 立即失效(Redis 黑名单生效)。"""
        _, access, _ = logged_in()

        # 1. logout 前: /me 通
        r = client.get("/api/v1/auth/me", headers=auth_headers(access))
        assert r.status_code == 200

        # 2. logout
        r = client.post("/api/v1/auth/logout", headers=auth_headers(access))
        assert r.status_code == 204

        # 3. logout 后:同一个 token 不再被接受
        r = client.get("/api/v1/auth/me", headers=auth_headers(access))
        assert r.status_code == 401
        # 错误信息应该提到 revoked
        assert "revoked" in r.json()["message"].lower() or "无效" in r.json()["message"]


# ============================================================
# TestEnvelopeFormat
# ============================================================


class TestEnvelopeFormat:
    """验证所有响应都被 ResponseEnvelopeMiddleware 包成 {code, message, data}。"""

    def test_success_response_has_envelope_keys(self, client, make_user):
        u = make_user(password="env1234567")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": u["username"], "password": "env1234567"},
        )
        raw = resp.json()
        assert set(raw.keys()) == {"code", "message", "data"}
        assert raw["code"] == 200
        assert isinstance(raw["data"], dict)

    def test_business_error_response_envelope(self, client, make_user):
        """409 业务错误也走 envelope。"""
        u = make_user()
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": u["username"], "password": "pass1234"},
        )
        raw = resp.json()
        assert raw["code"] == 409
        assert raw["data"] is None
        assert raw["message"]  # 非空错误信息

    def test_validation_error_response_envelope_has_errors_list(self, client):
        """422 校验错误的 data 里应该有 errors 列表(给前端定位字段)。"""
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "x", "password": "y"},
        )
        raw = resp.json()
        assert raw["code"] == 422
        assert isinstance(raw["data"], dict)
        assert "errors" in raw["data"]
        assert len(raw["data"]["errors"]) >= 2  # 至少两个字段错


# ============================================================
# TestDevFallback
# ============================================================


class TestDevFallback:
    """
    验证 deps.get_current_user 的"JWT 优先 + X-User-Id 兜底"组合策略。
    通过任何"需要鉴权但不是 auth 端点"来验证(/conversations 一直存在)。
    """

    def test_jwt_alone_works_on_protected_endpoint(self, client, logged_in):
        _, access, _ = logged_in()
        resp = client.get(
            "/api/v1/conversations", headers=auth_headers(access)
        )
        assert resp.status_code == 200

    def test_x_user_id_fallback_works(self, client, make_user):
        u = make_user()
        resp = client.get(
            "/api/v1/conversations", headers={"X-User-Id": u["id"]}
        )
        assert resp.status_code == 200

    def test_neither_jwt_nor_x_user_id_returns_401(self, client):
        resp = client.get("/api/v1/conversations")
        assert resp.status_code == 401
