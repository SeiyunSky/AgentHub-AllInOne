"""
agent_skills — Agent 挂载 Skill 关联表

记录 Agent 与 Skill 之间的多对多关系。
- 复合主键 (agent_id, skill_id)：同一 Agent 不能重复挂同一个 Skill。
- 单独索引 skill_id：支持反向查询"哪些 Agent 挂了某 Skill"，用于 Skill 详情页 / 影响面分析。
- 仅记录 created_at（关系建立时间），不需要 updated_at。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, TIMESTAMP, Index, func

from backend.models.base import Base, UTCTimestamp


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    agent_id = Column(String(36), primary_key=True, comment="agents.id")
    skill_id = Column(String(36), primary_key=True, comment="skills.id")
    created_at = Column(UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        # 反向查支持："哪些 Agent 挂了某 Skill"
        Index("ix_agent_skills_skill", "skill_id"),
    )
