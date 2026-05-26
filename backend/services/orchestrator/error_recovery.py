"""
ErrorRecovery —— 主 Agent 三路错误恢复

对应主 Agent 设计文档第十节,LLM 调用失败的三类原因 + 对应恢复策略:

| 错误类型         | 触发                               | 恢复策略                               |
|------------------|------------------------------------|--------------------------------------|
| max_tokens       | LLM 返回 stop_reason=max_tokens    | 注入"请继续"让其续写,最多 3 次重试    |
| prompt_too_long  | API 返回上下文过长错误             | 调 context_compactor 摘要 → 重试 1 次 |
| api_error        | 网络 / 5xx / rate limit            | 指数退避,最多 5 次重试                |

调用约定:
- max_tokens 路径:_agent_loop 拿到 LLM response 后判 stop_reason,
  如果是 max_tokens,调 on_max_tokens(attempt) 拿决策
- prompt_too_long / api_error 路径:try/except 捕获异常,
  先调 classify_api_error(exc) 分类,再调对应的 on_xxx
- RecoveryDecision.should_retry=False 时 _agent_loop 应该 raise,
  让 start_loop 兜底 mark_error

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

import anthropic


logger = logging.getLogger(__name__)


# ============================================================
# 重试上限与退避参数
# ============================================================

# max_tokens 路径:LLM 输出截断时,注入"请继续"重试上限
_MAX_TOKENS_RETRY_LIMIT = 3

# prompt_too_long 路径:摘要后还超长说明有别的问题,不再重试
_PROMPT_TOO_LONG_RETRY_LIMIT = 1

# api_error 路径:指数退避重试上限
_API_ERROR_RETRY_LIMIT = 5
# 指数退避 base = 1s,即 1, 2, 4, 8, 16 秒(再加 0~1s 抖动)
_API_ERROR_BACKOFF_BASE = 1.0
# 退避上限,防止 attempt 大时等太久
_API_ERROR_BACKOFF_CAP = 30.0

# max_tokens 恢复时注入给 LLM 的"请继续"提示
_CONTINUE_PROMPT = (
    "你的上一轮回复因为 max_tokens 被截断,请继续完成你刚才在做的事。"
    "如果上一轮工具调用块没输出完整,请重新发起完整的工具调用。"
)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RecoveryDecision:
    """恢复策略决策结果"""
    should_retry: bool
    delay_seconds: float = 0.0
    inject_user_message: str = ""  # 非空时把这条消息追加到 messages 再重试
    truncate_history: bool = False  # True 时调 context_compactor 摘要历史
    give_up_reason: str = ""        # should_retry=False 时填


# ============================================================
# 异常分类
# ============================================================

# 不该重试的"致命"错误 —— 重试也是同样结果,直接 give up
_FATAL_EXCEPTION_TYPES: tuple[type[Exception], ...] = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.UnprocessableEntityError,
)

# prompt_too_long 的 BadRequestError 错误消息特征
# Anthropic 实际返回类似:"prompt is too long: ... > 200000 maximum"
_PROMPT_TOO_LONG_HINTS = (
    "prompt is too long",
    "context length",
    "context_length_exceeded",
    "max input length",
    "input is too long",
)


def classify_api_error(exc: Exception) -> str:
    """
    把 LLM 调用抛出的异常分类成三种恢复路径之一。

    返回值:
        "prompt_too_long"  → on_prompt_too_long
        "api_error"        → on_api_error(指数退避)
        "fatal"            → 不重试,直接 raise

    分类规则:
    - 致命错误(认证 / 权限 / 资源不存在 / 422)→ fatal
    - BadRequestError 且消息含上下文超长关键字 → prompt_too_long
    - BadRequestError 其他(请求格式错)→ fatal,重试无意义
    - RateLimitError / Timeout / Connection / 5xx / 其他 APIError → api_error
    - 非 anthropic 异常 → fatal,可能是代码 bug 不该走重试
    """
    if isinstance(exc, _FATAL_EXCEPTION_TYPES):
        return "fatal"

    if isinstance(exc, anthropic.BadRequestError):
        msg = str(exc).lower()
        if any(hint in msg for hint in _PROMPT_TOO_LONG_HINTS):
            return "prompt_too_long"
        # 其他 BadRequest(请求格式错 / 字段非法等)重试也是同样结果
        return "fatal"

    if isinstance(exc, anthropic.APIError):
        # 包括 RateLimitError / APITimeoutError / APIConnectionError /
        # InternalServerError / 其他 APIStatusError
        return "api_error"

    # 非 anthropic 异常,可能是代码 bug —— 不重试,让 start_loop 兜底
    return "fatal"


# ============================================================
# ErrorRecovery
# ============================================================

class ErrorRecovery:
    """主 Agent loop 调 LLM 失败时的统一恢复决策。"""

    async def on_max_tokens(self, attempt: int) -> RecoveryDecision:
        """
        LLM 返回 stop_reason=max_tokens(输出被截断)。

        策略:注入"请继续"消息,无延迟立即重试,最多 _MAX_TOKENS_RETRY_LIMIT 次。
        attempt 从 0 开始;attempt >= 上限时给 up,避免 LLM 陷入冗长输出循环。
        """
        if attempt >= _MAX_TOKENS_RETRY_LIMIT:
            return RecoveryDecision(
                should_retry=False,
                give_up_reason=(
                    f"max_tokens 已重试 {attempt} 次仍被截断,"
                    "可能 LLM 陷入冗长输出循环,放弃本轮"
                ),
            )
        return RecoveryDecision(
            should_retry=True,
            inject_user_message=_CONTINUE_PROMPT,
        )

    async def on_prompt_too_long(self, attempt: int) -> RecoveryDecision:
        """
        API 返回上下文过长错误。

        策略:第 0 次告诉 service 摘要历史(truncate_history=True),
        让 service 调 context_compactor.global_summarize 压缩 messages 后重试一次。

        摘要后还超长(attempt >= 1)说明:
        - 单条消息体积过大(单个 tool_result 就超 context)→ 摘要无法挽救
        - 系统 prompt 本身太大(配置错误)
        这两种情况重试意义不大,直接放弃。
        """
        if attempt >= _PROMPT_TOO_LONG_RETRY_LIMIT:
            return RecoveryDecision(
                should_retry=False,
                give_up_reason=(
                    "prompt_too_long 摘要后仍超长,可能单条消息或 system prompt "
                    "本身超过模型上下文,放弃本轮"
                ),
            )
        return RecoveryDecision(
            should_retry=True,
            truncate_history=True,
        )

    async def on_api_error(
        self,
        exc: Exception,
        attempt: int,
    ) -> RecoveryDecision:
        """
        API 错误(网络 / 5xx / rate limit)。

        策略:指数退避 base * 2^attempt + 0~1s 随机抖动,
        attempt 从 0 起,最多 _API_ERROR_RETRY_LIMIT 次。
        退避时间 cap 在 _API_ERROR_BACKOFF_CAP 防止等太久。

        随机抖动避免多个 loop 同时退避后再同时重试造成 thundering herd。
        """
        if attempt >= _API_ERROR_RETRY_LIMIT:
            return RecoveryDecision(
                should_retry=False,
                give_up_reason=(
                    f"API 错误已重试 {attempt} 次仍失败:"
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        backoff = _API_ERROR_BACKOFF_BASE * (2 ** attempt)
        backoff = min(backoff, _API_ERROR_BACKOFF_CAP)
        delay = backoff + random.uniform(0, 1)

        logger.warning(
            "api_error attempt=%d: %s, will retry after %.2fs",
            attempt,
            exc,
            delay,
        )
        return RecoveryDecision(
            should_retry=True,
            delay_seconds=delay,
        )


error_recovery = ErrorRecovery()
