"""
Skills API 集成测试 — SQLite in-memory，不依赖真实文件系统（mock 文件 IO）。

测试范围：
  GET    /api/v1/skills          列表
  POST   /api/v1/skills          创建
  GET    /api/v1/skills/{id}     详情（含正文）
  PATCH  /api/v1/skills/{id}     更新
  DELETE /api/v1/skills/{id}     删除

Skill 的正文存文件，测试中 mock _write_skill_file / _read_skill_content 避免
真实文件 IO。

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.database import get_db
from backend.main import create_app
import backend.models  # noqa: F401 — 确保所有 ORM 模型注册到 Base.metadata
from backend.models.base import Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
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

    app = create_app(include_lifespan=False)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


@pytest.fixture
def skill_payload():
    return {
        "name": "test_skill",
        "display_name": "Test Skill",
        "description": "A skill for testing",
        "category": "test",
        "content": "# Test Skill\n\nThis is a test skill.",
        "is_public": False,
    }


# ---------------------------------------------------------------------------
# mock 文件 IO helpers
# ---------------------------------------------------------------------------

def _patch_skill_io():
    """mock Path.write_text，避免 create/update 时写入真实文件系统。"""
    return patch("pathlib.Path.write_text", return_value=None)


def _patch_skill_read(content: str = "# skill content"):
    """mock _read_content 返回固定内容。"""
    from backend.schemas.skill import SkillWithContent

    def _mock_read(self, skill):
        return SkillWithContent(
            id=skill.id,
            name=skill.name,
            display_name=skill.display_name,
            description=skill.description,
            category=skill.category,
            author_id=skill.author_id,
            is_public=bool(skill.is_public),
            is_active=bool(skill.is_active),
            content=content,
        )

    return patch(
        "backend.services.skill_service.SkillService._read_content",
        new=_mock_read,
    )


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

def test_list_skills_empty(client):
    resp = client.get("/api/v1/skills")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_skill(client, skill_payload):
    with _patch_skill_io(), _patch_skill_read(skill_payload["content"]):
        resp = client.post("/api/v1/skills", json=skill_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == skill_payload["name"]
    assert data["content"] == skill_payload["content"]
    assert "id" in data


def test_create_skill_duplicate_name(client, skill_payload):
    with _patch_skill_io(), _patch_skill_read():
        client.post("/api/v1/skills", json=skill_payload)
        resp = client.post("/api/v1/skills", json=skill_payload)
    assert resp.status_code == 409


def test_get_skill(client, skill_payload):
    unique_payload = {**skill_payload, "name": "get_test_skill"}
    with _patch_skill_io(), _patch_skill_read(unique_payload["content"]):
        create_resp = client.post("/api/v1/skills", json=unique_payload)
        skill_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/skills/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == skill_id


def test_get_skill_not_found(client):
    with _patch_skill_read():
        resp = client.get("/api/v1/skills/nonexistent-id")
    assert resp.status_code == 404


def test_update_skill(client, skill_payload):
    unique_payload = {**skill_payload, "name": "update_test_skill"}
    with _patch_skill_io(), _patch_skill_read():
        create_resp = client.post("/api/v1/skills", json=unique_payload)
        skill_id = create_resp.json()["id"]

    with _patch_skill_io(), _patch_skill_read("# updated content"):
        resp = client.patch(
            f"/api/v1/skills/{skill_id}",
            json={"description": "Updated description", "content": "# updated content"},
        )
    assert resp.status_code == 200
    assert resp.json()["content"] == "# updated content"


def test_update_skill_not_found(client):
    with _patch_skill_io(), _patch_skill_read():
        resp = client.patch(
            "/api/v1/skills/nonexistent-id",
            json={"description": "x"},
        )
    assert resp.status_code == 404


def test_delete_skill(client, skill_payload):
    unique_payload = {**skill_payload, "name": "delete_test_skill"}
    with _patch_skill_io(), _patch_skill_read():
        create_resp = client.post("/api/v1/skills", json=unique_payload)
        skill_id = create_resp.json()["id"]

    with _patch_skill_io(), _patch_skill_read():
        del_resp = client.delete(f"/api/v1/skills/{skill_id}")
        assert del_resp.status_code == 204

        get_resp = client.get(f"/api/v1/skills/{skill_id}")
        assert get_resp.status_code == 404


def test_delete_skill_not_found(client):
    with _patch_skill_io():
        resp = client.delete("/api/v1/skills/nonexistent-id")
    assert resp.status_code == 404
