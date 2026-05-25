"""
Memory 领域类型

主 Agent 的长期记忆是文件方案(不入库),按 user_id + conversation_id 隔离:
    runtime/memory/{user_id}/{conversation_id}/
        ├── MEMORY.md          ← 索引(每条一行)
        └── {name}.md          ← 单条记忆,frontmatter + 正文

每条记忆 4 类:user(身份偏好) / feedback(用户纠正) / project(项目背景) /
reference(外部参考)。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """记忆类型,4 类(参考主 Agent 设计第六节)"""
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


class MemoryFrontmatter(BaseModel):
    """单条记忆文件头的 YAML frontmatter 元数据"""

    name: str = Field(
        description="英文唯一标识,对应 .md 文件名",
        pattern=r"^[a-z0-9_-]+$",
        min_length=1,
        max_length=100,
    )
    description: str = Field(description="一句话摘要,MEMORY.md 索引展示用")
    type: MemoryType
    created_at: datetime
    updated_at: datetime


class MemoryEntry(BaseModel):
    """
    单条记忆的完整形态(元数据 + 正文)。

    持久化在文件 runtime/memory/{user_id}/{conversation_id}/{name}.md,
    本类是文件解析后的内存表达。
    """

    frontmatter: MemoryFrontmatter
    content: str = Field(description="记忆正文(markdown)")


class MemoryIndexLine(BaseModel):
    """
    MEMORY.md 索引中的一行(只含元数据,不含正文)。

    与 MemoryFrontmatter 字段重叠但用途不同:
    - 索引读取走 list_index() 单文件 IO,主 Agent 启动时低成本扫一眼可用记忆
    - 完整解析走 list_memories() 多文件 IO + YAML 解析,只在需要详情时调
    """

    name: str = Field(
        pattern=r"^[a-z0-9_-]+$",
        min_length=1,
        max_length=100,
    )
    description: str
