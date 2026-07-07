"""
skills — Skill 元数据 + 正文表

Skill 的正文（Markdown content）直接存 DB content 列；内置 Skill 在 backend/skills/*.md
作为版本化的源代码，启动时由 scan_builtin 同步进 DB。用户 Skill 完全只在 DB 中。

- name 是英文唯一标识；同一作者下不可重名（uq_skills_author_name）。
- description 来自 frontmatter（内置）/ 用户编辑（用户 Skill），用于 progressive
  disclosure：系统启动时把所有 description 列表塞进 system prompt，模型按需加载完整正文。
- content 是 Markdown 正文，TEXT 类型（最大 64KB）。子 Adapter 通过 SkillService
  list_with_content_for_agent 读出后塞进 system prompt。
- author_id 必填；值为 'GUGA' 时表示系统内置 Skill；is_public 控制是否对其他用户可见。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, SmallInteger, Text, UniqueConstraint, Index

from backend.models.base import Base, TimestampMixin


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, comment="UUID")
    name = Column(String(100), nullable=False, comment="英文唯一标识")
    display_name = Column(String(100), nullable=True, comment="中文展示名")
    description = Column(
        String(2000),
        nullable=True,
        comment="frontmatter description，progressive disclosure 时塞进系统 prompt",
    )
    category = Column(String(50), nullable=True, comment="分类（代码/安全/领域知识等）")
    content = Column(
        Text,
        nullable=False,
        default="",
        comment="Skill 正文（Markdown）",
    )
    author_id = Column(
        String(36),
        nullable=False,
        comment="创建者 user_id；'GUGA'=系统内置",
    )
    is_public = Column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="公开/私有",
    )
    is_active = Column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
        comment="启用/停用",
    )

    __table_args__ = (
        UniqueConstraint("author_id", "name", name="uq_skills_author_name"),
        Index("ix_skills_public_active", "is_public", "is_active"),
    )
