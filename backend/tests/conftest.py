import pytest

from backend.domain.message import TextBlock
from backend.schemas.message import MessageInHistory, MessageRole
from backend.schemas.skill import SkillWithContent


@pytest.fixture
def make_message():
    def _make(role="user", content="hello", **kwargs):
        blocks = [TextBlock(block_id="blk-1", content=content)]
        return MessageInHistory(role=MessageRole(role), blocks=blocks, **kwargs)
    return _make


@pytest.fixture
def make_skill():
    def _make(name="test_skill", content="# skill content", **kwargs):
        return SkillWithContent(
            id="sk-1",
            name=name,
            author_id="GUGA",
            is_public=True,
            is_active=True,
            content=content,
            **kwargs,
        )
    return _make
