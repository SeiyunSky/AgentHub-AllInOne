"""
HookManager —— Hook 注册中心 + 事件分发调度

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import asyncio
import copy
import logging
from collections import defaultdict
from typing import Optional

from backend.hooks.base import (
    AsyncHook,
    HookBlockedException,
    HookContext,
    HookEvent,
    HookResult,
    SyncHook,
)

logger = logging.getLogger(__name__)


class HookManager:
    """全局 Hook 注册中心 + 事件分发器。"""

    def __init__(self) -> None:
        self._sync_hooks: dict[HookEvent, list[SyncHook]] = defaultdict(list)
        self._async_hooks: dict[HookEvent, list[AsyncHook]] = defaultdict(list)

    # --------------------------------------------------------
    # 注册
    # --------------------------------------------------------

    def register_sync(self, event: HookEvent, hook: SyncHook) -> None:
        self._sync_hooks[event].append(hook)

    def register_async(self, event: HookEvent, hook: AsyncHook) -> None:
        self._async_hooks[event].append(hook)

    def clear(self) -> None:
        self._sync_hooks.clear()
        self._async_hooks.clear()

    # --------------------------------------------------------
    # 触发
    # --------------------------------------------------------

    async def fire(self, event: HookEvent, ctx: HookContext) -> HookResult:
        """
        触发同步 hook 链 + 异步 hook,返回聚合后的同步决策。

        - 任一同步 hook 返回 block → 抛 HookBlockedException
        - 多个 inject → 注入消息按顺序拼接
        - 多个 replace_input → 链式传递,后续 hook 看到更新后的 ctx.tool_input
        - 同次 fire 同时出现 inject 与 replace_input → 抛 ValueError(协议禁止)
        - 异步 hook 在同步链跑完后投递,拿到的是最终态 ctx 的深拷贝
        """
        sync_hooks = self._sync_hooks.get(event, [])

        injected_parts: list[str] = []
        last_updated_input: Optional[dict] = None
        replace_seen = False

        for hook in sync_hooks:
            try:
                result = await hook.handle(ctx)
            except HookBlockedException:
                raise
            except Exception:
                logger.exception(
                    "Sync hook %s raised on event %s, treated as continue",
                    type(hook).__name__,
                    event.value,
                )
                continue

            if result.decision == "block":
                raise HookBlockedException(event, result.block_reason or "blocked")

            if result.decision == "inject" and result.injected_message:
                injected_parts.append(result.injected_message)

            if result.decision == "replace_input" and result.updated_input is not None:
                replace_seen = True
                last_updated_input = result.updated_input
                ctx.tool_input = result.updated_input

        if injected_parts and replace_seen:
            raise ValueError(
                f"HookManager: event={event.value} 注册的 hooks 同时返回了 inject 与 "
                "replace_input,协议禁止。"
            )

        self._dispatch_async(event, ctx)

        if injected_parts:
            return HookResult(
                decision="inject",
                injected_message="\n".join(injected_parts),
            )
        if replace_seen:
            return HookResult(decision="replace_input", updated_input=last_updated_input)
        return HookResult(decision="continue")

    def emit(self, event: HookEvent, ctx: HookContext) -> None:
        """仅触发异步 hook,不等返回。ctx 会被深拷贝后投递。"""
        self._dispatch_async(event, ctx)

    # --------------------------------------------------------
    # 内部:异步分发
    # --------------------------------------------------------

    def _dispatch_async(self, event: HookEvent, ctx: HookContext) -> None:
        async_hooks = self._async_hooks.get(event, [])
        if not async_hooks:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning(
                "async dispatch(%s) called outside running loop, %d hooks dropped",
                event.value,
                len(async_hooks),
            )
            return

        snapshot = copy.deepcopy(ctx)
        for hook in async_hooks:
            loop.create_task(self._run_async(hook, snapshot))

    @staticmethod
    async def _run_async(hook: AsyncHook, ctx: HookContext) -> None:
        try:
            await hook.handle(ctx)
        except Exception:
            logger.exception(
                "Async hook %s raised on event %s, suppressed",
                type(hook).__name__,
                ctx.event.value,
            )


hook_manager = HookManager()
