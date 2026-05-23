import pytest

from backend.domain.message import MessageEntity
from backend.domain.skill import SkillEntity


@pytest.fixture
def make_message():
    def _make(role="user", content="hello", **kwargs):
        return MessageEntity(id="msg-1", role=role, content=content, **kwargs)
    return _make


@pytest.fixture
def make_skill():
    def _make(name="test_skill", content="# skill content", **kwargs):
        return SkillEntity(id="sk-1", name=name, file_path=f"skills/{name}.md", content=content, **kwargs)
    return _make
