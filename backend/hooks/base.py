"""
Hook 抽象基类

对应主 Agent 设计第七节。Hook 是切面机制,业务 service / 主 Agent loop 在关键
时刻 fire 事件,审计 / 限流 / Skill 注入 / 权限检查等横切关注点用 Hook 实现,
不散落在业务代码里。

本文件只放抽象基类与数据结构;HookManager(注册中心 + fire/emit 调度)在 manager.py。

两种 Hook 形态:
- SyncHook    阻塞主流程,能影响决策(返回 HookResult,可 block / inject / replace_input)
- AsyncHook   不阻塞,发后即忘(线程池跑),用于审计 / 日志等观察类钩子,无返回值

11 个事件覆盖:会话级、主 Agent loop 内、Adapter 层。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.core.utils import now_utc


# ============================================================
# 事件枚举
# ============================================================

class HookEvent(str, Enum):
    """Hook 事件类型,11 个"""

    # 会话级(由 chat_service / orchestrator_service 包装时 fire)
    SESSION_START = "session_start"
    PRE_ORCHESTRATE = "pre_orchestrate"
    POST_ORCHESTRATE = "post_orchestrate"

    # 主 Agent loop 内(由 orchestrator_service 内部 fire)
    PRE_DISPATCH = "pre_dispatch"
    POST_DISPATCH = "post_dispatch"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"

    # 审批
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECIDED = "approval_decided"

    # Adapter 层(由 Adapter 执行子 Thread 时 fire)
    PRE_THREAD_START = "pre_thread_start"
    POST_THREAD_END = "post_thread_end"


# ============================================================
# Hook 上下文(统一 payload)
# ============================================================

class HookContext(BaseModel):
    """
    Hook 调用时携带的统一上下文。
    fire/emit 调用方填充相关字段,未涉及的字段保持 None;
    extra 提供逃生口,放业务相关的临时字段。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: HookEvent
    trace_id: str = Field(description="贯穿一次请求的追踪 ID,与运行日志 / audit_logs 关联")
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = Field(
        default=None,
        description="工具入参的原始 dict(LLM 输出的 JSON 反序列化结果),未经 Pydantic Input 模型校验",
    )
    tool_output: Optional[Any] = None
    extra: dict[str, Any] = Field(default_factory=dict, description="业务自定义扩展字段")
    timestamp: datetime = Field(default_factory=now_utc)


# ============================================================
# Hook 返回值(仅同步 hook 用)
# ============================================================

class HookResult(BaseModel):
    """
    同步 Hook 的返回值。
    HookManager 按 decision 决定主流程走向;异步 Hook 没有返回值,本类型不适用。
    """

    decision: Literal["continue", "block", "inject", "replace_input"] = Field(
        default="continue",
        description=(
            "continue       —— 正常往下走\n"
            "block          —— 中断流程,业务层抛 HookBlockedException\n"
            "inject         —— 注入消息到主 Agent context(用 injected_message)\n"
            "replace_input  —— 改写工具的 input(用 updated_input)"
        ),
    )
    block_reason: Optional[str] = Field(
        default=None,
        description="decision=block 时填,作为异常 message",
    )
    injected_message: Optional[str] = Field(
        default=None,
        description="decision=inject 时填,作为 user 消息追加到主 Agent context",
    )
    updated_input: Optional[dict] = Field(
        default=None,
        description="decision=replace_input 时填,替换原 tool_input",
    )


# ============================================================
# 抽象基类
# ============================================================

class SyncHook(ABC):
    """
    同步 Hook:阻塞主流程,能影响决策。

    适用场景:限流 / 权限检查 / 审批前置 / Skill 注入 / 任何要 block / inject /
    replace_input 的钩子。
    """

    @abstractmethod
    async def handle(self, ctx: HookContext) -> HookResult:
        """
        处理事件并返回决策。
        实现方应当:
        - 计算成本可控,避免长时间阻塞主流程(超时阈值由 HookManager 控制)
        - 返回 HookResult 而不是抛异常;真出错可返回 decision='continue' 忽略
        """
        ...


class AsyncHook(ABC):
    """
    异步 Hook:不阻塞主流程,发后即忘。

    适用场景:审计日志 / 任何只观察不影响主流程的钩子。
    HookManager 通过线程池调度,主流程立即返回不等结果。

    重要约定:
    "异步"指**HookManager 的调度方式**(主流程 emit 后立即返回,handle 在线程池里跑),
    不代表实现方可以无限阻塞。线程池容量有限,长时间阻塞会拖垮整个 hook 系统。
    实现方仍应控制单次 handle 的执行时长,慢操作(网络调用 / 大量计算)应再次分发到
    自己的工作队列。
    """

    @abstractmethod
    async def handle(self, ctx: HookContext) -> None:
        """
        处理事件,无返回值。
        实现方应当:
        - 控制执行时长,避免占满线程池(超时阈值由 HookManager 控制)
        - 自行处理异常并记录日志,不让异常向上抛(否则会污染线程池)
        """
        ...


# ============================================================
# 异常
# ============================================================

class HookBlockedException(Exception):
    """同步 Hook 返回 decision=block 时,HookManager 抛出本异常中断主流程。"""

    def __init__(self, event: HookEvent, reason: str):
        self.event = event
        self.reason = reason
        super().__init__(f"Hook blocked at {event.value}: {reason}")
