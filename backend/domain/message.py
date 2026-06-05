"""
Message 领域模型 —— ContentBlock 联合类型

Agent 输出不再用单一 content + content_type 表达,而是拆解为有序的 ContentBlock 数组。
一条 Agent 消息可同时包含多个块(思考过程、工具调用、代码、文本等),按顺序渲染。

跨层共享:
- schemas/message.py    DTO 序列化(API / 内部传输)
- models/message.py     ORM 的 content JSON 列存储 ContentBlock 数组
- adapters/events.py    SSE 块级流式事件传输

每个块有:
- type    判别字段(text / thinking / tool_use / code / approval / deployment / image / artifacts)
- block_id 唯一标识(SSE 流式增量更新时用作主键,前端按此累积/合并)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


# ============================================================
# 块基础(每个块都有的字段)
# ============================================================

class _BaseBlock(BaseModel):
    """所有 ContentBlock 的公共字段"""

    block_id: str = Field(description="块唯一标识,SSE 流式增量更新的主键")


# ============================================================
# 文本块
# ============================================================

class TextBlock(_BaseBlock):
    """普通文本(Agent 自然语言输出)"""

    type: Literal["text"] = "text"
    content: str = Field(description="文本正文,支持 Markdown")


# ============================================================
# 思考块
# ============================================================

class ThinkingBlock(_BaseBlock):
    """Agent 的思考过程(extended thinking),前端可折叠展示"""

    type: Literal["thinking"] = "thinking"
    content: str = Field(description="思考内容")
    duration_ms: Optional[int] = Field(
        default=None,
        description="思考耗时(毫秒),done 后填充",
    )


# ============================================================
# 工具调用块
# ============================================================

ToolUseStatus = Literal["running", "completed", "error"]


class ToolUseBlock(_BaseBlock):
    """Agent 调用工具的记录(含输入、输出、状态)"""

    type: Literal["tool_use"] = "tool_use"
    tool_name: str = Field(description="工具名,如 read_file / dispatch_to_agent")
    input: Optional[dict[str, Any]] = Field(
        default=None,
        description="工具入参(LLM 输出的 JSON)",
    )
    output: Optional[str] = Field(
        default=None,
        description="工具执行结果,文本形态",
    )
    status: ToolUseStatus = Field(default="running")
    error_message: Optional[str] = Field(
        default=None,
        description="status=error 时填",
    )


# ============================================================
# 代码块(含可选 diff)
# ============================================================

class CodeBlock(_BaseBlock):
    """代码块。当含 old_code 时即为 diff,可触发一键应用流程。"""

    type: Literal["code"] = "code"
    language: str = Field(description="编程语言,如 python / typescript")
    code: str = Field(description="新代码内容")
    filename: Optional[str] = Field(
        default=None,
        description="目标文件路径,有值时表示这是要写入的代码",
    )
    old_code: Optional[str] = Field(
        default=None,
        description="原始代码(diff 模式),与 code 共同构成 diff",
    )
    additions: Optional[int] = Field(default=None, description="新增行数(diff 模式)")
    deletions: Optional[int] = Field(default=None, description="删除行数(diff 模式)")
    applied_commit_hash: Optional[str] = Field(
        default=None,
        description="已应用时的 git commit hash",
    )


# ============================================================
# 审批块
# ============================================================

ApprovalStatus = Literal["pending", "approved", "rejected"]


class ApprovalBlock(_BaseBlock):
    """工具调用前的审批请求,Thread 在此暂停等待用户决策"""

    type: Literal["approval"] = "approval"
    action: str = Field(description="待批准动作,如 run_command / write_file")
    detail: str = Field(description="动作详情,展示给用户")
    status: ApprovalStatus = Field(default="pending")
    decided_at: Optional[datetime] = Field(default=None)
    reject_reason: Optional[str] = Field(default=None)


# ============================================================
# 部署块
# ============================================================

DeploymentStatus = Literal["deploying", "completed", "error"]


class DeploymentBlock(_BaseBlock):
    """部署任务的实时进度展示"""

    type: Literal["deployment"] = "deployment"
    title: str = Field(description="部署标题,如 'Vercel 部署'")
    status: DeploymentStatus = Field(default="deploying")
    progress: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="进度百分比 0-100",
    )
    url: Optional[str] = Field(default=None, description="完成后的访问 URL")
    logs: Optional[str] = Field(default=None, description="部署日志(尾部)")


# ============================================================
# 图片块
# ============================================================

class ImageBlock(_BaseBlock):
    """图片(模型生成或外部链接)"""

    type: Literal["image"] = "image"
    src: str = Field(description="图片 URL 或 data URI")
    alt: Optional[str] = Field(default=None, description="替代文本")
    caption: Optional[str] = Field(default=None, description="图片说明")


# ============================================================
# 产物聚合块
# ============================================================

class ArtifactItem(BaseModel):
    """产物列表中的单条产物条目"""

    name: str
    type: str = Field(description="产物子类型,如 html / pdf / json")
    preview: Optional[str] = Field(default=None, description="预览 URL 或缩略文本")


class ArtifactsBlock(_BaseBlock):
    """多产物聚合卡片(如一次任务产出的多个文件清单)"""

    type: Literal["artifacts"] = "artifacts"
    title: str
    items: list[ArtifactItem]


# ============================================================
# 表情包块
# ============================================================

class MemeBlock(_BaseBlock):
    """Agent 发送的表情包 —— broadcast 闲聊模式下调用 send_meme 工具产生"""

    type: Literal["meme"] = "meme"
    meme_id: str = Field(description="表情包 ID，对应 meme_library.json 中的 id 字段")
    url: str = Field(description="前端可直接访问的图片路径，如 /memes/doge.png")
    description: str = Field(description="表情包文字描述，alt text 兜底用")


# ============================================================
# Discriminated Union
# ============================================================

ContentBlock = Annotated[
    Union[
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        CodeBlock,
        ApprovalBlock,
        DeploymentBlock,
        ImageBlock,
        ArtifactsBlock,
        MemeBlock,
    ],
    Field(discriminator="type"),
]


__all__ = [
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolUseStatus",
    "CodeBlock",
    "ApprovalBlock",
    "ApprovalStatus",
    "DeploymentBlock",
    "DeploymentStatus",
    "ImageBlock",
    "ArtifactItem",
    "ArtifactsBlock",
    "MemeBlock",
    "ContentBlock",
]
