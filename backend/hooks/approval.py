"""
ApprovalHook —— 高危工具审批闭环

注册到 HookEvent.PRE_TOOL_USE，对预定义高危工具拦截：
1. 创建 ApprovalBlock 写入消息（依赖 message_service） + 通过 stream_service 推 SSE
2. fire APPROVAL_REQUESTED 事件（异步 hook 用于审计）
3. 创建 asyncio.Event，await 阻塞主 Agent loop 等待用户决策
4. WS handler 收到 ApprovalDecisionRequest → 调 decide(block_id, decision) set event
5. hook 拿到结果：approve → return continue；reject → return block

超时机制：
- 默认 10 分钟无决策则降级为 reject（防止永久卡住主流程）
- 超时阈值由 _APPROVAL_TIMEOUT_SECONDS 控制

模块级状态：
- _pending_approvals: dict[block_id, _PendingApproval]
- decide() 是 WS handler 的入口，按 block_id set event

队伍：咕嘎一辈子队
修改者：咕嘎
修改日期：2026-05-27
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from dataclasses import dataclass
from typing import Literal, Optional

from backend.core.utils import gen_uuid
from backend.hooks.base import HookContext, HookEvent, HookResult, SyncHook

logger = logging.getLogger(__name__)


# 高危工具清单：执行前必须用户审批
# 当前清单覆盖文件写入类工具；web_search / bash 等工具未来加入时也归此类
_HIGH_RISK_TOOLS: frozenset[str] = frozenset({
    "create_file",
    "edit_file",
    # TODO: 等以下工具实装后加入
    #   "web_search"  网页查找类工具
    #   "run_command" / "bash"  shell 命令执行类工具
})

# 用户无决策的超时阈值（秒），超时降级为 reject
_APPROVAL_TIMEOUT_SECONDS = 600

# 通知通道就绪开关：False 时 ApprovalHook 直接放行，不走审批等待。
# 防止前端收不到 ApprovalBlock（message_service / stream_service.push_approval_block 未实装）
# 时主 Agent loop 静默卡住 10 分钟超时。
# message_service + stream 推送链路接通后改为 True（或删守卫）。
_APPROVAL_CHANNEL_READY = True

ApprovalDecision = Literal["approve", "reject"]


@dataclass
class _PendingApproval:
    """单个待审批请求的状态。"""
    block_id: str
    message_id: str            # ApprovalBlock 落库所在的 message id,decide 时用来回写持久化字段
    event: asyncio.Event
    decision: Optional[ApprovalDecision] = None
    reject_reason: Optional[str] = None


# 模块级全局状态：block_id → 待审批记录
# WS handler / HTTP handler 通过 block_id 索引到 event 来 set 决策
_pending_approvals: dict[str, _PendingApproval] = {}


# ============================================================
# WS handler 入口
# ============================================================

async def decide(
    block_id: str,
    decision: ApprovalDecision,
    reject_reason: Optional[str] = None,
) -> bool:
    """
    审批决策入口。HTTP / WS handler 收到用户决策后调用:

    1. 写库 —— 把 ApprovalBlock 的 status / decided_at / reject_reason 持久化
       (修复"刷新页面 ApprovalBlock 又变 pending"的 bug,DB 是真相源)
    2. 唤醒 hook —— set asyncio.Event,让 ApprovalHook 拿决策决定 continue / block

    返回 True 表示成功投递;False 表示该 block_id 已不存在(超时清理 / 重复决策)。

    顺序约束:必须**先写库再 set event**。否则 hook 醒来后立即让主 Agent loop 继续,
    用户刷新页面的瞬间可能恰好读到旧的 pending 状态(虽然窗口很短,但语义不正确)。
    """
    pending = _pending_approvals.get(block_id)
    if pending is None:
        logger.warning("approval.decide: block_id=%s 不存在或已被清理", block_id)
        return False

    # 写库:状态 + 决策时间 + 拒绝原因(approve 时 reject_reason 为 None)
    from datetime import datetime, timezone
    from backend.services.message_service import message_service
    persisted_status = "approved" if decision == "approve" else "rejected"
    decided_at_iso = datetime.now(timezone.utc).isoformat()
    try:
        await message_service.update_approval_block(
            pending.message_id,
            block_id,
            status=persisted_status,
            decided_at=decided_at_iso,
            reject_reason=reject_reason if decision == "reject" else None,
        )
    except Exception:
        # 写库失败不阻塞唤醒——hook 仍要继续工具执行决策。
        # 只是刷新页面会看到旧 pending 状态,记日志让人能查。
        logger.exception(
            "approval.decide 写库失败 block_id=%s message_id=%s",
            block_id, pending.message_id,
        )

    pending.decision = decision
    pending.reject_reason = reject_reason
    pending.event.set()
    return True


# ============================================================
# Hook 实装
# ============================================================

class ApprovalHook(SyncHook):
    """
    高危工具审批同步 hook。注册到 PRE_TOOL_USE。

    decision 语义：
    - 非高危工具 → continue
    - 高危且 approve → continue
    - 高危且 reject / timeout → block（block_reason 含拒绝原因）
    """

    async def handle(self, ctx: HookContext) -> HookResult:
        tool_name = ctx.tool_name or ""
        if tool_name not in _HIGH_RISK_TOOLS:
            return HookResult(decision="continue")

        # 守卫：通知通道未就绪时直接放行，避免主 Agent loop 静默等超时
        # （前端收不到 ApprovalBlock，用户无感知，10 分钟后自动 reject 体验极差）
        if not _APPROVAL_CHANNEL_READY:
            logger.warning(
                "APPROVAL channel not ready, bypassing approval for tool=%s "
                "(等 message_service / stream push_approval_block 接通后翻 _APPROVAL_CHANNEL_READY=True)",
                tool_name,
            )
            return HookResult(decision="continue")

        # 1. 生成 block_id + 推 ApprovalBlock(消息落库 → 拿到 message_id) → 注册待审批
        block_id = gen_uuid()
        try:
            persisted_message_id = await self._publish_approval_block(ctx, block_id, tool_name)
        except Exception:
            logger.exception(
                "ApprovalBlock 创建失败 block_id=%s tool=%s, 直接放行",
                block_id, tool_name,
            )
            return HookResult(decision="continue")

        if not persisted_message_id:
            # 落库失败时也直接放行,避免主 Agent loop 卡死等永远不会到来的决策
            logger.warning(
                "ApprovalBlock 未落库 block_id=%s tool=%s, 直接放行",
                block_id, tool_name,
            )
            return HookResult(decision="continue")

        pending = _PendingApproval(
            block_id=block_id,
            message_id=persisted_message_id,
            event=asyncio.Event(),
        )
        _pending_approvals[block_id] = pending

        try:
            # 2. fire APPROVAL_REQUESTED（异步 hook 监听做审计；避免循环 import 用本地 import）
            from backend.hooks.manager import hook_manager
            approval_ctx = ctx.model_copy(update={
                "event": HookEvent.APPROVAL_REQUESTED,
                "extra": {**ctx.extra, "approval_block_id": block_id},
            })
            hook_manager.emit(HookEvent.APPROVAL_REQUESTED, approval_ctx)

            logger.info(
                "APPROVAL_REQUESTED tool=%s block_id=%s user=%s conversation=%s",
                tool_name, block_id, ctx.user_id, ctx.conversation_id,
            )

            # 3. 阻塞等待用户决策，带超时
            try:
                await asyncio.wait_for(
                    pending.event.wait(),
                    timeout=_APPROVAL_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "APPROVAL timeout tool=%s block_id=%s, treated as reject",
                    tool_name, block_id,
                )
                self._fire_decided(ctx, block_id, "reject", "timeout")
                # 超时也持久化(否则刷新页面 ApprovalBlock 仍是 pending)
                from datetime import datetime, timezone
                from backend.services.message_service import message_service
                try:
                    await message_service.update_approval_block(
                        pending.message_id,
                        block_id,
                        status="rejected",
                        decided_at=datetime.now(timezone.utc).isoformat(),
                        reject_reason="timeout",
                    )
                except Exception:
                    logger.exception(
                        "approval timeout 写库失败 block_id=%s message_id=%s",
                        block_id, pending.message_id,
                    )
                return HookResult(
                    decision="block",
                    block_reason=f"工具 '{tool_name}' 审批超时（{_APPROVAL_TIMEOUT_SECONDS}s 未决策），已自动拒绝",
                )

            # 4. 处理决策结果(decide() 已经写库,这里只 fire audit hook + 决定 continue/block)
            self._fire_decided(ctx, block_id, pending.decision or "reject", pending.reject_reason)

            if pending.decision == "approve":
                logger.info(
                    "APPROVAL approved tool=%s block_id=%s user=%s",
                    tool_name, block_id, ctx.user_id,
                )
                return HookResult(decision="continue")

            reason = pending.reject_reason or "用户拒绝"
            logger.info(
                "APPROVAL rejected tool=%s block_id=%s reason=%s user=%s",
                tool_name, block_id, reason, ctx.user_id,
            )
            return HookResult(
                decision="block",
                block_reason=f"工具 '{tool_name}' 被用户拒绝执行：{reason}",
            )

        finally:
            # 无论 approve / reject / timeout / 异常,都清理本 block 的待审批记录
            _pending_approvals.pop(block_id, None)

    # --------------------------------------------------------
    # 内部辅助
    # --------------------------------------------------------

    @staticmethod
    async def _publish_approval_block(
        ctx: HookContext,
        block_id: str,
        tool_name: str,
    ) -> Optional[str]:
        """
        创建 ApprovalBlock 落库 + 推送 SSE。
        返回创建的 message_id(供 _PendingApproval 记录,decide 时回写持久化字段);
        落库失败返回 None,调用方自行兜底。
        """
        from backend.adapters.events import BlockStartEvent
        from backend.domain.message import ApprovalBlock
        from backend.services.message_service import message_service
        from backend.services.stream_service import stream_service

        # detail 用 JSON 序列化 tool_input,前端可解析后按 tool_name 结构化渲染
        # (例如 create_file 显示 path / size / 折叠的 content)。
        # 不可序列化的字段(罕见)兜底用 default=str,保证 detail 永远是合法 JSON。
        try:
            detail_json = _json.dumps(ctx.tool_input or {}, ensure_ascii=False, default=str)
        except Exception:
            detail_json = str(ctx.tool_input or {})

        approval_block = ApprovalBlock(
            block_id=block_id,
            action=tool_name,
            detail=detail_json,
        )

        try:
            msg = await message_service.create_assistant_message(
                conversation_id=ctx.conversation_id or "",
                agent_id=ctx.agent_id or "",
                content_blocks=[approval_block],
                thread_id=ctx.thread_id,
            )
            message_id = getattr(msg, "id", None)
        except Exception:
            logger.exception(
                "ApprovalBlock 落库失败 block_id=%s tool=%s", block_id, tool_name
            )
            return None

        try:
            event = BlockStartEvent(
                agent_id=ctx.agent_id or "",
                thread_id=ctx.thread_id or "",
                message_id=message_id or "",
                block=approval_block,
            )
            await stream_service.push_event(ctx.conversation_id or "", event)
        except Exception:
            logger.exception(
                "ApprovalBlock SSE 推送失败 block_id=%s tool=%s", block_id, tool_name
            )

        return message_id

    @staticmethod
    def _fire_decided(
        ctx: HookContext,
        block_id: str,
        decision: ApprovalDecision,
        reason: Optional[str],
    ) -> None:
        """触发 APPROVAL_DECIDED 异步 hook（审计用）。"""
        from backend.hooks.manager import hook_manager
        decided_ctx = ctx.model_copy(update={
            "event": HookEvent.APPROVAL_DECIDED,
            "extra": {
                **ctx.extra,
                "approval_block_id": block_id,
                "approval_decision": decision,
                "approval_reject_reason": reason,
            },
        })
        hook_manager.emit(HookEvent.APPROVAL_DECIDED, decided_ctx)
