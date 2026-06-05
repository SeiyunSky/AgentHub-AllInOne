"""
read_receipts — 已读回执表

broadcast 模式下，Agent 决定不回复时写一行已读记录，
前端据此在对应消息上展示"某某已读"标记。

字段说明：
- id            UUID 主键
- conversation_id / message_id / agent_id  三元定位
- read_at       Agent 处理完该消息的时间（UTC）

唯一约束 (message_id, agent_id)：同一消息同一 Agent 只写一次，幂等。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-06-05
"""

from sqlalchemy import Column, String, UniqueConstraint, Index

from backend.models.base import Base, UTCTimestamp


class ReadReceipt(Base):
    __tablename__ = "read_receipts"

    id = Column(String(36), primary_key=True, comment="UUID")
    conversation_id = Column(String(36), nullable=False)
    message_id = Column(String(36), nullable=False, comment="触发本回执的用户消息 ID")
    agent_id = Column(String(36), nullable=False, comment="已读的 Agent ID")
    read_at = Column(UTCTimestamp, nullable=False, comment="Agent 处理完成时间（UTC）")

    __table_args__ = (
        UniqueConstraint("message_id", "agent_id", name="uq_read_receipt_msg_agent"),
        Index("ix_read_receipts_message_id", "message_id"),
    )
