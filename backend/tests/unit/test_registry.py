"""Unit tests for AdapterRegistry and _build_adapter factory.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-23
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.adapters.registry import AdapterRegistry, _build_adapter
from backend.core.exceptions import AgentNotFoundError


# ---------------------------------------------------------------------------
# Register / get / unregister
# ---------------------------------------------------------------------------

def test_register_and_get():
    reg = AdapterRegistry()
    mock_adapter = MagicMock()
    reg.register("agent-1", mock_adapter)
    assert reg.get("agent-1") is mock_adapter


def test_get_unknown_returns_none():
    reg = AdapterRegistry()
    assert reg.get("nonexistent") is None


def test_get_or_raise_unknown():
    reg = AdapterRegistry()
    with pytest.raises(AgentNotFoundError):
        reg.get_or_raise("nonexistent")


def test_get_or_raise_returns_adapter():
    reg = AdapterRegistry()
    mock_adapter = MagicMock()
    reg.register("a1", mock_adapter)
    assert reg.get_or_raise("a1") is mock_adapter


def test_unregister():
    reg = AdapterRegistry()
    mock_adapter = MagicMock()
    reg.register("a1", mock_adapter)
    reg.unregister("a1")
    assert reg.get("a1") is None


def test_unregister_nonexistent_is_safe():
    reg = AdapterRegistry()
    reg.unregister("ghost")  # Should not raise


# ---------------------------------------------------------------------------
# shutdown
# ---------------------------------------------------------------------------

async def test_shutdown_clears_registry():
    reg = AdapterRegistry()
    a1 = AsyncMock()
    a2 = AsyncMock()
    reg.register("a1", a1)
    reg.register("a2", a2)
    await reg.shutdown()
    assert reg.get("a1") is None
    assert reg.get("a2") is None


async def test_shutdown_tolerates_close_error():
    reg = AdapterRegistry()
    bad_adapter = AsyncMock()
    reg.register("bad", bad_adapter)
    await reg.shutdown()  # Should not raise


# ---------------------------------------------------------------------------
# seed_from_db
# ---------------------------------------------------------------------------

def test_seed_from_db_registers_active_agents():
    reg = AdapterRegistry()

    def _make_row(agent_id, agent_type):
        row = MagicMock()
        row.id = agent_id
        row.name = f"Agent {agent_id}"
        row.type = agent_type
        row.system_prompt = None
        row.capabilities = {}
        row.is_active = 1
        return row

    claude_row = _make_row("claude-1", "claude")
    codex_row = _make_row("codex-1", "codex")
    custom_row = _make_row("custom-1", "custom")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [claude_row, codex_row, custom_row]

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_result

    with patch("backend.adapters.custom.openai.AsyncOpenAI"):
        reg.seed_from_db(mock_db)

    assert reg.get("claude-1") is not None
    assert reg.get("codex-1") is not None
    assert reg.get("custom-1") is not None


def test_seed_from_db_skips_failed_rows():
    reg = AdapterRegistry()

    bad_row = MagicMock()
    bad_row.id = "bad-1"
    bad_row.name = "Bad"
    bad_row.type = "unsupported_type"
    bad_row.system_prompt = None
    bad_row.capabilities = {}
    bad_row.is_active = 1

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [bad_row]

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_result

    with patch("backend.adapters.custom.openai.AsyncOpenAI"):
        reg.seed_from_db(mock_db)

    assert reg.get("bad-1") is None


# ---------------------------------------------------------------------------
# _build_adapter factory
# ---------------------------------------------------------------------------

def _make_row(agent_id: str, agent_type: str):
    row = MagicMock()
    row.id = agent_id
    row.name = "Test"
    row.type = agent_type
    row.system_prompt = None
    row.capabilities = {}
    return row


def test_build_adapter_claude():
    from backend.adapters.claude import ClaudeAdapter
    adapter = _build_adapter(_make_row("a1", "claude"))
    assert isinstance(adapter, ClaudeAdapter)


def test_build_adapter_codex():
    from backend.adapters.codex import CodexAdapter
    adapter = _build_adapter(_make_row("a1", "codex"))
    assert isinstance(adapter, CodexAdapter)


def test_build_adapter_custom():
    from backend.adapters.custom import CustomAdapter
    with patch("backend.adapters.custom.openai.AsyncOpenAI"):
        adapter = _build_adapter(_make_row("a1", "custom"))
    assert isinstance(adapter, CustomAdapter)


def test_build_adapter_opencode():
    from backend.adapters.opencode import OpencodeAdapter
    adapter = _build_adapter(_make_row("a1", "opencode"))
    assert isinstance(adapter, OpencodeAdapter)


def test_build_adapter_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        _build_adapter(_make_row("a1", "unsupported"))
