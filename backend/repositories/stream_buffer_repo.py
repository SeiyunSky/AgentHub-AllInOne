"""
StreamEventBuffer —— Redis 事件缓冲(刷新回放用)

职责:
- 缓冲每个会话最近 N 秒的 SSE 事件
- 支持按 message_id 回放该消息之后的所有事件
- 自动清理过期数据(TTL)

队伍:咕嘎一辈子队
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Redis key 前缀
_KEY_PREFIX = "agenthub:events:"
# 事件缓冲 TTL (秒)
_TTL_SECONDS = 600
# 单会话最大事件数
_MAX_EVENTS = 500


class StreamEventBuffer:
    """Redis 事件缓冲(按消息回放)。"""

    def __init__(self, conversation_id: str):
        self.conv_id = conversation_id
        self.key = f"{_KEY_PREFIX}{conversation_id}"

    def push(self, event_json: str) -> None:
        """
        推入事件到缓冲队列。
        左侧推入(LPUSH),保持时间正序(新事件在左)。

        Args:
            event_json: 序列化后的事件 JSON 字符串
        """
        from backend.core.redis import get_redis

        r = get_redis()
        if r is None:
            # Redis 未配置,静默降级
            return

        try:
            # LPUSH + LTRIM 保证队列长度
            r.lpush(self.key, event_json)
            r.ltrim(self.key, 0, _MAX_EVENTS - 1)
            # 刷新 TTL
            r.expire(self.key, _TTL_SECONDS)
        except Exception:
            logger.warning(
                "Failed to push event to Redis buffer for conv=%s",
                self.conv_id,
                exc_info=True,
            )

    def replay_from_message(self, after_message_id: Optional[str]) -> list[str]:
        """
        回放指定消息之后的所有事件。

        Redis 队列结构(左新右旧):
        [event_newest, ..., event_older, ..., event_oldest]

        回放逻辑:
        1. after_message_id == "__START__": 回放全部事件(从最开始)
        2. 找到队列中第一个 message_id === after_message_id 的事件(最新那条)
        3. 回放该位置之后的所有事件(更旧的事件,需要反转成旧→新顺序)

        Args:
            after_message_id: 回放该消息ID之后的事件；
                             "__START__" 表示从最开始回放；
                             None 表示不回放

        Returns:
            事件 JSON 列表(时间正序:旧→新)
        """
        from backend.core.redis import get_redis

        r = get_redis()
        if r is None:
            return []

        try:
            # LRANGE 0 -1 拿全部(时间倒序:新→旧)
            all_events = r.lrange(self.key, 0, -1)
            if not all_events:
                return []

            # 未指定 after_message_id,不回放
            if after_message_id is None:
                return []

            # 特殊字符串 "__START__": 从最开始回放全部
            if after_message_id == "__START__":
                logger.info(
                    "Replay all %d events for conv=%s (from start)",
                    len(all_events),
                    self.conv_id,
                )
                return list(reversed(all_events))

            # 找到 after_message_id 在队列中第一次出现的位置
            # (同一 message_id 可能有多个事件:agent_start, block_start, block_delta...)
            # 我们要找"该消息的最新事件",也就是队列中第一个出现的
            target_idx = -1
            for idx, event_json in enumerate(all_events):
                try:
                    event = json.loads(event_json)
                    if event.get("message_id") == after_message_id:
                        target_idx = idx
                        break  # 找到第一个(最新的)就停止
                except Exception:
                    continue

            # 如果找到了,返回该位置之后的所有事件
            if target_idx >= 0:
                # all_events[target_idx+1:] 是更旧的事件
                # 需要反转成旧→新顺序
                result = list(reversed(all_events[:target_idx]))
                logger.info(
                    "Replay %d events after message=%s for conv=%s",
                    len(result),
                    after_message_id,
                    self.conv_id,
                )
                return result

            # 未找到该 message_id,不回放(避免重复推送旧事件)
            # 场景:消息ID对应的轮次已完成很久,Redis 缓冲已过期,队列里全是更新的轮次
            logger.info(
                "message_id=%s not found in buffer, skip replay for conv=%s",
                after_message_id,
                self.conv_id,
            )
            return []
        except Exception:
            logger.warning(
                "Failed to replay events from Redis buffer for conv=%s",
                self.conv_id,
                exc_info=True,
            )
            return []

    def replay_for_active_threads(self, active_thread_ids: list[str]) -> list[str]:
        """
        从 Redis 缓冲中提取指定 Thread 的所有事件(用于 SSE 回放)。

        流程:
        1. 从 Redis 读取全部事件
        2. 过滤出 thread_id 在 active_thread_ids 中的事件
        3. 按时间正序返回(旧→新)

        Args:
            active_thread_ids: 活跃 Thread ID 列表(从数据库查询得到)

        Returns:
            事件 JSON 列表(时间正序:旧→新)
        """
        from backend.core.redis import get_redis

        r = get_redis()
        if r is None:
            return []

        if not active_thread_ids:
            return []

        try:
            # LRANGE 0 -1 拿全部(时间倒序:新→旧)
            all_events = r.lrange(self.key, 0, -1)
            if not all_events:
                return []

            # 过滤出属于活跃 Thread 的事件
            matched_events = []
            for event_json in all_events:
                try:
                    event = json.loads(event_json)
                    thread_id = event.get("thread_id")
                    if thread_id and thread_id in active_thread_ids:
                        matched_events.append(event_json)
                except Exception:
                    continue

            # 反转成时间正序(旧→新)
            result = list(reversed(matched_events))
            if result:
                logger.info(
                    "Replay %d events for %d active threads in conv=%s",
                    len(result),
                    len(active_thread_ids),
                    self.conv_id,
                )
            return result
        except Exception:
            logger.warning(
                "Failed to replay events for active threads in conv=%s",
                self.conv_id,
                exc_info=True,
            )
            return []

    def clear(self) -> None:
        """清空缓冲。"""
        from backend.core.redis import get_redis

        r = get_redis()
        if r is None:
            return
        try:
            r.delete(self.key)
        except Exception:
            logger.warning(
                "Failed to clear Redis buffer for conv=%s",
                self.conv_id,
            )


# ============================================================
# 便捷函数
# ============================================================


def push_event_to_buffer(conversation_id: str, event_json: str) -> None:
    """
    把事件推入缓冲队列。

    Args:
        conversation_id: 会话 ID
        event_json: 序列化后的事件 JSON 字符串
    """
    buf = StreamEventBuffer(conversation_id)
    buf.push(event_json)
