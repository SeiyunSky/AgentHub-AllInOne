"""
WebSocket 双向消息协议

WebSocket 用于内容流之外的双向交互(Diff 应用 / 审批决策 / Thread 状态变化推送),
跟单向 SSE(内容流)互补。

两个方向各自的消息类型用 discriminated union 包装:
- ClientToServerMessage —— 前端发给后端的请求(apply_diff / approval_decision)
- ServerToClientMessage —— 后端推给前端的事件(diff_applied / approval_acknowledged /
                            thread_status_changed)

每个消息共享:
- type      —— 判别字段
- timestamp —— 时间戳

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.utils import now_utc
from backend.schemas.thread import ThreadStatus


# ============================================================
# Client → Server
# ============================================================

class ApplyDiffRequest(BaseModel):
    """用户点 Diff 卡片'应用'按钮"""

    type: Literal["apply_diff"] = "apply_diff"
    message_id: str = Field(description="对应 content_type=artifact_diff 的消息 ID")
    timestamp: datetime = Field(default_factory=now_utc)


class ApprovalDecisionRequest(BaseModel):
    """用户对 approval_request 的决策"""

    type: Literal["approval_decision"] = "approval_decision"
    message_id: str = Field(description="对应 content_type=approval_request 的消息 ID")
    decision: Literal["approve", "reject"]
    reason: Optional[str] = Field(
        default=None,
        description="拒绝时建议填写,审批日志归档",
    )
    timestamp: datetime = Field(default_factory=now_utc)


ClientToServerMessage = Annotated[
    Union[ApplyDiffRequest, ApprovalDecisionRequest],
    Field(discriminator="type"),
]


# ============================================================
# Server → Client
# ============================================================

class DiffAppliedEvent(BaseModel):
    """Diff 应用结果(WebSocket 单独推送,不走 SSE 内容流)"""

    type: Literal["diff_applied"] = "diff_applied"
    message_id: str = Field(description="对应被应用的 artifact_diff 消息 ID")
    status: Literal["success", "conflict", "error"]
    commit_hash: Optional[str] = Field(
        default=None,
        description="status=success 时的 git commit hash",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="status=conflict / error 时的错误描述",
    )
    timestamp: datetime = Field(default_factory=now_utc)


class ApprovalAcknowledgedEvent(BaseModel):
    """审批结果已被后端处理,Thread 据此 resume / cancel"""

    type: Literal["approval_acknowledged"] = "approval_acknowledged"
    message_id: str = Field(description="对应 approval_request 的消息 ID")
    decision: Literal["approve", "reject"]
    thread_id: str = Field(description="该审批关联的 Thread ID")
    timestamp: datetime = Field(default_factory=now_utc)


class ThreadStatusChangedEvent(BaseModel):
    """
    Thread 状态变化通知。
    用于前端展示 Thread 进度(如等待审批 / 已取消 / 已失败)。
    """

    type: Literal["thread_status_changed"] = "thread_status_changed"
    thread_id: str
    agent_id: str
    status: ThreadStatus
    timestamp: datetime = Field(default_factory=now_utc)


ServerToClientMessage = Annotated[
    Union[
        DiffAppliedEvent,
        ApprovalAcknowledgedEvent,
        ThreadStatusChangedEvent,
    ],
    Field(discriminator="type"),
]
