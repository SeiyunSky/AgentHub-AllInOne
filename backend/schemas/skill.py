"""
skills 相关 Pydantic DTO

Skill 的特殊性:元数据入库(skills 表),正文存文件。所以 DTO 分两种:
- 列表 / 挂载选择场景 → SkillSummary(不含正文)
- 加载正文 / 编辑器场景 → SkillWithContent(SkillSummary + content)

涵盖五类 DTO:
1. 内部 / 列表 DTO —— SkillSummary(精简,不含正文)
2. 加载正文 DTO —— SkillWithContent(给 Adapter / 编辑器用)
3. API DTO —— SkillCreate / SkillUpdate / SkillResponse

关键约定:
- name 是英文唯一标识(同一作者下唯一,UNIQUE KEY (author_id, name)),对应 .md 文件名。
- content 字段(正文)在 DTO 层接收完整 markdown 字符串;skill_service 落地时
  写文件 skills/{name}.md + 写 skills 表元数据。
- file_path 由 skill_service 内部生成,不暴露给 API 调用方填写。
- SkillUpdate 所有字段 Optional 默认 None,partial update 模式。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 内部 / 列表 DTO
# ============================================================

class SkillSummary(BaseModel):
    """
    Skill 精简形态,不含正文。
    用于列表展示(GET /skills)、Agent 挂载选择(创建 Agent 时选 Skill)、
    progressive disclosure(主 Agent 系统 prompt 只塞 description)。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str = Field(description="英文唯一标识,对应 .md 文件名")
    display_name: Optional[str] = Field(
        default=None,
        description="中文展示名,前端列表用",
    )
    description: Optional[str] = Field(
        default=None,
        description="frontmatter description,progressive disclosure 时塞进系统 prompt",
    )
    category: Optional[str] = Field(
        default=None,
        description="分类(代码 / 安全 / 领域知识等),市场筛选用",
    )
    author_id: str = Field(
        description="创建者 user_id,值为 'GUGA' 表示系统内置(前端据此判断是否允许编辑)",
    )
    is_public: bool
    is_active: bool


# ============================================================
# 加载正文 DTO
# ============================================================

class SkillWithContent(SkillSummary):
    """
    含正文的完整 Skill 形态。
    用于:
    - Adapter 加载 Skill 喂给 LLM
    - 前端编辑器展示 / 编辑
    - GET /skills/{name} 详情接口

    content 字段是 markdown 正文(不含 frontmatter,frontmatter 信息已散在元数据字段里)。
    """

    content: str = Field(description="markdown 正文,不含 frontmatter")


# ============================================================
# API DTO
# ============================================================

class SkillCreate(BaseModel):
    """
    POST /api/v1/skills 创建 Skill。
    service 层把 content 写入 skills/{name}.md(或 skills/user_{author_id}/{name}.md),
    元数据写入 skills 表;file_path 由 service 内部生成。
    """

    name: str = Field(
        description="英文唯一标识",
        pattern=r"^[a-z0-9_-]+$",
        min_length=1,
        max_length=100,
    )
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    content: str = Field(description="markdown 正文")
    is_public: bool = False


class SkillUpdate(BaseModel):
    """
    PATCH /api/v1/skills/{id} 修改 Skill。
    所有字段 Optional 默认 None,service 用 model_dump(exclude_unset=True) 取被显式传的字段。

    注意:name 不可修改(改了文件路径要跟着重命名,且 agent_skills 关联仍以 skill_id 为主键
    不需要靠 name 关联,所以禁止改 name 简化运维)。用户想换 name 应删除原 Skill 后新建。
    """

    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


class SkillResponse(BaseModel):
    """
    GET /api/v1/skills 返回的完整字段(不含正文)。
    需要正文请走 GET /api/v1/skills/{name} → SkillWithContent。

    file_path 是内部实现细节(如 skills/user_xxx/foo.md),不暴露给 API 调用方。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    author_id: str = Field(
        description="创建者 user_id,值为 'GUGA' 表示系统内置",
    )
    is_public: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
