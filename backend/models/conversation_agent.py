"""
conversation_agents — 会话参与的 Agent（多对多）

记录某个会话里有哪些 Agent。单聊场景一条记录、群聊场景多条记录。
- joined_at 记录该 Agent 加入会话的时间，群成员列表按加入顺序展示。
- is_active 是软删除标志：将 Agent 移出群聊时只置 0，不真删，保证历史消息中
  agent_id 仍能关联到这条记录、不丢"曾经在群里"的语义。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, TIMESTAMP, SmallInteger, func

from backend.models.base import Base


class ConversationAgent(Base):
    __tablename__ = "conversation_agents"

    conversation_id = Column(String(36), primary_key=True, comment="conversations.id")
    agent_id = Column(String(36), primary_key=True, comment="agents.id")
    joined_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        comment="加入时间，群成员按加入顺序展示",
    )
    is_active = Column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default="1",
        comment="是否仍在群里（踢出后置 0，历史消息不丢）",
    )
