"""
SQLAlchemy ORM 基类与公共 mixin。

Base 是所有 ORM 模型的声明基类；TimestampMixin 提供 created_at / updated_at
两个标准时间戳字段，由数据库默认值与 ON UPDATE 触发器自动维护，业务代码无需手动赋值。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from sqlalchemy import Column, TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""
    pass


class TimestampMixin:
    """
    通用时间戳 mixin。

    含义：
        created_at — 行首次插入时间，由数据库 DEFAULT CURRENT_TIMESTAMP 写入。
        updated_at — 行最近修改时间，由 ON UPDATE CURRENT_TIMESTAMP 自动刷新。

    适用：业务实体表（user / agent / conversation 等）。
    不适用：纯关联表（agent_skills / conversation_agents），它们通常只需 created_at。
    """

    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
