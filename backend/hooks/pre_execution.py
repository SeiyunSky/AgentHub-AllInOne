"""
PreExecutionHook —— 工具调用前同步拦截

注册到 HookEvent.PRE_TOOL_USE，在主 Agent loop 每次工具调用前 fire。

当前实装的拦截规则：
1. 危险工具黑名单：直接 block（当前 19 个工具里暂无，预留扩展）
2. 文件工具沙箱路径前置校验：create_file / read_file / edit_file / list_directory
   的 path 字段包含路径穿越特征时提前 block（双重防御，handler 层仍有自己的校验）
3. 放行时记 INFO 日志

待补充（依赖 auth 模块完成后填）：
- TODO[auth]: 用户权限校验（检查 user_id 是否有权调用该工具）
- TODO[rate-limit]: 限流检查（接 Redis 计数器）

队伍：咕嘎一辈子队
修改者：咕嘎
修改日期：2026-05-27
"""

import logging
from pathlib import PurePosixPath

from backend.hooks.base import HookContext, HookResult, SyncHook

logger = logging.getLogger(__name__)

# 直接 block 的危险工具名（预留，当前 19 个工具暂无此类）
_BLOCKED_TOOLS: frozenset[str] = frozenset()

# 需要沙箱路径检查的文件类工具
_FILE_TOOLS: frozenset[str] = frozenset({
    "create_file",
    "read_file",
    "edit_file",
    "list_directory",
})


def _is_path_traversal(path: str) -> bool:
    """
    判断路径是否有穿越沙箱的特征：
    - 绝对路径（'/' 开头或 Windows 盘符）
    - 含 '..' 路径段

    注意：本函数不处理 URL 编码（%2e%2e）或 Unicode 规范化绕过，
    属于双重防御的第一层（快速拦截），handler 层的 _resolve_sandbox_path
    会做完整的路径规范化和沙箱边界校验，是真正的安全边界。
    """
    if not isinstance(path, str):
        return False
    normalized = path.replace("\\", "/")
    if normalized.startswith("/"):
        return True
    if len(normalized) >= 2 and normalized[1] == ":":
        return True
    try:
        parts = PurePosixPath(normalized).parts
    except Exception:
        return False
    return ".." in parts


class PreExecutionHook(SyncHook):
    """工具执行前同步拦截。"""

    async def handle(self, ctx: HookContext) -> HookResult:
        # SyncHook 的抽象方法签名本身就是 async def（见 base.py），
        # 这里 async 是必须的，与"同步"指的是 HookManager 串行调度方式无关。
        tool_name = ctx.tool_name or ""
        tool_input = ctx.tool_input or {}

        # 1. 危险工具黑名单
        if tool_name in _BLOCKED_TOOLS:
            logger.warning(
                "PRE_TOOL_USE blocked tool=%s user=%s conversation=%s",
                tool_name, ctx.user_id, ctx.conversation_id,
            )
            return HookResult(
                decision="block",
                block_reason=f"工具 '{tool_name}' 已被系统禁用",
            )

        # 2. 文件工具沙箱路径前置校验
        if tool_name in _FILE_TOOLS:
            path = tool_input.get("path", "")
            if _is_path_traversal(path):
                logger.warning(
                    "PRE_TOOL_USE blocked path traversal tool=%s path=%r user=%s",
                    tool_name, path, ctx.user_id,
                )
                return HookResult(
                    decision="block",
                    block_reason=f"路径 '{path}' 包含路径穿越，只允许操作当前会话目录下的文件",
                )

        # TODO[auth]: 用户权限校验
        # TODO[rate-limit]: 限流检查

        # 3. 放行日志
        logger.info(
            "PRE_TOOL_USE tool=%s user=%s conversation=%s thread=%s",
            tool_name, ctx.user_id, ctx.conversation_id, ctx.thread_id,
        )
        return HookResult(decision="continue")
