"""
PostExecutionHook —— 工具调用后异步审计

注册到 HookEvent.POST_TOOL_USE，在主 Agent loop 每次工具调用后 fire。
属于 AsyncHook：发后即忘，不阻塞主流程。

当前实装：
1. 记录工具调用审计日志（tool_name / tool_input / tool_output / user_id / conversation_id）

预留（依赖未实装模块）：
- TODO[audit]: 接通 audit_service，写 audit_logs 表
- TODO[diff]:  识别 create_file / edit_file 产物 → 调 diff_service → 推 diff 消息
- TODO[preview]: 识别 HTML 产物 → 调 preview_service → 推 preview URL 消息

队伍：咕嘎一辈子队
修改者：咕嘎
修改日期:2026-05-27
"""

import logging

from backend.hooks.base import AsyncHook, HookContext

logger = logging.getLogger(__name__)

# 错误信息日志截断阈值：避免完整堆栈 / API 响应体 / 文件绝对路径直接落盘
_ERROR_LOG_MAX_LEN = 500


def _truncate_error(err: object) -> str:
    """把 error 字段安全截断为短字符串，防止敏感信息泄漏到日志。"""
    text = str(err)
    if len(text) > _ERROR_LOG_MAX_LEN:
        return text[:_ERROR_LOG_MAX_LEN] + "...(truncated)"
    return text


class PostExecutionHook(AsyncHook):
    """工具执行后异步审计。"""

    async def handle(self, ctx: HookContext) -> None:
        tool_name = ctx.tool_name or ""
        tool_input = ctx.tool_input or {}
        tool_output = ctx.tool_output

        # 1. 审计日志（只记 input 的 key 列表，不记 value，防止敏感参数泄漏）
        logger.info(
            "POST_TOOL_USE tool=%s user=%s conversation=%s thread=%s input_keys=%s",
            tool_name,
            ctx.user_id,
            ctx.conversation_id,
            ctx.thread_id,
            list(tool_input.keys()),
        )

        # 2. 错误输出单独 warning，方便排查
        # 注意：error 内容可能含路径 / 堆栈 / API 响应体，做截断防止敏感信息泄漏
        if isinstance(tool_output, dict) and tool_output.get("error"):
            logger.warning(
                "POST_TOOL_USE tool=%s returned error=%s user=%s conversation=%s",
                tool_name,
                _truncate_error(tool_output["error"]),
                ctx.user_id,
                ctx.conversation_id,
            )

        # TODO[audit]: audit_service.record(ctx) 写 audit_logs 表
        # TODO[diff]:  if tool_name in {"create_file", "edit_file"}: diff_service.push(ctx)
        # TODO[preview]: if _is_html_output(tool_output): preview_service.push(ctx)
