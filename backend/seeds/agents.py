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
        "name": "Orchestrator",
        "description": "多 Agent 协作调度中心，理解用户意图、拆解任务、派发给合适的子 Agent",
        "type": "claude",
        "prompt_key": None,  # orchestrator prompt 不走 agents 目录，由 prompt_builder 加载
        "capabilities": {"supports_diff": False, "supports_approval": False},
        "avatar": "/static/avatars/avatar-1.jpg",
        "is_active": 1,
        "is_public": 0,
        "default_skills": [],
    },
    {
        # 注:旧 ID agent-research-builtin 已迁移为 agent-research-dev,见 _migrate_legacy_ids
        "id": "agent-research-dev",
        "user_id": "GUGA",
        "name": "技术调研 Agent",
        "description": "技术选型、库对比、最佳实践调研。dev 群组专用,输出可决策的对比表与推荐结论",
        "type": "claude",
        "prompt_key": "research_dev",
        "capabilities": {
            "supports_web_search": True,
            "supports_web_fetch": True,
        },
        "avatar": "/static/avatars/avatar-2.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": ["python_runtime_environment"],
    },
    {
        "id": "agent-coder-builtin",
        "user_id": "GUGA",
        "name": "代码 Agent",
        "description": "代码生成、Bug 修复、重构,输出精准 Diff,适合编码类任务",
        "type": "claude",
        "prompt_key": "coder",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-3.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": [
            "software_engineering_principles",
            "python_runtime_environment",
            "web_app_development_workflow",
            "python_expert",
        ],
    },
    {
        # 注:旧 ID agent-reviewer-builtin 已迁移为 agent-reviewer-dev,见 _migrate_legacy_ids
        "id": "agent-reviewer-dev",
        "user_id": "GUGA",
        "name": "代码审查 Agent",
        "description": "代码审查、逻辑评审、安全扫描,给出通过/修改/拒绝结论。dev 群组专用,兼任部署前合规检查",
        "type": "claude",
        "prompt_key": "reviewer",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-4.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": [
            "software_engineering_principles",
            "code_review",
            "security_audit",
            "deployment_workflow",
        ],
    },
    # ====================================================================
    # data squad 三件套
    # ====================================================================
    {
        "id": "agent-research-data",
        "user_id": "GUGA",
        "name": "数据调研 Agent",
        "description": "业务/数据口径调研,核实指标定义、数据源和已知问题,服务数据分析任务",
        "type": "claude",
        "prompt_key": "research_data",
        "capabilities": {
            "supports_web_search": True,
            "supports_web_fetch": True,
        },
        "avatar": "/static/avatars/avatar-6.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": [],
    },
    {
        "id": "agent-data-analyst-builtin",
        "user_id": "GUGA",
        "name": "数据分析师",
        "description": "用 pandas/numpy 写脚本做探索、清洗、统计、可视化,输出结构化分析报告",
        "type": "claude",
        "prompt_key": "data_analyst",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-7.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": [
            "software_engineering_principles",
            "python_runtime_environment",
            "data_analysis_workflow",
            "data_storytelling",
            "python_expert",
        ],
    },
    {
        "id": "agent-reviewer-data",
        "user_id": "GUGA",
        "name": "数据审查 Agent",
        "description": "审查数据分析脚本的统计正确性、口径一致性、结论是否被数据支撑",
        "type": "claude",
        "prompt_key": "reviewer_data",
        "capabilities": {},
        "avatar": "/static/avatars/avatar-8.jpg",
        "is_active": 1,
        "is_public": 1,
        "default_skills": [
            "data_quality_checklist",
            "data_analysis_workflow",
        ],
    },
]


# 旧 ID → 新 ID 迁移表(rename 后兼容已经把旧 ID 加进会话的用户)
_LEGACY_ID_MIGRATIONS: list[tuple[str, str]] = [
    ("agent-research-builtin", "agent-research-dev"),
    ("agent-reviewer-builtin", "agent-reviewer-dev"),
]


def _migrate_legacy_ids(db: Session) -> int:
    """
    旧 ID 兼容迁移:把 agents / agent_skills / conversations 等表里引用旧 ID 的行
    update 成新 ID,然后删除旧 agents 行。

    幂等:旧 ID 不存在时直接跳过。
    """
    from backend.models.agent import Agent
    from sqlalchemy import text as _sql_text

    affected = 0
    for old_id, new_id in _LEGACY_ID_MIGRATIONS:
        old_row = db.query(Agent).filter_by(id=old_id).first()
        if old_row is None:
            continue
        # 关联表里的 agent_id 引用全部改成新 ID。SQL 层 UPDATE 比 ORM 起 N 次查省事。
        # threads / agent_skills / conversation_agents / messages 等表如果有外键引用都要改;
        # 这里只覆盖已知会引用 agent_id 的核心表,新增表时按需补。
        for table, col in [
            ("agent_skills", "agent_id"),
            ("threads", "agent_id"),
            ("conversation_agents", "agent_id"),
            ("messages", "agent_id"),
        ]:
            try:
                db.execute(
                    _sql_text(f"UPDATE {table} SET {col} = :new WHERE {col} = :old"),
                    {"new": new_id, "old": old_id},
                )
            except Exception:
                # 表不存在 / 列不存在(早期数据库)→ 忽略,不阻塞主流程
                logger.exception(
                    "legacy id migration on %s.%s failed (non-fatal)", table, col
                )
        # 旧 Agent 行删掉
        db.delete(old_row)
        logger.info("Migrated legacy agent id: %s → %s", old_id, new_id)
        affected += 1

    if affected:
        db.commit()
    return affected


def _seed_agent_skills(db: Session) -> int:
    """
    把 PRESET_AGENTS 里 default_skills 配置写进 agent_skills 关联表。
    幂等:已存在的 (agent_id, skill_id) 跳过;不存在的插入。
    """
    from backend.models.agent_skill import AgentSkill
    from backend.models.skill import Skill

    affected = 0
    for spec in PRESET_AGENTS:
        agent_id = spec["id"]
        skill_names = spec.get("default_skills") or []
        if not skill_names:
            continue
        for skill_name in skill_names:
            skill = (
                db.query(Skill)
                .filter_by(name=skill_name, author_id="GUGA")
                .first()
            )
            if skill is None:
                logger.warning(
                    "default_skill %s referenced by agent %s not found in skills table"
                    " (是否漏跑 skill_service.scan_builtin?)",
                    skill_name, agent_id,
                )
                continue
            existing = (
                db.query(AgentSkill)
                .filter_by(agent_id=agent_id, skill_id=skill.id)
                .first()
            )
            if existing is None:
                db.add(AgentSkill(agent_id=agent_id, skill_id=skill.id))
                affected += 1

    if affected:
        db.commit()
        logger.info("Seeded agent_skills (%d row(s))", affected)
    return affected


def seed_agents(db: Session) -> int:
    """
    幂等写入内置 Agent。返回实际插入或更新的行数。

    流程:
      1. 旧 ID 兼容迁移(_LEGACY_ID_MIGRATIONS 表)
      2. PRESET_AGENTS 逐条写入 / 更新
      3. agent_skills 关联表按 default_skills 字段写入

    Agent 字段策略:
      - 不存在 → INSERT(含 avatar,不含 default_skills,这是 seed 用字段不入库)
      - 存在但 system_prompt 为空 → UPDATE(补回内置提示词)
      - 存在但 avatar 为空 → UPDATE(补回预置头像)
      - 存在且 system_prompt / avatar 均非空 → SKIP(尊重用户修改)
    """
    from backend.models.agent import Agent

    # Step 1: 旧 ID 兼容迁移
    _migrate_legacy_ids(db)

    # Step 2: PRESET_AGENTS
    affected = 0
    for spec in PRESET_AGENTS:
        prompt_key: str | None = spec.get("prompt_key")
        # default_skills 是 seed 用字段,不入 agents 表
        fields = {
            k: v for k, v in spec.items()
            if k not in ("prompt_key", "default_skills")
        }

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

    # Step 3: agent_skills 关联(依赖 skills 表已 scan_builtin,
    # main.py lifespan 里顺序保证: seed_agents 之后才扫 skill)
    # 这里在 seed_agents 内部调一次,但实际 skill 表可能还没数据,
    # 所以 main.py 调用顺序: scan_builtin → seed_agents,在 seed_agents 末尾挂关联。
    _seed_agent_skills(db)

    return affected
