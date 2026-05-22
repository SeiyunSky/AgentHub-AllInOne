"""
skills — Skill 元数据表

Skill 的正文（Markdown 内容）存于文件系统 skills/*.md，本表只存元数据。
- name 是英文唯一标识，对应 .md 文件名；同一作者下不可重名（uq_skills_author_name）。
- description 来自 .md frontmatter，用于 progressive disclosure：
  系统启动时把所有 description 列表塞进 system prompt，模型按需用 load_skill 工具加载完整正文。
- author_id 为 NULL 表示系统内置 Skill；is_public 控制是否对其他用户可见。
- file_path 指向实际 .md 文件位置，方便重命名 / 跨目录组织时解耦。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, SmallInteger, UniqueConstraint, Index

from backend.models.base import Base, TimestampMixin


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, comment="UUID")
    name = Column(String(100), nullable=False, comment="英文唯一标识，对应 .md 文件名")
    display_name = Column(String(100), nullable=True, comment="中文展示名")
    description = Column(
        String(500),
        nullable=True,
        comment="frontmatter description，progressive disclosure 时塞进系统 prompt",
    )
    category = Column(String(50), nullable=True, comment="分类（代码/安全/领域知识等）")
    file_path = Column(String(255), nullable=False, comment="指向 skills/{name}.md")
    author_id = Column(String(36), nullable=True, comment="创建者，GUGUGAGA=系统内置")
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
