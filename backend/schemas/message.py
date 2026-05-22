"""
messages 相关 Pydantic DTO

对应数据结构设计文档第七节 messages 表。涵盖五类 DTO:
1. 枚举 —— role / content_type / status / feedback / approval_status
2. 嵌套结构 —— SelectedRange(局部修改时携带的代码段)
3. 产物 Payload —— ArtifactHtmlPayload / ArtifactDiffPayload / ApprovalPayload
                   (content_type 非 text 时,content 字段反序列化的结构)
4. 内部传输 DTO —— MessageInHistory(给 Adapter 喂上下文用,精简) /
                   MessageCreate(service 层创建消息) /
                   MessageUpdate(service 层更新已存在消息)
5. API DTO —— MessageResponse(GET /messages 返回完整字段) /
              FeedbackUpdate(PATCH /feedback 入参)

关键约定:
- ORM 模型(models/message.py)是数据库表结构,本文件是网络传输与跨层调用的形态。
- 流式过程中(status=streaming)的中间态不通过本 DTO 暴露,前端通过 SSE AgentEvent
  增量接收;最终落库后才以 MessageResponse 形态返回给查询接口。
- Message ID 由应用层生成(UUID),MessageCreate 接受可选 id,允许调用方在创建消息
  之前先生成并把同一个 id 注入 Adapter(配合 AgentEvent 回填 message_id 的协议)。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 枚举
# ============================================================

class MessageRole(str, Enum):
    """消息发送方角色"""
    USER = "user"
    ASSISTANT = "assistant"


class MessageContentType(str, Enum):
    """消息内容类型,前端按此选择渲染组件"""
    TEXT = "text"
    ARTIFACT_HTML = "artifact_html"
    ARTIFACT_CODE = "artifact_code"
    ARTIFACT_DIFF = "artifact_diff"
    APPROVAL_REQUEST = "approval_request"


class MessageStatus(str, Enum):
    """消息状态"""
    STREAMING = "streaming"
    DONE = "done"
    ERROR = "error"


class MessageFeedback(str, Enum):
    """用户对 Agent 消息的反馈"""
    UP = "up"
    DOWN = "down"


class MessageApprovalStatus(str, Enum):
    """content_type=approval_request 时的审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ============================================================
# 嵌套结构
# ============================================================

class SelectedRange(BaseModel):
    """对话式局部修改时携带的代码段元数据"""

    file: str = Field(description="目标文件路径")
    start: int = Field(description="起始行号(含)")
    end: int = Field(description="结束行号(含)")
    code: str = Field(description="选中的原始代码内容")


# ============================================================
# 产物 Payload(content_type 非 text 时,content 字段反序列化的结构)
# ============================================================

class ArtifactHtmlPayload(BaseModel):
    """content_type=artifact_html 时 content 字段的结构"""

    preview_url: str = Field(description="预览文件 URL")
    html: str = Field(description="完整 HTML 内容")


class ArtifactDiffPayload(BaseModel):
    """content_type=artifact_diff 时 content 字段的结构"""

    file: str = Field(description="目标文件路径")
    additions: int = Field(description="新增行数")
    deletions: int = Field(description="删除行数")
    patch: str = Field(description="标准 unified diff 字符串")


class ApprovalPayload(BaseModel):
    """content_type=approval_request 时 content 字段的结构"""

    action: str = Field(description="待批准动作的标识,如 run_command / write_file")
    detail: str = Field(description="动作详情,给用户看")


# ============================================================
# 内部传输 DTO
# ============================================================

class MessageInHistory(BaseModel):
    """
    给 Adapter 喂入对话历史用的精简消息形态。
    去掉数据库字段(id / status / token_count 等),只保留 LLM 上下文必需的内容。

    群聊场景下 role=assistant 的消息有多条,LLM 看不到 agent_id 区分谁是谁;
    Adapter 拼 prompt 时建议把 sender(Agent 显示名快照)拼到 content 前面,
    例如:"[CodeReviewer]: ...",让 LLM 理解每条 assistant 消息的发出方。

    content_type 非 text 时 content 字段是 JSON 字符串(如 ArtifactDiffPayload),
    Adapter 喂给 LLM 之前应转成自然语言描述,例如:
        artifact_diff   → "[Diff: api.py +15/-2]"
        artifact_html   → "[HTML 产物已生成: 登录页]"
        approval_request → "[已请求审批: run_command 'npm install']"
    避免把原始 JSON 直接塞进 LLM 上下文。
    """

    role: MessageRole
    content: str = Field(description="文本或 artifact JSON 序列化后字符串")
    content_type: MessageContentType = MessageContentType.TEXT
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
    强制传值是为了避免流式场景遗漏 status 导致默认落 DONE 的隐藏 bug。
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
    content: str
    content_type: MessageContentType = MessageContentType.TEXT
    status: MessageStatus = Field(
        description="必填,流式建消息传 STREAMING,落地态传 DONE",
    )
    model: Optional[str] = None
    sender: Optional[str] = None
    selected_range: Optional[SelectedRange] = None


class MessageUpdate(BaseModel):
    """
    service 层内部更新一条已存在消息用的 DTO。
    所有字段可选,只更新非 None 的字段;支持流式追加 content、改 status、写入错误信息等。
    """

    content: Optional[str] = Field(
        default=None,
        description="完整覆盖内容(流式结束后的最终态)",
    )
    status: Optional[MessageStatus] = None
    error_message: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: Optional[int] = None
    approval_status: Optional[MessageApprovalStatus] = None
    applied_commit_hash: Optional[str] = None


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
    role: MessageRole
    content: str
    content_type: MessageContentType
    status: MessageStatus
    error_message: Optional[str] = None
    model: Optional[str] = None
    sender: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    latency_ms: Optional[int] = None
    feedback: Optional[MessageFeedback] = None
    approval_status: Optional[MessageApprovalStatus] = None
    selected_range: Optional[SelectedRange] = None
    applied_commit_hash: Optional[str] = None
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
