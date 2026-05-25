"""
HookManager —— Hook 注册中心 + 事件分发调度

业务 service / 主 Agent loop / Adapter 通过本模块 fire 事件,HookManager 负责:
1. 同步 hook 链式调用,任意一个返回 block 立即抛 HookBlockedException
2. 异步 hook 投递到线程池,主流程不等返回
3. 决策聚合:把所有同步 hook 的 inject / replace_input 决策合并返回

并发模型:
- 同步 hook 用 await 顺序执行(保证决策顺序可预期)
- 异步 hook 用 asyncio.create_task 在事件循环中并发跑(发后即忘)
- 全局单例 hook_manager 在启动时注册各类 hook,运行时只读

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


# ============================================================
# HookManager
# ============================================================

class HookManager:
    """
    全局 Hook 注册中心 + 事件分发器。

    使用方式(全局单例,见模块底部 hook_manager):
        # 启动时注册
        hook_manager.register_sync(HookEvent.PRE_TOOL_USE, my_permission_hook)
        hook_manager.register_async(HookEvent.PRE_TOOL_USE, my_audit_hook)

        # 业务代码 fire(同步路径,会等同步 hook 决策返回)
        result = await hook_manager.fire(HookEvent.PRE_TOOL_USE, ctx)
        if result.decision == "inject":
            ...
        if result.decision == "replace_input":
            new_input = result.updated_input

        # 业务代码 emit(纯异步,不等返回)
        hook_manager.emit(HookEvent.PRE_TOOL_USE, ctx)
    """

    def __init__(self) -> None:
        self._sync_hooks: dict[HookEvent, list[SyncHook]] = defaultdict(list)
        self._async_hooks: dict[HookEvent, list[AsyncHook]] = defaultdict(list)

    # --------------------------------------------------------
    # 注册
    # --------------------------------------------------------

    def register_sync(self, event: HookEvent, hook: SyncHook) -> None:
        """注册一个同步 hook 到指定事件。"""
        self._sync_hooks[event].append(hook)

    def register_async(self, event: HookEvent, hook: AsyncHook) -> None:
        """注册一个异步 hook 到指定事件。"""
        self._async_hooks[event].append(hook)

    def clear(self) -> None:
        """清空所有注册(测试用)。"""
        self._sync_hooks.clear()
        self._async_hooks.clear()

    # --------------------------------------------------------
    # 触发
    # --------------------------------------------------------

    async def fire(self, event: HookEvent, ctx: HookContext) -> HookResult:
        """
        触发同步 hook 链 + 异步 hook(发后即忘),返回聚合后的同步决策。

        语义:
        - 同步 hook 按注册顺序串行执行
        - 任一 hook 返回 decision=block → 抛 HookBlockedException(中断主流程)
        - 任一 hook 返回 decision=replace_input → 后续 hook 看到的 ctx.tool_input 是更新后的值
        - 多个 hook 都返回 decision=inject → 注入消息按顺序拼接
        - 同一次 fire 中不允许同时产生 inject 与 replace_input 两类决策(协议约束),
          违反会抛 ValueError —— 提示开发者重构 hook 注册关系
        - 异步 hook 在同步链跑完后投递,拿到的是经过 replace_input 更新的最终态 ctx 拷贝

        最终返回:
        - 至少一个 inject 且无 replace_input → decision=inject,injected_message=按序拼接
        - 至少一个 replace_input 且无 inject → decision=replace_input,updated_input=最后一次的值
        - 都是 continue → decision=continue
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
                # 同步 hook 内部异常:记录日志,继续执行后续 hook(避免一个坏 hook 拖垮主流程)
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
                # 让后续 hook 看到更新后的 input
                ctx.tool_input = result.updated_input

        # 协议约束:一次 fire 不允许同时产生 inject 与 replace_input
        if injected_parts and replace_seen:
            raise ValueError(
                f"HookManager: event={event.value} 注册的 hooks 同时返回了 inject 与 "
                "replace_input,协议禁止。请把这两种决策拆到不同事件,或合并为同一个 hook 内逻辑判断。"
            )

        # 同步链跑完后投递异步 hook(发后即忘),传 ctx 深拷贝避免后续修改污染审计
        self._dispatch_async(event, ctx)

        # 聚合最终决策
        if injected_parts:
            return HookResult(
                decision="inject",
                injected_message="\n".join(injected_parts),
            )
        if replace_seen:
            return HookResult(decision="replace_input", updated_input=last_updated_input)
        return HookResult(decision="continue")

    def emit(self, event: HookEvent, ctx: HookContext) -> None:
        """
        仅触发异步 hook,不等返回。
        每个异步 hook 用 asyncio.create_task 投递到当前事件循环。
        异步 hook 内部异常由 _run_async 捕获并记录,不影响主流程。

        传入的 ctx 会被深拷贝后再投递,避免后续修改污染异步 hook 看到的快照。
        """
        self._dispatch_async(event, ctx)

    # --------------------------------------------------------
    # 内部:异步分发
    # --------------------------------------------------------

    def _dispatch_async(self, event: HookEvent, ctx: HookContext) -> None:
        """
        把当前 ctx 深拷贝后投递给所有异步 hook。
        ctx.tool_input / extra 可能含嵌套 dict,必须 deepcopy 防止后续修改污染。
        """
        async_hooks = self._async_hooks.get(event, [])
        if not async_hooks:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有正在运行的 event loop(同步上下文),静默丢弃
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
        """异步 hook 包装:统一捕获异常,避免污染事件循环。"""
        try:
            await hook.handle(ctx)
        except Exception:
            logger.exception(
                "Async hook %s raised on event %s, suppressed",
                type(hook).__name__,
                ctx.event.value,
            )


# ============================================================
# 全局单例
# ============================================================

hook_manager = HookManager()
