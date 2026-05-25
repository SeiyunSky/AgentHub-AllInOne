"""
threads — Thread 执行状态表

记录每个 Agent 在一次会话中的执行生命周期，是"用户视角的消息"与"Agent 视角的执行上下文"
之间的桥梁。一次用户发言可能触发多个 Thread（群聊并行），每个 Thread 独立维护自己的状态机：
    init → running → done
                  → suspended（等审批 / 中断）→ running
                  → error
- checkpoint 字段是冷存储，热缓存放在 Redis；用于 @个体特化的会话续写、
  审批中断后恢复、断线重连。
- started_at / finished_at / tokens_total 用于性能分析与计费审计。
- 索引 (conversation_id, agent_id, updated_at) 支持 thread_service.resume_or_create()
  快速找到某会话中某 Agent 最近的 Thread。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, Text, Enum, JSON, Integer, TIMESTAMP, Index

from backend.models.base import Base, TimestampMixin


class Thread(Base, TimestampMixin):
    __tablename__ = "threads"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False)
    message_id = Column(String(36), nullable=False, comment="触发本 Thread 的用户消息")
    agent_id = Column(String(36), nullable=False)
    status = Column(
        Enum(
            "init", "running", "suspended", "done", "error", "cancelled",
            name="thread_status",
        ),
        nullable=False,
        default="init",
        server_default="init",
    )
    checkpoint = Column(JSON, nullable=True, comment="冷存储，热缓存在 Redis")
    blocked_by = Column(
        JSON,
        nullable=True,
        comment="任务依赖图：依赖的 thread_id 数组，全部 done 后该 Thread 才解锁启动",
    )
    dispatch_prompt = Column(
        Text,
        nullable=True,
        comment="主 Agent 派活时给子 Agent 的指令，_run_thread 启动 Adapter 时塞进 StreamInput.prompt",
    )
    started_at = Column(TIMESTAMP, nullable=True, comment="进入 running 时间")
    finished_at = Column(TIMESTAMP, nullable=True, comment="进入 done/error 时间")
    error_message = Column(String(500), nullable=True)
    tokens_total = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="累计 token 消耗（输入+输出）",
    )

    __table_args__ = (
        # resume_or_create 查询用：按 conversation+agent 找最近的 thread
        Index(
            "ix_threads_conv_agent_updated",
            "conversation_id",
            "agent_id",
            "updated_at",
        ),
    )
