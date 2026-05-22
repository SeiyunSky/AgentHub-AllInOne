"""
chat 入口相关 Pydantic DTO

对应 chat_service 三路由分发(主 Agent 设计第十三节)的 HTTP 入口:
    POST /api/v1/chat       发消息
    POST /api/v1/chat/stop  紧急中止当前轮

涵盖:
1. ChatRequest —— POST /chat 入参,统一所有路由分支(单聊/群聊/@个体特化/局部修改)
2. 应答 DTO —— ChatStartedResponse(立即开始) / ChatQueuedResponse(进入队列)
   两种应答类型用 ChatResponse discriminated union 包装
3. ChatStopRequest —— POST /chat/stop 入参

排队机制(主 Agent 设计第十三节·2):
- 用户在 round 进行中再次发消息 → chat_service 检测到 conversation 锁被占
  → 写入 pending_messages 队列 → 返回 ChatQueuedResponse(同步 HTTP 应答)
- 当前轮 round_done 后从队列取出 → 复用现有 SSE 连接继续推 agent_start / token...
- 前端按"已排队 / 已开始"两种状态分别渲染等待提示 / 立即流式

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from backend.core.utils import now_utc
from backend.schemas.message import SelectedRange


# ============================================================
# 请求
# ============================================================

class ChatRequest(BaseModel):
    """
    POST /api/v1/chat 入参,统一所有路由分支。

    路由判定优先级(chat_service 内部):
    1. selected_range 非空 → 局部修改流程
    2. conversation 单聊 → 单聊直通
    3. conversation 群聊 + 单 mention → @个体特化
    4. 其他 → 群聊全员(走主 Agent)

    mention_ids 为 @提及的 agent_id 列表,前端解析输入框 @标记 后填充。
    """

    conversation_id: str
    content: str = Field(description="用户输入的消息内容(纯文本 / Markdown)")
    mention_ids: list[str] = Field(
        default_factory=list,
        description="@提及的 agent_id 列表,空列表表示未 @任何 Agent",
    )
    selected_range: Optional[SelectedRange] = Field(
        default=None,
        description="对话式局部修改时携带的代码段;非空时强制走局部修改流程",
    )


class ChatStopRequest(BaseModel):
    """
    POST /api/v1/chat/stop 入参,紧急中止当前轮(独立于发消息流程)。

    与排队机制并存:
    - 默认:用户在 round 进行中发消息走排队
    - 显式中止:用户点"停止"按钮调本接口,立即 cancel 所有 Thread,推 round_done,
      释放锁,处理队列后续消息
    """

    conversation_id: str


# ============================================================
# 应答(discriminated union)
# ============================================================

class ChatStartedResponse(BaseModel):
    """
    立即开始处理的应答。前端拿到后开始监听 SSE 流。
    """

    status: Literal["started"] = "started"
    conversation_id: str
    user_message_id: str = Field(
        description="本次用户消息落库后的 id,前端据此匹配 SSE 流上的事件",
    )


class ChatQueuedResponse(BaseModel):
    """
    进入队列的应答。前端不重开 SSE,继续监听已有的 SSE 连接;
    后端轮到时会在同一条 SSE 流上继续推 agent_start。
    """

    status: Literal["queued"] = "queued"
    conversation_id: str
    queued_message_id: str = Field(description="排队中的用户消息 id")
    queue_position: int = Field(description="排在队列中的位置,从 1 开始")


ChatResponse = Annotated[
    Union[ChatStartedResponse, ChatQueuedResponse],
    Field(discriminator="status"),
]


# ============================================================
# 中止应答
# ============================================================

class ChatStopResponse(BaseModel):
    """POST /api/v1/chat/stop 应答"""

    conversation_id: str
    aborted: bool = Field(description="是否成功中止(False 表示当前轮已无活跃 Thread)")
    cancelled_thread_ids: list[str] = Field(
        default_factory=list,
        description="被本次中止 cancel 的 thread_id 列表",
    )
    timestamp: datetime = Field(default_factory=now_utc)
