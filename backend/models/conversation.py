"""
conversations — 会话表

每一行代表用户左侧聊天列表里的一个条目。
- mode 决定 chat_service 的路由分支（single = 单聊、group = 群聊）。
- is_pinned / is_archived 控制列表展示与排序。
- last_message_preview / last_message_at 是冗余字段：
  发新消息时同步刷新，避免每次列表查询都要 LIMIT 1 取最后一条消息。
- message_count / unread_count 是预留计数字段。
- 索引 (user_id, last_message_at) 支持"我的会话按最近活跃排序"主查询路径。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, Enum, SmallInteger, Integer, TIMESTAMP, Index

from backend.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, comment="UUID")
    user_id = Column(String(36), nullable=False, comment="多用户隔离")
    title = Column(String(200), nullable=True, comment="会话标题")
    mode = Column(
        Enum("single", "group", name="conversation_mode"),
        nullable=False,
        comment="chat_service 路由分支用",
    )
    is_pinned = Column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="置顶",
    )
    is_archived = Column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="归档",
    )
    last_message_preview = Column(
        String(200),
        nullable=True,
        comment="最后一条消息摘要，会话列表展示",
    )
    last_message_at = Column(
        TIMESTAMP,
        nullable=True,
        comment="最后一条消息时间，比 updated_at 更精确",
    )
    message_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="消息总数",
    )
    unread_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="未读数，前端 badge",
    )

    __table_args__ = (
        Index("ix_conversations_user_last_msg", "user_id", "last_message_at"),
    )
