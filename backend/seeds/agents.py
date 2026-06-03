"""
内置 Agent seed 数据

提示词内容存放在 backend/prompts/agents/<key>.md，与 Agent 身份数据解耦。
启动时调用 seed_agents()，幂等写入 DB：

  - 记录不存在           → INSERT
  - 记录存在但 system_prompt 为空 → UPDATE（补回内置提示词）
  - 记录存在且 system_prompt 非空 → SKIP（尊重用户的手动修改）

新增内置 Agent：
  1. 在 backend/prompts/agents/ 下新建 <key>.md（frontmatter + 正文）
  2. 在 PRESET_AGENTS 中追加一条记录

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-27
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "agents"

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _load_prompt(key: str) -> str | None:
    """从 prompts/agents/<key>.md 读取正文（去掉 frontmatter）。"""
    path = _PROMPTS_DIR / f"{key}.md"
    if not path.exists():
        logger.warning("Agent prompt file not found: %s", path)
        return None
    text = path.read_text(encoding="utf-8")
    body = _FRONTMATTER_RE.sub("", text, count=1).strip()
    return body or None


# ---------------------------------------------------------------------------
# Agent 身份数据（与提示词内容解耦）
# ---------------------------------------------------------------------------

PRESET_AGENTS: list[dict] = [
    {
        # 主 Agent（orchestrator）—— 不通过 Adapter 运行，type 用 claude 占位。
        # system_prompt 从 prompts/orchestrator.md 加载。
        "id": "orchestrator",
        "user_id": "GUGA",
        "name": "主 Agent",
        "description": "多 Agent 协作调度中心，理解用户意图、拆解任务、派发给合适的子 Agent",
        "type": "claude",
        "prompt_key": None,  # orchestrator prompt 不走 agents 目录，由 prompt_builder 加载
        "capabilities": {"supports_diff": False, "supports_approval": False},
        "avatar": "/static/avatars/avatar-1.jpg",
        "is_active": 1,
        "is_public": 0,
    },
    {
        "id": "agent-research-builtin",
        "user_id": "GUGA",
        "name": "调研 Agent",
        "description": "专业信息收集与结构化报告输出，适合市场调研、技术选型、资料汇总等任务",
        "type": "claude",
        "prompt_key": "research",
        "capabilities": {
            "supports_web_search": True,
            "supports_web_fetch": True,
        },
        "avatar": "/static/avatars/avatar-2.jpg",
        "is_active": 1,
        "is_public": 1,
    },
    {
        "id": "agent-coder-builtin",
        "user_id": "GUGA",
        "name": "代码 Agent",
        "description": "代码生成、Bug 修复、重构，输出精准 Diff，适合编码类任务",
        "type": "claude",
        "prompt_key": "coder",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-3.jpg",
        "is_active": 1,
        "is_public": 1,
    },
    {
        "id": "agent-reviewer-builtin",
        "user_id": "GUGA",
        "name": "审查 Agent",
        "description": "代码审查、逻辑评审、安全扫描，给出通过/修改/拒绝结论",
        "type": "claude",
        "prompt_key": "reviewer",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-4.jpg",
        "is_active": 1,
        "is_public": 1,
    },
]


def seed_agents(db: Session) -> int:
    """
    幂等写入内置 Agent。返回实际插入或更新的行数。

    策略：
      - 不存在 → INSERT（含 avatar）
      - 存在但 system_prompt 为空 → UPDATE（补回内置提示词）
      - 存在但 avatar 为空 → UPDATE（补回预置头像）
      - 存在且 system_prompt / avatar 均非空 → SKIP（尊重用户修改）
    """
    from backend.models.agent import Agent

    affected = 0
    for spec in PRESET_AGENTS:
        prompt_key: str | None = spec.get("prompt_key")
        fields = {k: v for k, v in spec.items() if k != "prompt_key"}

        existing = db.query(Agent).filter_by(id=fields["id"]).first()

        if existing is None:
            db.add(Agent(**fields, system_prompt=_load_prompt(prompt_key) if prompt_key else None))
            logger.info("Seeded agent (insert): %s", fields["name"])
            affected += 1

        else:
            updated = False
            if not existing.system_prompt:
                existing.system_prompt = _load_prompt(prompt_key) if prompt_key else None
                updated = True
            if not existing.avatar and fields.get("avatar"):
                existing.avatar = fields["avatar"]
                updated = True
            if updated:
                logger.info("Seeded agent (updated): %s", fields["name"])
                affected += 1

    if affected:
        db.commit()
        logger.info("Seed committed (%d agent(s) affected)", affected)

    return affected
