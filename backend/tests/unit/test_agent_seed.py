"""Unit tests for seeds/agents.py — prompt file loading and seed idempotency.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.seeds.agents import PRESET_AGENTS, _load_prompt, seed_agents


# ---------------------------------------------------------------------------
# _load_prompt：从 .md 文件加载提示词正文
# ---------------------------------------------------------------------------

def test_load_prompt_research():
    body = _load_prompt("research")
    assert body is not None
    assert len(body) > 50
    assert "调研" in body
    assert "---" not in body.splitlines()[0]   # frontmatter 已去除


def test_load_prompt_coder():
    body = _load_prompt("coder")
    assert body is not None
    assert "代码" in body
    assert "---" not in body.splitlines()[0]


def test_load_prompt_reviewer():
    body = _load_prompt("reviewer")
    assert body is not None
    assert "审查" in body
    assert "---" not in body.splitlines()[0]


def test_load_prompt_missing_key_returns_none():
    body = _load_prompt("nonexistent_key_xyz")
    assert body is None


# ---------------------------------------------------------------------------
# PRESET_AGENTS：身份数据结构完整性
# ---------------------------------------------------------------------------

def test_preset_agents_have_required_fields():
    required = {"id", "user_id", "name", "type", "prompt_key"}
    for agent in PRESET_AGENTS:
        missing = required - agent.keys()
        assert not missing, f"{agent['name']} missing fields: {missing}"


def test_preset_agents_prompt_keys_have_files():
    """每个非 None 的 prompt_key 必须对应一个实际存在的 .md 文件。
    orchestrator 等特殊 Agent 的 prompt 由独立路径加载，prompt_key=None 跳过。
    """
    for agent in PRESET_AGENTS:
        key = agent["prompt_key"]
        if key is None:
            continue  # orchestrator 等无 prompt_key 的 Agent 跳过
        body = _load_prompt(key)
        assert body is not None, f"prompt file missing for agent '{agent['name']}' (key={key!r})"


def test_preset_agents_ids_are_unique():
    ids = [a["id"] for a in PRESET_AGENTS]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# seed_agents：幂等写入逻辑
# ---------------------------------------------------------------------------

def _make_db(existing_agents: dict[str, MagicMock] | None = None):
    """构造一个 mock Session，query().filter_by().first() 按 id 返回指定值。"""
    existing = existing_agents or {}
    db = MagicMock()

    def _query_first(**kwargs):
        agent_id = kwargs.get("id")
        return existing.get(agent_id)

    db.query.return_value.filter_by.return_value.first.side_effect = (
        lambda: _query_first(**db.query.return_value.filter_by.call_args.kwargs)
    )
    return db


def test_seed_agents_inserts_when_none_exist():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None

    count = seed_agents(db)

    assert count == len(PRESET_AGENTS)
    assert db.add.call_count == len(PRESET_AGENTS)


def test_seed_agents_skips_existing_with_prompt():
    """已存在且 system_prompt 非空 → 全部跳过，不 add 也不修改。"""
    existing = MagicMock()
    existing.system_prompt = "已有人格，用户自定义"

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = existing

    count = seed_agents(db)

    assert count == 0
    db.add.assert_not_called()


def test_seed_agents_restores_empty_prompt():
    """已存在但 system_prompt 为空 → 补回提示词（UPDATE），不 INSERT。
    orchestrator 的 prompt_key=None，补回后 system_prompt 仍为 None，不算 affected。
    """
    existing_map = {a["id"]: MagicMock(system_prompt=None) for a in PRESET_AGENTS}

    db = MagicMock()
    db.query.return_value.filter_by.side_effect = lambda **kw: MagicMock(
        first=MagicMock(return_value=existing_map.get(kw.get("id")))
    )

    count = seed_agents(db)

    # 有 prompt_key 的 agent 才会被 UPDATE；orchestrator(prompt_key=None) 写 None 也算 affected
    assert count == len(PRESET_AGENTS)
    db.add.assert_not_called()
    # 有 prompt_key 的 agent system_prompt 必须非空
    agents_with_key = [a for a in PRESET_AGENTS if a["prompt_key"] is not None]
    for agent_spec in agents_with_key:
        mock_agent = existing_map[agent_spec["id"]]
        assert mock_agent.system_prompt is not None
        assert len(mock_agent.system_prompt) > 10


def test_seed_agents_does_not_mutate_preset_list():
    """seed_agents 多次调用不能修改 PRESET_AGENTS 里的原始 dict（防止 pop 副作用）。"""
    keys_before = [set(a.keys()) for a in PRESET_AGENTS]

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None

    seed_agents(db)
    seed_agents(db)

    keys_after = [set(a.keys()) for a in PRESET_AGENTS]
    assert keys_before == keys_after
