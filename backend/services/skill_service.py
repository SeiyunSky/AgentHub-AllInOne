"""
SkillService —— Skill 元数据 + 正文管理

正文存储：
- 内置 Skill：源代码在 backend/skills/*.md，启动时 scan_builtin() 同步进 DB content
- 用户 Skill：完全只在 DB 中（content 列），create/update 直接写 DB

职责：
1. scan_builtin()             — 扫描 backend/skills/*.md 同步元数据 + 正文到 DB（幂等）
2. list_for_orchestrator()    — 供 prompt_builder._layer_3 调用
3. get_with_content() / get_by_name_with_content() — 读 DB content 返回 SkillWithContent
4. create / update / delete   — 用户 Skill CRUD（纯 DB）

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-06-05
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.core.frontmatter import parse_frontmatter
from backend.core.utils import gen_uuid
from backend.models.skill import Skill
from backend.repositories.skill_repo import SkillRepository
from backend.schemas.skill import SkillCreate, SkillSummary, SkillUpdate, SkillWithContent

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def _parse_md(path: Path) -> tuple[dict, str]:
    """解析 .md 文件，返回 (frontmatter_fields, body)。委托给 core/frontmatter.py。"""
    return parse_frontmatter(path.read_text(encoding="utf-8"))


class SkillService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SkillRepository(db)

    # --------------------------------------------------------
    # 启动时扫描内置 Skill：把 backend/skills/*.md 文件同步进 DB
    # --------------------------------------------------------

    def scan_builtin(self) -> int:
        """
        扫描 backend/skills/*.md 同步到 skills 表。仅扫顶层 .md（用户 skill 在
        各自的 user_{author_id}/ 子目录，不会被这里误处理；改 DB 存储后子目录
        将逐渐废弃，本扫描也只看顶层）。

        策略（幂等）：
        - 不存在 → INSERT (元数据 + content)
        - 存在但 content 为空 → UPDATE content + 缺失的 description
        - 存在且 content 非空 → 强制同步 content / description（让 .md 永远是
          内置 Skill 的真相源；用户编辑过内置 Skill？我们已禁止，所以这里直接覆盖）

        返回实际插入或更新的行数。
        """
        affected = 0
        for md_path in sorted(_SKILLS_DIR.glob("*.md")):
            name = md_path.stem
            fm, body = _parse_md(md_path)

            existing = self._repo.get_by_name(name, "GUGA")
            if existing is None:
                skill = Skill(
                    id=gen_uuid(),
                    name=name,
                    display_name=fm.get("display_name") or fm.get("name"),
                    description=fm.get("description"),
                    category=fm.get("category"),
                    content=body,
                    author_id="GUGA",
                    is_public=1,
                    is_active=1,
                )
                self._db.add(skill)
                logger.info("Skill scan: inserted %s", name)
                affected += 1
            else:
                changed = False
                # content 强制同步：.md 是内置 Skill 的真相源
                if existing.content != body:
                    existing.content = body
                    changed = True
                if not existing.description and fm.get("description"):
                    existing.description = fm["description"]
                    changed = True
                # display_name / category 也强制同步
                new_display_name = fm.get("display_name") or fm.get("name")
                if new_display_name and existing.display_name != new_display_name:
                    existing.display_name = new_display_name
                    changed = True
                if fm.get("category") and existing.category != fm["category"]:
                    existing.category = fm["category"]
                    changed = True
                if changed:
                    logger.info("Skill scan: updated %s", name)
                    affected += 1

        self._db.commit()
        return affected

    # --------------------------------------------------------
    # orchestrator 接口
    # --------------------------------------------------------

    def list_for_orchestrator(self, user_id: str) -> list[SkillSummary]:
        """
        返回该用户可用的所有 Skill 精简信息（不含正文）。
        供 prompt_builder._layer_3 塞进主 Agent system prompt。
        """
        skills = self._repo.list_visible_for_user(user_id)
        return [SkillSummary.model_validate(s) for s in skills]

    # --------------------------------------------------------
    # 读取完整内容
    # --------------------------------------------------------

    def get_with_content(self, skill_id: str) -> Optional[SkillWithContent]:
        skill = self._repo.get(skill_id)
        if skill is None:
            return None
        return self._read_content(skill)

    def get_by_name_with_content(self, name: str, author_id: str = "GUGA") -> Optional[SkillWithContent]:
        skill = self._repo.get_by_name(name, author_id)
        if skill is None:
            return None
        return self._read_content(skill)

    def _read_content(self, skill: Skill) -> SkillWithContent:
        """从 DB content 列直接读正文，构造 SkillWithContent。"""
        data = SkillSummary.model_validate(skill).model_dump()
        return SkillWithContent(**data, content=skill.content or "")

    def list_with_content_for_agent(self, agent_id: str) -> list[SkillWithContent]:
        """为子 Adapter 加载 Agent 挂载的所有 Skill（含正文）。"""
        skills = self._repo.list_skills_for_agent(agent_id)
        return [self._read_content(s) for s in skills]

    # --------------------------------------------------------
    # 用户 Skill CRUD：纯 DB，不再写文件
    # --------------------------------------------------------

    def create(self, author_id: str, data: SkillCreate) -> Skill:
        skill = Skill(
            id=gen_uuid(),
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            category=data.category,
            content=data.content,
            author_id=author_id,
            is_public=1 if data.is_public else 0,
            is_active=1,
        )
        self._db.add(skill)
        self._db.commit()
        self._db.refresh(skill)
        return skill

    def update(self, skill_id: str, author_id: str, data: SkillUpdate) -> Optional[Skill]:
        skill = self._repo.get(skill_id)
        if skill is None:
            return None
        # 只有创建者本人能改：内置 Skill 的 author_id='GUGA'（系统用户，无法登录），
        # 普通用户永远不会等于它，自然被拒绝。同时也防止用户改其他用户的私有 Skill。
        if str(skill.author_id) != author_id:
            return None

        fields = data.model_dump(exclude_unset=True)
        for key, val in fields.items():
            if key in ("is_public", "is_active"):
                setattr(skill, key, 1 if val else 0)
            else:
                setattr(skill, key, val)

        self._db.flush()
        self._db.commit()
        return skill

    def delete(self, skill_id: str, author_id: str) -> bool:
        skill = self._repo.get(skill_id)
        if skill is None:
            return False
        # 只有创建者本人能删
        if str(skill.author_id) != author_id:
            return False

        self._db.delete(skill)
        self._db.commit()
        return True
