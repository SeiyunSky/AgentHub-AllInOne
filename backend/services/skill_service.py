"""
SkillService —— Skill 元数据管理

职责：
1. scan_builtin()   — 扫 backend/skills/*.md，同步元数据到 skills 表（幂等）
2. list_for_orchestrator(user_id) — 供 prompt_builder._layer_3 调用
3. get_with_content(id/name)     — 读文件正文，返回 SkillWithContent
4. create / update / delete      — 用户 Skill CRUD（元数据写 DB + 正文写文件）

文件约定：
- 内置 Skill：backend/skills/{name}.md
- 用户 Skill：backend/skills/user_{author_id}/{name}.md

frontmatter 字段（可选）：
  name / display_name / description / category

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.core.utils import gen_uuid
from backend.models.skill import Skill
from backend.repositories.skill_repo import SkillRepository
from backend.schemas.skill import SkillCreate, SkillSummary, SkillUpdate, SkillWithContent

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent.parent / "skills"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FM_FIELD_RE = re.compile(r"^(\w+)\s*:\s*(.+)$", re.MULTILINE)


def _parse_md(path: Path) -> tuple[dict[str, str], str]:
    """解析 .md 文件，返回 (frontmatter_fields, body)。"""
    text = path.read_text(encoding="utf-8")
    fm: dict[str, str] = {}
    m = _FRONTMATTER_RE.match(text)
    if m:
        for key, val in _FM_FIELD_RE.findall(m.group(1)):
            fm[key.strip()] = val.strip().strip("'\"")
        body = text[m.end():].strip()
    else:
        body = text.strip()
    return fm, body


class SkillService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SkillRepository(db)

    # --------------------------------------------------------
    # 启动时扫描内置 Skill
    # --------------------------------------------------------

    def scan_builtin(self) -> int:
        """
        扫描 backend/skills/*.md，幂等同步到 skills 表。
        - 不存在 → INSERT
        - 存在但 description 为空 → UPDATE description
        - 存在且 description 非空 → SKIP
        返回实际插入或更新的行数。
        """
        affected = 0
        for md_path in sorted(_SKILLS_DIR.glob("*.md")):
            name = md_path.stem
            fm, _ = _parse_md(md_path)
            file_path = f"skills/{md_path.name}"

            existing = self._repo.get_by_name(name, "GUGA")
            if existing is None:
                skill = Skill(
                    id=gen_uuid(),
                    name=name,
                    display_name=fm.get("display_name") or fm.get("name"),
                    description=fm.get("description"),
                    category=fm.get("category"),
                    file_path=file_path,
                    author_id="GUGA",
                    is_public=1,
                    is_active=1,
                )
                self._db.add(skill)
                logger.info("Skill scan: inserted %s", name)
                affected += 1
            elif not existing.description and fm.get("description"):
                existing.description = fm["description"]
                logger.info("Skill scan: updated description for %s", name)
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
        path = Path(__file__).parent.parent / skill.file_path
        if path.exists():
            _, body = _parse_md(path)
        else:
            logger.warning("Skill file missing: %s", path)
            body = ""
        data = SkillSummary.model_validate(skill).model_dump()
        return SkillWithContent(**data, content=body)

    def list_with_content_for_agent(self, agent_id: str) -> list[SkillWithContent]:
        """为子 Adapter 加载 Agent 挂载的所有 Skill（含正文）。"""
        skills = self._repo.list_skills_for_agent(agent_id)
        return [self._read_content(s) for s in skills]

    # --------------------------------------------------------
    # 用户 Skill CRUD
    # --------------------------------------------------------

    def create(self, author_id: str, data: SkillCreate) -> Skill:
        if author_id == "GUGA":
            file_path = f"skills/{data.name}.md"
        else:
            file_path = f"skills/user_{author_id}/{data.name}.md"

        abs_path = Path(__file__).parent.parent / file_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(data.content, encoding="utf-8")

        skill = Skill(
            id=gen_uuid(),
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            category=data.category,
            file_path=file_path,
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
        if skill is None or skill.author_id != author_id:
            return None

        fields = data.model_dump(exclude_unset=True)
        content = fields.pop("content", None)

        for key, val in fields.items():
            if key in ("is_public", "is_active"):
                setattr(skill, key, 1 if val else 0)
            else:
                setattr(skill, key, val)

        if content is not None:
            abs_path = Path(__file__).parent.parent / skill.file_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")

        self._db.flush()
        self._db.commit()
        return skill

    def delete(self, skill_id: str, author_id: str) -> bool:
        skill = self._repo.get(skill_id)
        if skill is None or skill.author_id != author_id:
            return False
        self._db.delete(skill)
        self._db.commit()
        return True
