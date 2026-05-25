"""
ErrorRecovery —— 主 Agent 三路错误恢复

- max_tokens       注入"请继续",最多重试 3 次
- prompt_too_long  调 LLM 摘要历史替换 messages_history,重试一次
- API 错误         指数退避 base * 2^attempt + 随机抖动,最多 5 次

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from dataclasses import dataclass


@dataclass
class RecoveryDecision:
    """恢复策略决策结果"""
    should_retry: bool
    delay_seconds: float = 0.0
    inject_user_message: str = ""  # 非空时把这条消息追加到 messages 再重试
    truncate_history: bool = False  # True 时调 context_compactor 摘要历史
    give_up_reason: str = ""        # should_retry=False 时填


class ErrorRecovery:
    """主 Agent loop 调 LLM 失败时的统一恢复决策。"""

    async def on_max_tokens(self, attempt: int) -> RecoveryDecision:
        """
        LLM 返回 stop_reason=max_tokens。
        TODO[F-recovery]: 实装"注入请继续"重试逻辑,最多 3 次。
        """
        raise NotImplementedError("[TODO/F-recovery] on_max_tokens 未实装")

    async def on_prompt_too_long(self, attempt: int) -> RecoveryDecision:
        """
        API 返回上下文过长错误。
        TODO[F-recovery]: 实装"调 LLM 摘要历史 → 替换 → 重试一次"。
        """
        raise NotImplementedError("[TODO/F-recovery] on_prompt_too_long 未实装")

    async def on_api_error(
        self,
        exc: Exception,
        attempt: int,
    ) -> RecoveryDecision:
        """
        API 错误(网络 / 5xx / 限流)。
        TODO[F-recovery]: 实装指数退避,最多 5 次重试。
        """
        raise NotImplementedError("[TODO/F-recovery] on_api_error 未实装")


error_recovery = ErrorRecovery()
