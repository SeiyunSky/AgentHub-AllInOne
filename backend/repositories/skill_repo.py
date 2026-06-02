"""
SkillRepository —— skills 表 + agent_skills 关联表数据访问层

继承 BaseRepository[Skill] 通用 CRUD，补充：
- 按 author 或 public/active 过滤的列表查询
- agent_skills 挂载关系增删查

session 由调用方注入；repo 只 add / flush，commit 由 service 控制。

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, or_

from backend.models.agent_skill import AgentSkill
from backend.models.skill import Skill
from backend.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    model = Skill

    # --------------------------------------------------------
    # 列表查询
    # --------------------------------------------------------

    def list_visible_for_user(
        self,
        user_id: str,
        *,
        include_inactive: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Skill]:
        """用户可见的 Skill：自己创建的 + 公开的，按 created_at 倒序。"""
        conds = [or_(Skill.author_id == user_id, Skill.is_public == 1)]
        if not include_inactive:
            conds.append(Skill.is_active == 1)
        return (
            self.session.query(Skill)
            .filter(and_(*conds))
            .order_by(desc(Skill.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_builtin(self, *, limit: int = 20, offset: int = 0) -> list[Skill]:
        """内置 Skill（author_id='GUGA'），按 created_at 倒序。"""
        return (
            self.session.query(Skill)
            .filter(Skill.author_id == "GUGA", Skill.is_active == 1)
            .order_by(desc(Skill.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_name(self, name: str, author_id: str) -> Optional[Skill]:
        """按 (author_id, name) 唯一键查找。"""
        return (
            self.session.query(Skill)
            .filter(Skill.author_id == author_id, Skill.name == name)
            .first()
        )

    # --------------------------------------------------------
    # agent_skills 挂载关系
    # --------------------------------------------------------

    def list_skills_for_agent(self, agent_id: str) -> list[Skill]:
        """返回某 Agent 挂载的所有 Skill（按 name 升序）。"""
        return (
            self.session.query(Skill)
            .join(AgentSkill, AgentSkill.skill_id == Skill.id)
            .filter(AgentSkill.agent_id == agent_id, Skill.is_active == 1)
            .order_by(Skill.name.asc())
            .all()
        )

    def list_skill_ids_for_agent(self, agent_id: str) -> list[str]:
        rows = (
            self.session.query(AgentSkill.skill_id)
            .filter(AgentSkill.agent_id == agent_id)
            .all()
        )
        return [r.skill_id for r in rows]

    def attach_skill(self, agent_id: str, skill_id: str) -> None:
        """挂载 Skill；已存在则 no-op。"""
        existing = (
            self.session.query(AgentSkill)
            .filter(AgentSkill.agent_id == agent_id, AgentSkill.skill_id == skill_id)
            .first()
        )
        if existing is None:
            self.session.add(AgentSkill(agent_id=agent_id, skill_id=skill_id))
            self.session.flush()

    def detach_skill(self, agent_id: str, skill_id: str) -> None:
        """卸载 Skill；不存在则 no-op。"""
        self.session.query(AgentSkill).filter(
            AgentSkill.agent_id == agent_id, AgentSkill.skill_id == skill_id
        ).delete()
        self.session.flush()

    def sync_agent_skills(self, agent_id: str, skill_ids: list[str]) -> None:
        """替换 Agent 的全部挂载 Skill（增量 diff：新增 + 删除多余）。"""
        current = set(self.list_skill_ids_for_agent(agent_id))
        target = set(skill_ids)
        for sid in target - current:
            self.attach_skill(agent_id, sid)
        for sid in current - target:
            self.detach_skill(agent_id, sid)
