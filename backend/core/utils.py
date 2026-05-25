"""
通用工具函数

集中放置跨模块复用的小工具,避免在 events.py / schemas/*.py 等文件里重复定义。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

import uuid
from datetime import datetime, timezone


def now_utc() -> datetime:
    """统一 UTC 时间戳工厂,用于 Pydantic Field default_factory。"""
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    """生成 UUID4 字符串(36 字符,带连字符)。所有 ID 字段统一通过本函数生成。"""
    return str(uuid.uuid4())
