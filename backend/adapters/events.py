"""
AgentEvent —— Adapter 与主Agent / 前端之间的统一事件模型(块级流式)

Adapter 把任意来源（Claude SDK / Codex MCP / OpenAI 兼容 API）的输出
转换成本文件定义的 AgentEvent 类型，向上 yield 给主Agent 与 stream_service。

消息 = 块数组(domain.message.ContentBlock),Adapter 流式输出时按"块级增量"协议:
    block_start  → 创建一个新块(指定 block_id + 初始字段)
    block_delta  → 对该 block_id 的字段做增量更新(text 累加 / 状态变化等)
    block_stop   → 该块结束(可附带最终字段)

前端按 block_id 累积/合并,直到 block_stop 后该块视为最终态。
该协议与 Anthropic / OpenAI 流式块协议同构,Adapter 接入成本低。

调用方约定:`message_id` 由主Agent 创建 Thread 时一同生成并注入 Adapter,
Adapter 只负责把它填充到事件中,不自行生成。`block_id` 由 Adapter 在 block_start
时生成(UUID 或递增字符串均可),后续 delta/stop 复用。

事件清单(SSE 协议):
    agent_start         Agent 开始说话(前端创建新气泡)
    block_start         一个内容块开始(thinking / tool_use / code / text / approval / ...)
    block_delta         块内字段增量更新(包括文本累加、状态切换、字段补全)
    block_stop          块结束(可附最终字段)
    agent_done          单个 Agent 完成(整条消息所有块就绪)
    agent_error         单个 Agent 出错

整轮 / 队列信号(独立类型,与 AgentEvent 解耦):
    round_done          本轮所有 Agent 完成,但 SSE 连接保持打开等待排队消息
    queue_drained       该会话排队消息全部处理完毕,前端可安全关闭 SSE

队伍：咕嘎一辈子队
修改者：Adam Zhang Musuyin
修改日期：2026-05-25
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.utils import now_utc
from backend.domain.message import ContentBlock


# ============================================================
# 基类:所有 AgentEvent 共享的字段
# ============================================================

class _BaseAgentEvent(BaseModel):
    """所有 AgentEvent 的公共字段。"""

    agent_id: str = Field(description="发出事件的 Agent ID")
    thread_id: str = Field(description="所属 Thread ID")
    message_id: str = Field(description="对应前端气泡的 messageId(由主Agent 注入)")
    timestamp: datetime = Field(default_factory=now_utc, description="事件产生时间")


# ============================================================
# 消息级事件
# ============================================================

class AgentStartEvent(_BaseAgentEvent):
    """Agent 开始说话。前端收到后创建一个新气泡(空 blocks)。"""

    type: Literal["agent_start"] = "agent_start"
    agent_name: str = Field(description="Agent 显示名(联系人列表展示用)")


class AgentDoneEvent(_BaseAgentEvent):
    """单个 Agent 完成本次输出。整条消息的所有块都已 block_stop。"""

    type: Literal["agent_done"] = "agent_done"


class AgentErrorEvent(_BaseAgentEvent):
    """单个 Agent 出错。"""

    type: Literal["agent_error"] = "agent_error"
    error: str = Field(
        description="错误描述(SSE 协议字段名 'error',与数据库 messages.error_message 解耦)",
    )


# ============================================================
# 块级流式事件
# ============================================================

class BlockStartEvent(_BaseAgentEvent):
    """
    一个新内容块开始。
    携带块的初始字段(完整或部分),前端据此插入新块到当前消息 blocks 数组。
    后续 BlockDeltaEvent / BlockStopEvent 通过 block.block_id 关联。
    """

    type: Literal["block_start"] = "block_start"
    block: ContentBlock = Field(
        description="块初始态,含 block_id 与 type;字段可后续 block_delta 增量补全",
    )


class BlockDeltaEvent(_BaseAgentEvent):
    """
    块字段增量更新。

    delta 是一个 dict,按字段名表达本次变化:
    - 文本累加: {"content": "新增片段"} → 前端把字符串拼到原值后
    - 状态切换: {"status": "completed"} → 前端覆盖该字段
    - 补全字段: {"output": "...", "duration_ms": 1200} → 多字段同时覆盖

    具体字段语义由 ContentBlock 子类决定;前端按"已知是累加 / 覆盖"分别处理,
    或简化为"全部覆盖"(累加场景由 Adapter 在 delta 时直接发完整新值)。
    """

    type: Literal["block_delta"] = "block_delta"
    block_id: str = Field(description="目标块的 block_id")
    delta: dict[str, Any] = Field(description="字段增量更新")


class BlockStopEvent(_BaseAgentEvent):
    """
    块结束。可附带最终字段(如最终的 status / output / duration_ms 等)。
    前端收到后认为该块进入最终态,不再期待该 block_id 的 delta。
    """

    type: Literal["block_stop"] = "block_stop"
    block_id: str = Field(description="目标块的 block_id")
    final_fields: Optional[dict[str, Any]] = Field(
        default=None,
        description="可选的最终字段补全",
    )


# ============================================================
# Discriminated Union:Adapter 产生的事件总类型
# ============================================================

AgentEvent = Annotated[
    Union[
        AgentStartEvent,
        BlockStartEvent,
        BlockDeltaEvent,
        BlockStopEvent,
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
    block_* / ...,前端无需重新建立连接。
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
