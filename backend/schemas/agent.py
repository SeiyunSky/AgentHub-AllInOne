"""
agents 相关 Pydantic DTO

对应数据结构设计文档第 2 节 agents 表。涵盖五类 DTO:
1. 内部 DTO —— AgentForOrchestrator(主 Agent list_available_agents 工具返回的精简版)
2. API DTO —— AgentCreate / AgentUpdate / AgentResponse(普通 CRUD)
3. 对话式创建 —— AgentBuildRequest / AgentBuildDraft / AgentBuildResponse / AgentBuildConfirm

关键约定:
- AgentType / AgentCapabilities 定义在 domain/agent.py,本文件 import 复用,避免重复。
- AgentForOrchestrator 不含 system_prompt(避免主 Agent context 撑爆)。
- AgentUpdate 所有字段 Optional 默认 None,service 用 model_dump(exclude_unset=True)
  取被显式传入的字段做 partial update。
- AgentBuildDraft 是草稿本体,session_id 包在 Build Request/Response/Confirm 外层,
  不污染草稿数据。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.agent import AgentCapabilities, AgentType


# ============================================================
# 内部 DTO
# ============================================================

class AgentForOrchestrator(BaseModel):
    """
    主 Agent 调 list_available_agents / get_agent_capabilities 工具时返回的形态。
    精简版,不含 system_prompt 避免污染主 Agent 上下文。
    """

    id: str
    name: str
    description: Optional[str] = None
    type: AgentType
    capabilities: AgentCapabilities
    tags: list[str] = Field(default_factory=list)


# ============================================================
# 普通 CRUD
# ============================================================

class AgentCreate(BaseModel):
    """POST /api/v1/agents 创建 Agent"""

    name: str = Field(description="联系人列表展示名")
    description: Optional[str] = Field(
        default=None,
        description="Agent 简介,联系人卡片副标题",
    )
    type: AgentType
    system_prompt: Optional[str] = None
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False
    skill_ids: list[str] = Field(
        default_factory=list,
        description="挂载的 Skill ID 列表,service 层落 agent_skills 关联表",
    )


class AgentUpdate(BaseModel):
    """
    PATCH /api/v1/agents/{id} 修改 Agent。
    所有字段 Optional 默认 None;service 用 model_dump(exclude_unset=True) 取被显式传的字段。

    注意:type 字段不可修改(会改变 Adapter 路由,等于换了个 Agent)。
    用户想换类型应删除原 Agent 后新建。
    """

    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    capabilities: Optional[AgentCapabilities] = None
    tags: Optional[list[str]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None
    skill_ids: Optional[list[str]] = None


class AgentResponse(BaseModel):
    """
    GET /api/v1/agents 返回的完整字段。

    注意:skill_ids 不在 ORM Agent 模型上,from_attributes 无法自动填充。
    service 层从 agent_skills 关联表查出列表后手动注入,例如:
        agent_response = AgentResponse.model_validate(agent_orm)
        agent_response.skill_ids = await skill_repo.list_skill_ids_for_agent(agent.id)
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str = Field(
        description="创建者 user_id,值为 'GUGA' 表示系统内置 Agent",
    )
    name: str
    description: Optional[str] = None
    type: AgentType
    system_prompt: Optional[str] = None
    capabilities: AgentCapabilities
    tags: list[str] = Field(default_factory=list)
    is_public: bool
    is_active: bool
    skill_ids: list[str] = Field(
        default_factory=list,
        description="从 agent_skills 关联表查出的 Skill ID 列表(service 层手动注入)",
    )
    created_at: datetime
    updated_at: datetime


# ============================================================
# 对话式创建 Agent
# ============================================================

class AgentBuildRequest(BaseModel):
    """POST /api/v1/agents/build 入参,启动一轮对话式创建"""

    description: str = Field(
        description="用户自然语言描述需要的 Agent,如'我需要一个专门做代码审查的 Agent,擅长 Python 和安全'",
    )


class AgentBuildDraft(BaseModel):
    """
    LLM 生成的 Agent 草稿(用户确认前的临时态)。
    在 Redis agent_draft:user:{user_id}:{session_id} 中以本结构存储。

    suggested_skill_names → skill_id 的映射:
    - 草稿阶段保留为 name 字符串(便于 LLM 输出 / 用户在前端编辑增删)。
    - 用户确认时 agent_builder_service.confirm() 负责按 name 去 skills 表查 skill_id,
      把最终列表写入 agent_skills 关联表。
    - 名字找不到对应 Skill 的应该报错给用户,而不是静默丢弃。
    """

    name: str
    description: Optional[str] = None
    type: AgentType
    system_prompt: str
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    tags: list[str] = Field(default_factory=list)
    suggested_skill_names: list[str] = Field(
        default_factory=list,
        description="LLM 建议挂载的 Skill 名字(confirm 时由 service 转成 skill_id)",
    )


class AgentBuildResponse(BaseModel):
    """POST /api/v1/agents/build 返回,session_id 用于后续 confirm"""

    session_id: str = Field(description="本轮对话式创建的会话 ID,带回 confirm 接口")
    draft: AgentBuildDraft


class AgentBuildConfirm(BaseModel):
    """POST /api/v1/agents/build/confirm 入参,提交编辑后的最终草稿"""

    session_id: str = Field(description="对应 AgentBuildResponse.session_id")
    edited_draft: AgentBuildDraft = Field(
        description="用户在前端编辑后的最终草稿,直接替换 Redis 中原草稿落库",
    )
