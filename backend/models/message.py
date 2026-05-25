"""
messages — 消息表

承载用户消息与 Agent 回复，是 IM 时间流的最终态存储（streaming 中间态在 Redis 缓冲）。

内容模型：
- content 字段是 JSON，存有序的 ContentBlock 数组（domain.message.ContentBlock）。
  一条 Agent 消息可同时包含 thinking / tool_use / code / text 等多个块，
  按顺序在前端渲染。
- 不再有 content_type / approval_status / applied_commit_hash 等外层字段，
  这些语义全在对应 ContentBlock 子类内部表达。

其它字段：
- role + (user_id / agent_id) 组合表达发送方：role=user 时 agent_id=NULL，反之亦然。
- thread_id 反向索引到 threads 表，便于追溯执行过程。
- parent_id 形成树形结构，支持"重新生成"与分支。
- model / sender 是写入时刻的快照：保证 Agent 改名 / 升级模型后历史消息仍展示当时数据。
- selected_range 是对话式局部修改时携带的代码段元数据（用户输入特征，不是消息块）。

索引 (conversation_id, created_at) 支持按会话翻页；(thread_id) 支持反查执行细节。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-25
"""

from sqlalchemy import (
    Column,
    String,
    Enum,
    SmallInteger,
    Integer,
    JSON,
    TIMESTAMP,
    Index,
    func,
)

from backend.models.base import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, comment="messageId")
    conversation_id = Column(String(36), nullable=False)
    thread_id = Column(String(36), nullable=True, comment="关联 threads 表")
    parent_id = Column(
        String(36),
        nullable=True,
        comment="树形结构（重新生成/分支）",
    )
    user_id = Column(String(36), nullable=True, comment="用户消息时填")
    agent_id = Column(String(36), nullable=True, comment="Agent 消息时填")
    role = Column(
        Enum("user", "assistant", name="message_role"),
        nullable=False,
    )
    content = Column(
        JSON,
        nullable=False,
        comment="ContentBlock 数组的 JSON 序列化（见 domain/message.py）",
    )
    status = Column(
        Enum("streaming", "done", "error", name="message_status"),
        nullable=False,
        default="done",
        server_default="done",
    )
    error_message = Column(String(500), nullable=True)
    model = Column(
        String(50),
        nullable=True,
        comment="实际用的模型快照，hover 气泡显示",
    )
    sender = Column(
        String(100),
        nullable=True,
        comment="Agent 显示名快照，避免每次 join agents",
    )
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True, comment="Agent 响应耗时")
    feedback = Column(
        Enum("up", "down", name="message_feedback"),
        nullable=True,
        comment="用户点赞/点踩",
    )
    selected_range = Column(
        JSON,
        nullable=True,
        comment='{"file","start","end","code"}，对话式局部修改',
    )
    is_deleted = Column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
        comment="软删除",
    )
    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_messages_thread", "thread_id"),
    )
