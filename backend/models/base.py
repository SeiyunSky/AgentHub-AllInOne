"""
SQLAlchemy ORM 基类与公共 mixin。

Base 是所有 ORM 模型的声明基类；TimestampMixin 提供 created_at / updated_at
两个标准时间戳字段，由数据库默认值与 ON UPDATE 触发器自动维护，业务代码无需手动赋值。

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from datetime import datetime, timezone

from sqlalchemy import Column, TIMESTAMP, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCTimestamp(TypeDecorator):
    """
    TIMESTAMP 包装：MySQL 列存的是 UTC（database.py 中 SET time_zone='+00:00'），
    但 pymysql 取出来的是 naive datetime。Pydantic 序列化 naive datetime 不带
    时区信息（"2026-06-04T07:00:44"），前端 new Date() 当本地时间解析→
    UTC+8 时区下显示晚 8 小时。

    本类型在 process_result_value 给 naive datetime 强制加 UTC tzinfo，
    Pydantic 后续序列化输出 ISO 8601 带 +00:00，前端正确转本地时区。

    数据库列定义不变（仍是 TIMESTAMP），只影响 Python 端读取后的 tzinfo。
    """

    impl = TIMESTAMP
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


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

    使用 UTCTimestamp 包装：读取时自动给 naive datetime 加 UTC tzinfo，
    Pydantic 序列化后输出带时区的 ISO 8601 字符串，前端能正确转本地时间。
    """

    created_at = Column(
        UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at = Column(
        UTCTimestamp,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
