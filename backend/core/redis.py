"""
core/redis.py —— Redis 连接(lazy 单例,可选化)

设计原则:
- Redis 是可选基础设施;settings.REDIS_URL 未配置时返回 None,调用方 None-check 后降级。
- 进程级单例,首次调用时建连;失败一次后本进程不再重试(避免每次请求都报错刷屏)。
- 用法对齐 sync FastAPI 路径;后续如果 chat / WS 路径异步化需要 redis,再考虑 redis.asyncio。

调用示例:
    from backend.core.redis import get_redis
    r = get_redis()
    if r is None:
        # 降级路径(MVP 没配 Redis)
        return False
    r.set("key", "value", ex=60)

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-02
"""

from __future__ import annotations

import logging
from typing import Optional

import redis as _redis_pkg

from backend.config import settings


logger = logging.getLogger(__name__)


# 进程级缓存:None 表示"还没尝试过","__failed__" 哨兵表示"尝试过但失败了"
_client: Optional[_redis_pkg.Redis] = None
_init_failed: bool = False


def get_redis() -> Optional[_redis_pkg.Redis]:
    """
    返回 Redis 客户端;未配置 / 连接失败时返回 None。

    调用方必须 None-check 并走降级分支;不要让上游业务因 Redis 不可达而崩。

    Returns:
        Redis 客户端;None 表示功能不可用(REDIS_URL 未配置或建连失败)。
    """
    global _client, _init_failed

    if _client is not None:
        return _client
    if _init_failed:
        return None
    if not settings.REDIS_URL:
        # 未配置 = 静默降级,不报警(MVP 默认场景)
        _init_failed = True
        return None

    try:
        client = _redis_pkg.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,  # str 进 str 出,省去 .decode()
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # 立刻 ping 一次确认连接可用;失败抛 ConnectionError
        client.ping()
        _client = client
        logger.info("redis connected: %s", _redact_url(settings.REDIS_URL))
        return _client
    except Exception:
        _init_failed = True
        logger.warning(
            "redis init failed; subsystems depending on redis will degrade",
            exc_info=True,
        )
        return None


def reset_redis_for_test() -> None:
    """
    仅供测试:清掉进程级缓存,让下次 get_redis() 重新初始化。
    生产代码不应调用本函数。
    """
    global _client, _init_failed
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _init_failed = False


def _redact_url(url: str) -> str:
    """日志安全:把 redis://user:password@host 中的 password 脱敏。"""
    if "@" not in url:
        return url
    scheme_and_creds, host_and_rest = url.rsplit("@", 1)
    if "//" not in scheme_and_creds:
        return url
    scheme, creds = scheme_and_creds.split("//", 1)
    if ":" not in creds:
        return url
    user, _ = creds.split(":", 1)
    return f"{scheme}//{user}:***@{host_and_rest}"


__all__ = ["get_redis", "reset_redis_for_test"]
