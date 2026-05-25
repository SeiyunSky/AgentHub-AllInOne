"""
ContextCompactor —— 主 Agent 短期记忆压缩三层

1. 大工具输出持久化  子 Thread 完整结果不进 messages_history,只留摘要 + thread_id
2. micro_compact     保留最近 N(默认 3)次工具结果,老的折叠为占位
3. 全局摘要          token 超阈值(默认 30K)→ LLM 摘要 → 用摘要 + 最近 5 条替换 history

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from typing import Any


COMPACT_THRESHOLD_TOKENS = 30_000
RECENT_TOOL_RESULTS_KEEP = 3
RECENT_MESSAGES_KEEP_AFTER_SUMMARY = 5


class ContextCompactor:
    """主 Agent loop 每轮结束检查并触发的压缩器。"""

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        粗估 messages 序列的 token 数。
        TODO[F-compact]: 实装(可用 anthropic count_tokens 或 tiktoken 近似)。
        """
        raise NotImplementedError("[TODO/F-compact] estimate_tokens 未实装")

    def micro_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        第二层压缩:保留最近 RECENT_TOOL_RESULTS_KEEP 次工具结果,老的替换为占位。
        TODO[F-compact]: 实装。
        """
        raise NotImplementedError("[TODO/F-compact] micro_compact 未实装")

    async def global_summarize(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        第三层压缩:LLM 摘要历史,返回压缩后的 messages 序列。
        保留最近 RECENT_MESSAGES_KEEP_AFTER_SUMMARY 条原始消息 + 一条摘要 user 消息。
        TODO[F-compact]: 实装(调 llm_client 单独发一次摘要请求)。
        """
        raise NotImplementedError("[TODO/F-compact] global_summarize 未实装")

    async def maybe_compact(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        每轮结束调:检查 token 是否超阈值,超则按三层策略递进压缩。
        TODO[F-compact]: 实装总入口。
        """
        raise NotImplementedError("[TODO/F-compact] maybe_compact 未实装")


context_compactor = ContextCompactor()
