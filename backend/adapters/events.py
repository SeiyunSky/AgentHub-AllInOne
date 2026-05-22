"""
AgentEvent —— Adapter 与主Agent / 前端之间的统一事件模型

Adapter 把任意来源（Claude SDK / Codex MCP / OpenAI 兼容 API）的输出
转换成本文件定义的 AgentEvent 类型，向上 yield 给主Agent 与 stream_service。
所有 AgentEvent 都共享基础字段（type / agent_id / thread_id / message_id / timestamp），
按 type 分子类各自携带特有字段。

`RoundDoneEvent` 不属于 AgentEvent —— 它是"整轮结束"的全局信号，由 stream_service
在所有 Adapter 都 done 后单独产生，与具体 Agent 无关。

调用方约定:`message_id` 由主Agent 创建 Thread 时一同生成并注入 Adapter，
Adapter 只负责把它填充到事件中,不自行生成。

事件清单（与 SSE 协议对齐）:
    agent_start         Agent 开始说话（前端创建新气泡）
    token               普通 token 流（追加到对应气泡）
    artifact_html       HTML 产物预览卡片
    artifact_diff       Diff 卡片
    approval_request    审批请求（Thread 暂停等待）
    agent_done          单个 Agent 完成
    agent_error         单个 Agent 出错

整轮 / 队列信号（独立类型,与 AgentEvent 解耦）:
    round_done          本轮所有 Agent 完成,但 SSE 连接保持打开等待排队消息
    queue_drained       该会话排队消息全部处理完毕,前端可安全关闭 SSE

队伍：咕嘎一辈子队
修改者：Adam Zhang
修改日期：2026-05-22
"""

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from backend.core.utils import now_utc


# ============================================================
# 基类:所有 AgentEvent 共享的字段
# ============================================================

class _BaseAgentEvent(BaseModel):
    """所有 AgentEvent 的公共字段。"""

    agent_id: str = Field(description="发出事件的 Agent ID")
    thread_id: str = Field(description="所属 Thread ID")
    message_id: str = Field(description="对应前端气泡的 messageId（由主Agent 注入）")
    timestamp: datetime = Field(default_factory=now_utc, description="事件产生时间")


# ============================================================
# 各类事件子类
# ============================================================

class AgentStartEvent(_BaseAgentEvent):
    """Agent 开始说话。前端收到后创建一个新气泡。"""

    type: Literal["agent_start"] = "agent_start"
    agent_name: str = Field(description="Agent 显示名（联系人列表展示用）")


class TokenEvent(_BaseAgentEvent):
    """流式 token 片段。前端追加到对应气泡。"""

    type: Literal["token"] = "token"
    content: str = Field(description="本次新增的文字片段")


class ArtifactHtmlEvent(_BaseAgentEvent):
    """
    HTML 产物预览卡片。前端渲染 sandboxed iframe。

    preview_url 与 html 同时存在,各司其职:
    - preview_url:指向后端临时静态文件(如 /preview/xxx.html),iframe 直接 src= 加载,
      隔离 CSP/沙箱;前端常规渲染走它。
    - html:完整 HTML 字符串,用于"复制源码"按钮、二次编辑、落 messages.content
      (后续查询历史消息时不依赖临时文件 TTL)。
    """

    type: Literal["artifact_html"] = "artifact_html"
    preview_url: str = Field(description="预览文件 URL,iframe 加载用")
    html: str = Field(description="完整 HTML 内容,用于复制源码 / 落库")


class ArtifactDiffEvent(_BaseAgentEvent):
    """Diff 产物卡片。前端展示文件名 + 红绿行 + 应用按钮。"""

    type: Literal["artifact_diff"] = "artifact_diff"
    file: str = Field(description="目标文件路径")
    additions: int = Field(description="新增行数")
    deletions: int = Field(description="删除行数")
    patch: str = Field(description="标准 unified diff 字符串")


class ApprovalRequestEvent(_BaseAgentEvent):
    """审批请求。子 Thread 暂停等待用户批准。"""

    type: Literal["approval_request"] = "approval_request"
    action: str = Field(description="待批准动作的标识，如 run_command / write_file")
    detail: str = Field(description="动作详情，给用户看")


class AgentDoneEvent(_BaseAgentEvent):
    """单个 Agent 完成本次输出。"""

    type: Literal["agent_done"] = "agent_done"


class AgentErrorEvent(_BaseAgentEvent):
    """单个 Agent 出错。"""

    type: Literal["agent_error"] = "agent_error"
    error: str = Field(description="错误描述(SSE 协议字段名 'error',与数据库 messages.error_message 解耦)")


# ============================================================
# Discriminated Union:Adapter 产生的事件总类型
# ============================================================

AgentEvent = Annotated[
    Union[
        AgentStartEvent,
        TokenEvent,
        ArtifactHtmlEvent,
        ArtifactDiffEvent,
        ApprovalRequestEvent,
        AgentDoneEvent,
        AgentErrorEvent,
    ],
    Field(discriminator="type"),
]


# ============================================================
# 整轮 / 队列信号:与 AgentEvent 独立,由 stream_service 单独产生
# ============================================================

class RoundDoneEvent(BaseModel):
    """
    本轮所有 Agent 全部完成。

    注意:推完此事件后 SSE 连接**不立即关闭**,继续保持打开等待该 conversation
    可能存在的排队消息。后端取出排队消息后会在同一条 SSE 流上继续推 agent_start /
    token / ... ,前端无需重新建立连接。
    """

    type: Literal["round_done"] = "round_done"
    timestamp: datetime = Field(default_factory=now_utc)


class QueueDrainedEvent(BaseModel):
    """
    该会话所有排队消息均已处理完毕。
    stream_service 推完此事件后关闭 SSE 连接,前端可安全断开。
    """

    type: Literal["queue_drained"] = "queue_drained"
    timestamp: datetime = Field(default_factory=now_utc)
