"""
messages — 消息表

承载用户消息与 Agent 回复，是 IM 时间流的最终态存储（streaming 中间态在 Redis 缓冲）。
- role + (user_id / agent_id) 组合表达消息发出方：role=user 时 agent_id=NULL，反之亦然。
- content_type 控制前端渲染分支：
  text / artifact_html / artifact_code / artifact_diff / approval_request。
  非 text 类型时 content 字段存对应卡片的 JSON 序列化数据。
- thread_id 反向索引到 threads 表，便于追溯一条消息背后的执行过程。
- parent_id 形成树形结构，支持"重新生成"与对话分支。
- model / sender 是写入时刻的快照字段：保证 Agent 改名 / 升级模型后历史消息仍展示当时数据。
- approval_status / selected_range / applied_commit_hash 是按 content_type 启用的可选字段。
- 索引 (conversation_id, created_at) 支持按会话翻页主路径；(thread_id) 支持反查执行细节。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import (
    Column,
    String,
    Text,
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
    content = Column(Text, nullable=False, comment="文本 / artifact JSON 序列化")
    content_type = Column(
        Enum(
            "text",
            "artifact_html",
            "artifact_code",
            "artifact_diff",
            "approval_request",
            name="message_content_type",
        ),
        nullable=False,
        default="text",
        server_default="text",
        comment="前端按此渲染",
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
    approval_status = Column(
        Enum("pending", "approved", "rejected", name="message_approval_status"),
        nullable=True,
        comment="content_type=approval_request 时的审批状态",
    )
    selected_range = Column(
        JSON,
        nullable=True,
        comment='{"file","start","end","code"}，对话式局部修改',
    )
    applied_commit_hash = Column(
        String(40),
        nullable=True,
        comment="Diff 应用后的 git commit hash",
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
