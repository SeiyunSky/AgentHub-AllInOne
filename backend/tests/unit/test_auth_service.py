"""
Unit tests for backend.services.auth_service.

测试范围(28 用例,五组):
  1. 密码哈希 / 校验          (4)
  2. JWT 签发                 (5)
  3. JWT 解码 / 校验          (6)
  4. Redis 黑名单(fake redis) (5)
  5. AuthService 业务流(in-mem)(8)

使用 SQLite in-memory 跑业务流测试,完全不依赖 MariaDB / Redis。
Redis 黑名单通过 monkeypatch backend.core.redis.get_redis 注入 fake 客户端。

队伍:咕嘎一辈子队
修改者:咕嘎(Phase C)
修改日期:2026-06-02
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models  # noqa: F401 — 注册所有 ORM 表到 Base.metadata
from backend.config import settings
from backend.core.exceptions import (
    AuthenticationError,
    TokenInvalidError,
    UserAlreadyExistsError,
)
from backend.models.base import Base
from backend.services.auth_service import (
    AuthService,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    _add_to_blacklist,
    _is_blacklisted,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ============================================================
# 共用 fixture
# ============================================================


@pytest.fixture
def db_session():
    """每个测试一个干净的 SQLite in-memory DB,所有表已建好。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def auth_svc(db_session):
    return AuthService(db_session)


# ============================================================
# 第 1 组:密码哈希 / 校验
# ============================================================


class TestPasswordHash:
    def test_hash_then_verify_succeeds(self):
        h = hash_password("password123")
        assert verify_password("password123", h) is True

    def test_same_password_different_hash(self):
        """bcrypt 自带盐:同一密码两次哈希应不相等。"""
        h1 = hash_password("password123")
        h2 = hash_password("password123")
        assert h1 != h2
        # 但都能 verify 回来
        assert verify_password("password123", h1)
        assert verify_password("password123", h2)

    def test_wrong_password_fails(self):
        h = hash_password("correct_password")
        assert verify_password("wrong_password", h) is False

    def test_empty_or_garbage_hash_returns_false(self):
        """空 hash / 格式坏的 hash 不能崩,直接判否。"""
        assert verify_password("any", "") is False
        assert verify_password("any", "not_a_bcrypt_hash") is False
        assert verify_password("any", None) is False  # type: ignore[arg-type]


# ============================================================
# 第 2 组:JWT 签发
# ============================================================


class TestTokenCreation:
    def test_access_token_returns_str_and_aware_datetime(self):
        token, expire_at = create_access_token("u-1", "alice")
        assert isinstance(token, str) and token.count(".") == 2
        assert expire_at.tzinfo is not None  # aware UTC
        assert expire_at > datetime.now(timezone.utc)

    def test_refresh_token_lifetime_longer_than_access(self):
        _, access_exp = create_access_token("u-1", "alice")
        _, refresh_exp = create_refresh_token("u-1", "alice")
        assert refresh_exp > access_exp

    def test_two_tokens_have_different_jti(self):
        """每次签 token 都应该有独一无二的 jti(给黑名单用)。"""
        t1, _ = create_access_token("u-1", "alice")
        t2, _ = create_access_token("u-1", "alice")
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]
        assert p1["sub"] == p2["sub"] == "u-1"

    def test_payload_contains_required_fields(self):
        token, _ = create_access_token("u-42", "bob")
        payload = decode_token(token)
        for key in ("sub", "username", "type", "jti", "iat", "exp"):
            assert key in payload, f"payload missing field {key!r}"
        assert payload["sub"] == "u-42"
        assert payload["username"] == "bob"
        assert payload["type"] == TOKEN_TYPE_ACCESS

    def test_access_and_refresh_have_different_type(self):
        a, _ = create_access_token("u-1", "alice")
        r, _ = create_refresh_token("u-1", "alice")
        assert decode_token(a)["type"] == TOKEN_TYPE_ACCESS
        assert decode_token(r)["type"] == TOKEN_TYPE_REFRESH


# ============================================================
# 第 3 组:JWT 解码 / 校验
# ============================================================


class TestTokenDecoding:
    def test_garbage_token_raises(self):
        with pytest.raises(TokenInvalidError):
            decode_token("not.a.real.token")

    def test_empty_token_raises(self):
        with pytest.raises(TokenInvalidError):
            decode_token("")

    def test_type_mismatch_rejected(self):
        """access 当 refresh 用,refresh 当 access 用,都该拒绝。"""
        access, _ = create_access_token("u-1", "alice")
        refresh, _ = create_refresh_token("u-1", "alice")

        with pytest.raises(TokenInvalidError, match="type mismatch"):
            decode_token(access, expected_type=TOKEN_TYPE_REFRESH)
        with pytest.raises(TokenInvalidError, match="type mismatch"):
            decode_token(refresh, expected_type=TOKEN_TYPE_ACCESS)

    def test_no_expected_type_accepts_both(self):
        """logout 路径不限定 type,access 和 refresh 都允许。"""
        access, _ = create_access_token("u-1", "alice")
        refresh, _ = create_refresh_token("u-1", "alice")
        assert decode_token(access)["type"] == TOKEN_TYPE_ACCESS
        assert decode_token(refresh)["type"] == TOKEN_TYPE_REFRESH

    def test_expired_token_raises(self, monkeypatch):
        """模拟 access token 已过期。靠 monkeypatch JWT_ACCESS_EXPIRE_MINUTES = -1。"""
        monkeypatch.setattr(settings, "JWT_ACCESS_EXPIRE_MINUTES", -1)
        token, _ = create_access_token("u-1", "alice")
        with pytest.raises(TokenInvalidError):
            decode_token(token)

    def test_tampered_signature_rejected(self):
        """伪造 token 的签名段会被拒绝。"""
        token, _ = create_access_token("u-1", "alice")
        head, payload, _signature = token.split(".")
        tampered = f"{head}.{payload}.deadbeefdeadbeefdeadbeefdeadbeef"
        with pytest.raises(TokenInvalidError):
            decode_token(tampered)


# ============================================================
# 第 4 组:Redis 黑名单(fake)
# ============================================================


class _FakeRedis:
    """最小可用 Redis mock:支持 set / exists / 模拟连接异常。"""

    def __init__(self, *, raise_on_set: bool = False, raise_on_exists: bool = False):
        self._store: dict[str, str] = {}
        self.raise_on_set = raise_on_set
        self.raise_on_exists = raise_on_exists

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if self.raise_on_set:
            raise ConnectionError("simulated redis down")
        self._store[key] = value
        return True

    def exists(self, key: str) -> int:
        if self.raise_on_exists:
            raise ConnectionError("simulated redis down")
        return 1 if key in self._store else 0


class TestBlacklist:
    def test_blacklist_no_redis_returns_false_silent(self, monkeypatch):
        """未配置 Redis 时,加黑名单和查黑名单都安静地降级为 false。"""
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: None)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert _add_to_blacklist("jti-x", future) is False
        assert _is_blacklisted("jti-x") is False

    def test_blacklist_writes_and_reads(self, monkeypatch):
        """正常路径:写黑名单后查得到。"""
        fake = _FakeRedis()
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: fake)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert _add_to_blacklist("jti-1", future) is True
        assert _is_blacklisted("jti-1") is True
        assert _is_blacklisted("jti-other") is False

    def test_blacklist_set_failure_returns_false(self, monkeypatch):
        """Redis 写失败时降级 fail-open(返回 False,不抛)。"""
        fake = _FakeRedis(raise_on_set=True)
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: fake)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert _add_to_blacklist("jti-x", future) is False

    def test_blacklist_check_failure_returns_false(self, monkeypatch):
        """Redis 查失败时也 fail-open(允许通过,不阻塞业务)。"""
        fake = _FakeRedis(raise_on_exists=True)
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: fake)
        assert _is_blacklisted("any-jti") is False

    def test_blacklisted_token_decode_rejected(self, monkeypatch):
        """token 加入黑名单后,decode_token 拒绝放行。"""
        fake = _FakeRedis()
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: fake)
        token, expire_at = create_access_token("u-1", "alice")
        jti = decode_token(token)["jti"]  # 此时还没在黑名单,能解
        _add_to_blacklist(jti, expire_at)
        with pytest.raises(TokenInvalidError, match="revoked"):
            decode_token(token)


# ============================================================
# 第 5 组:AuthService 业务流
# ============================================================


class TestAuthServiceBusiness:
    def test_register_creates_user(self, auth_svc):
        user = auth_svc.register(username="alice", password="pass1234", email="a@x.com", display_name="A")
        assert user.id is not None
        assert user.username == "alice"
        assert user.password_hash != "pass1234"  # 不存明文
        assert user.password_hash.startswith("$2")  # bcrypt 前缀
        assert user.display_name == "A"

    def test_register_default_display_name_falls_back_to_username(self, auth_svc):
        user = auth_svc.register(username="bob", password="pass1234")
        assert user.display_name == "bob"

    def test_register_duplicate_username(self, auth_svc):
        auth_svc.register(username="alice", password="pass1234")
        with pytest.raises(UserAlreadyExistsError) as exc:
            auth_svc.register(username="alice", password="pass5678")
        assert exc.value.field == "username"

    def test_register_duplicate_email(self, auth_svc):
        auth_svc.register(username="alice", password="pass1234", email="dup@x.com")
        with pytest.raises(UserAlreadyExistsError) as exc:
            auth_svc.register(username="bob", password="pass5678", email="dup@x.com")
        assert exc.value.field == "email"

    def test_login_success_returns_tokens_and_touches_last_login(self, auth_svc):
        user = auth_svc.register(username="alice", password="secret123")
        assert user.last_login_at is None

        u, access, _, refresh, _ = auth_svc.login(username="alice", password="secret123")

        assert u.id == user.id
        assert isinstance(access, str) and access.count(".") == 2
        assert isinstance(refresh, str) and refresh.count(".") == 2
        assert decode_token(access, expected_type=TOKEN_TYPE_ACCESS)["sub"] == user.id

        # last_login_at 已被刷新
        from backend.repositories.user_repo import UserRepository
        refreshed = UserRepository(auth_svc.session).get(user.id)
        assert refreshed.last_login_at is not None

    def test_login_wrong_password_raises(self, auth_svc):
        auth_svc.register(username="alice", password="secret123")
        with pytest.raises(AuthenticationError):
            auth_svc.login(username="alice", password="wrong")

    def test_login_nonexistent_user_raises_same_error(self, auth_svc):
        """不存在的用户和错密码抛同一种异常,防枚举。"""
        with pytest.raises(AuthenticationError):
            auth_svc.login(username="nobody", password="anything")

    def test_refresh_returns_new_access_keeps_user(self, auth_svc):
        user = auth_svc.register(username="alice", password="secret123")
        _, _, _, refresh, _ = auth_svc.login(username="alice", password="secret123")

        u, new_access, _ = auth_svc.refresh(refresh)
        assert u.id == user.id
        assert decode_token(new_access, expected_type=TOKEN_TYPE_ACCESS)["sub"] == user.id

    def test_refresh_with_access_token_rejected(self, auth_svc):
        auth_svc.register(username="alice", password="secret123")
        _, access, _, _, _ = auth_svc.login(username="alice", password="secret123")
        with pytest.raises(TokenInvalidError):
            auth_svc.refresh(access)  # access 不能当 refresh

    def test_user_from_access_token_resolves_user(self, auth_svc):
        user = auth_svc.register(username="alice", password="secret123")
        _, access, _, _, _ = auth_svc.login(username="alice", password="secret123")
        u = auth_svc.user_from_access_token(access)
        assert u.id == user.id

    def test_user_from_access_token_rejects_refresh(self, auth_svc):
        auth_svc.register(username="alice", password="secret123")
        _, _, _, refresh, _ = auth_svc.login(username="alice", password="secret123")
        with pytest.raises(TokenInvalidError):
            auth_svc.user_from_access_token(refresh)

    def test_user_from_access_token_user_deleted(self, auth_svc):
        """token 还有效但用户已被删,应该 401(TokenInvalidError),不要 500。"""
        user = auth_svc.register(username="alice", password="secret123")
        _, access, _, _, _ = auth_svc.login(username="alice", password="secret123")

        # 删掉用户
        from backend.repositories.user_repo import UserRepository
        UserRepository(auth_svc.session).delete(user.id)
        auth_svc.session.commit()

        with pytest.raises(TokenInvalidError, match="不存在"):
            auth_svc.user_from_access_token(access)

    def test_logout_no_redis_returns_false(self, auth_svc, monkeypatch):
        """无 Redis 时 logout 不抛错,返回 False(降级)。"""
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: None)
        auth_svc.register(username="alice", password="secret123")
        _, access, _, _, _ = auth_svc.login(username="alice", password="secret123")
        assert auth_svc.logout(access) is False

    def test_logout_with_fake_redis_blacklists_token(self, auth_svc, monkeypatch):
        """有 Redis 时 logout 把 jti 写进黑名单,后续 decode 被拒。"""
        fake = _FakeRedis()
        monkeypatch.setattr("backend.services.auth_service.get_redis", lambda: fake)

        auth_svc.register(username="alice", password="secret123")
        _, access, _, _, _ = auth_svc.login(username="alice", password="secret123")

        assert auth_svc.logout(access) is True
        with pytest.raises(TokenInvalidError, match="revoked"):
            auth_svc.user_from_access_token(access)

    def test_logout_invalid_token_raises(self, auth_svc):
        with pytest.raises(TokenInvalidError):
            auth_svc.logout("garbage.token.here")
