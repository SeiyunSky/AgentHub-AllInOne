"""
messages 相关 Pydantic DTO

对应数据结构设计文档第七节 messages 表 + domain/message.py 的 ContentBlock 联合类型。

消息内容用 **ContentBlock 数组** 表达,而非单一字符串。一条 Agent 消息可同时含
思考过程 / 工具调用 / 代码 / 文本 等多个块,有序渲染。

涵盖五类 DTO:
1. 枚举 —— role / status / feedback
2. 嵌套结构 —— SelectedRange(ChatRequest 入参元数据,不是消息块)
3. 内部传输 DTO —— MessageInHistory(给 Adapter 喂上下文用,精简) /
                   MessageCreate(service 创建消息) /
                   MessageUpdate(service 更新消息)
4. API DTO —— MessageResponse(GET /messages 返回) / FeedbackUpdate(PATCH /feedback)

关键约定:
- ORM 模型(models/message.py)的 content 字段是 JSON,存 ContentBlock 数组。
- 不再有 content_type / approval_status / applied_commit_hash 等外层字段,
  这些语义全在对应 ContentBlock 子类内部表达。
- 流式过程中(status=streaming)的中间态通过 SSE 块级流式事件增量推送,
  最终态落库为完整 blocks 数组。
- Message ID 由应用层生成(UUID),MessageCreate 接受可选 id。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.message import ContentBlock


# ============================================================
# 枚举
# ============================================================

class MessageRole(str, Enum):
    """消息发送方角色"""
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(str, Enum):
    """消息状态"""
    STREAMING = "streaming"
    DONE = "done"
    ERROR = "error"


class MessageFeedback(str, Enum):
    """用户对 Agent 消息的反馈"""
    UP = "up"
    DOWN = "down"


# ============================================================
# 嵌套结构
# ============================================================

class SelectedRange(BaseModel):
    """对话式局部修改时携带的代码段元数据(ChatRequest 入参)"""

    file: str = Field(description="目标文件路径")
    start: int = Field(description="起始行号(含)")
    end: int = Field(description="结束行号(含)")
    code: str = Field(description="选中的原始代码内容")


# ============================================================
# 内部传输 DTO
# ============================================================

class MessageInHistory(BaseModel):
    """
    给 Adapter 喂入对话历史用的精简消息形态。
    去掉数据库字段(id / status / token_count 等),只保留 LLM 上下文必需的内容。

    群聊场景下 role=assistant 的消息有多条,LLM 看不到 agent_id 区分谁是谁;
    Adapter 拼 prompt 时建议把 sender(Agent 显示名快照)拼到内容前面,
    例如:"[CodeReviewer]: ...",让 LLM 理解每条 assistant 消息的发出方。

    blocks 是有序的内容块列表(domain.message.ContentBlock)。Adapter 喂 LLM 时,
    应根据块类型转成自然语言描述,例如:
        ToolUseBlock      → "[Tool: read_file -> ok]"
        CodeBlock         → "[Code: api.py +15/-2]"
        ApprovalBlock     → "[Approval: run_command 'npm install' (approved)]"
    避免把原始 JSON 直接塞进 LLM 上下文。
    """

    role: MessageRole
    blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="消息内容块有序列表",
    )
    sender: Optional[str] = Field(
        default=None,
        description="发送方显示名(Agent name 快照),仅 role=assistant 时有值",
    )


class MessageCreate(BaseModel):
    """
    service 层内部创建一条消息记录用的 DTO。

    id 是可选项:调用方可以提前生成 UUID 并注入(配合 Adapter 事件回填 message_id 协议),
    repo 层在 id 为空时自行生成。

    status 必填,无默认值:
    - 流式场景(收到 agent_start 时建消息) → 必须显式传 STREAMING,后续 MessageUpdate 改为 DONE
    - 非流式场景(用户消息 / 一次性写入的产物消息) → 显式传 DONE
    """

    id: Optional[str] = Field(
        default=None,
        description="可选,调用方提前生成的 UUID;为空时由 repo 自动生成",
    )
    conversation_id: str
    thread_id: Optional[str] = None
    parent_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    role: MessageRole
    blocks: list[ContentBlock] = Field(
        default_factory=list,
        description="消息内容块,用户消息通常含单个 TextBlock",
    )
    status: MessageStatus = Field(
        description="必填,流式建消息传 STREAMING,落地态传 DONE",
    )
    model: Optional[str] = None
    sender: Optional[str] = None
    selected_range: Optional[SelectedRange] = None


class MessageUpdate(BaseModel):
    """
    service 层内部更新一条已存在消息用的 DTO。
    所有字段可选,只更新非 None 的字段;支持流式结束后写完整 blocks、改 status、写错误信息等。

    流式过程中**不通过本 DTO 增量更新单个块**,块级增量走 SSE 事件协议;
    本 DTO 只负责"批量替换 blocks"或"标态"等粗粒度更新。
    """

    blocks: Optional[list[ContentBlock]] = Field(
        default=None,
        description="完整覆盖整条消息的块列表(流式结束后的最终态)",
    )
    status: Optional[MessageStatus] = None
    error_message: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: Optional[int] = None


# ============================================================
# API DTO
# ============================================================

class MessageResponse(BaseModel):
    """GET /api/v1/conversations/{id}/messages 返回的完整消息字段"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    thread_id: Optional[str] = None
    parent_id: Optional[str] = None
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_avatar: Optional[str] = None
    role: MessageRole
    blocks: list[ContentBlock] = Field(default_factory=list)
    status: MessageStatus
    error_message: Optional[str] = None
    model: Optional[str] = None
    sender: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: Optional[int] = None
    feedback: Optional[MessageFeedback] = None
    selected_range: Optional[SelectedRange] = None
    is_deleted: bool = Field(
        default=False,
        description="软删除标志,前端可据此渲染'消息已撤回'占位",
    )
    created_at: datetime


class FeedbackUpdate(BaseModel):
    """PATCH /api/v1/messages/{id}/feedback 请求体"""

    feedback: Optional[MessageFeedback] = Field(
        default=None,
        description="up=点赞,down=点踩,null=取消评价",
    )
