"""
audit_logs — 审计日志表

记录系统中关键业务行为的不可变事件流：登录登出、Agent CRUD、Diff 应用、审批确认等。
- 表只增不改不删，是合规追溯的事实底账。
- 由 hooks（pre_execution / approval）统一触发 + 关键 service（auth / agent CRUD）补写。
- detail 字段以 JSON 自由结构记录输入参数 / 变更前后值，避免每加一种行为就改表结构。
- trace_id 串联同一次请求的运行日志（文件）与审计日志（DB），跨系统排查时可联动检索。
- 三个索引分别支持："某用户的操作历史"/"某类行为的发生频率"/"某资源的变更轨迹"。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, String, JSON, TIMESTAMP, Index, func

from backend.models.base import Base, UTCTimestamp


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, comment="UUID")
    user_id = Column(String(36), nullable=True, comment="谁触发的，系统操作时为 NULL")
    action = Column(
        String(50),
        nullable=False,
        comment="行为标识，如 login / agent.create / diff.apply / approval.confirm",
    )
    target_type = Column(
        String(50),
        nullable=True,
        comment="agent / conversation / message ...",
    )
    target_id = Column(String(36), nullable=True)
    detail = Column(JSON, nullable=True, comment="输入参数 / 变更前后值")
    ip = Column(String(45), nullable=True, comment="客户端 IP（IPv6 最长 45）")
    user_agent = Column(String(255), nullable=True, comment="浏览器 UA")
    trace_id = Column(String(36), nullable=True, comment="关联运行日志 trace_id")
    created_at = Column(UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
        Index("ix_audit_target", "target_type", "target_id"),
    )
