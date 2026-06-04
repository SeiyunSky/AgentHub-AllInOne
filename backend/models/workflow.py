"""
workflows — 前端 workflow 视图持久化表

每轮主 Agent 完成后（round_done），前端把内存中的 workflow（threads + 嵌套 blocks）
整体 POST 上来落库。一行 = 一轮 workflow 快照。

字段：
- conversation_id: 关联会话（多用户隔离 + 列表查询）
- user_id: 创建者，鉴权用
- trigger_message_id: 触发本轮的用户消息 ID（前端可定位"哪条消息引发的"）
- threads: JSON 数组，前端 WorkflowThread[] 的原样存储
- created_at: 落库时间，也是 round 完成时间

索引 (conversation_id, created_at) 支持按时间倒序拉取。

队伍：咕嘎一辈子队
"""

from sqlalchemy import Column, String, JSON, TIMESTAMP, Index, func

from backend.models.base import Base, UTCTimestamp


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    trigger_message_id = Column(String(36), nullable=True)
    threads = Column(JSON, nullable=False, comment="WorkflowThread[] 的 JSON 序列化")
    created_at = Column(UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        Index("ix_workflows_conv_created", "conversation_id", "created_at"),
        Index("ix_workflows_user", "user_id"),
    )
