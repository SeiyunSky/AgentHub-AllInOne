"""
agents API — Agent CRUD 端点

GET    /agents                  列表（当前用户可见）
POST   /agents                  创建
GET    /agents/{id}             详情
PATCH  /agents/{id}             更新
DELETE /agents/{id}             删除
POST   /agents/{id}/activate    启用
POST   /agents/{id}/deactivate  停用
POST   /agents/build            LLM 辅助生成草稿（返回 session_id + draft）
POST   /agents/build/confirm    用户确认草稿后落库（返回创建的 Agent）

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from backend.api.deps import get_current_user, get_db
from backend.repositories.agent_repo import AgentRepository
from backend.repositories.skill_repo import SkillRepository
from backend.schemas.agent import (
    AgentBuildConfirm,
    AgentBuildRequest,
    AgentBuildResponse,
    AgentCreate,
    AgentResponse,
    AgentUpdate,
)
from backend.services.agent_builder_service import AgentBuilderService

router = APIRouter()


def _to_response(agent, skill_repo: SkillRepository) -> AgentResponse:
    resp = AgentResponse.model_validate(agent)
    resp.skill_ids = skill_repo.list_skill_ids_for_agent(agent.id)
    return resp


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
    limit: int = Query(default=20, ge=1, le=200, description="每页返回数量，默认 20"),
    offset: int = Query(default=0, ge=0, description="分页偏移量"),
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)
    agents = repo.list_visible_for_user(user_id, limit=limit, offset=offset)
    return [_to_response(a, skill_repo) for a in agents]


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    data: AgentCreate,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)

    fields = data.model_dump(exclude={"skill_ids"})
    fields["user_id"] = user_id
    fields["is_public"] = 1 if fields.pop("is_public") else 0
    if "capabilities" in fields and fields["capabilities"] is not None:
        fields["capabilities"] = fields["capabilities"].model_dump() if hasattr(fields["capabilities"], "model_dump") else fields["capabilities"]
    if not fields.get("avatar"):
        from backend.core.avatars import pick_random_avatar
        fields["avatar"] = pick_random_avatar()

    agent = repo.create(**fields)
    if data.skill_ids:
        skill_repo.sync_agent_skills(agent.id, data.skill_ids)
    db.commit()
    db.refresh(agent)
    return _to_response(agent, skill_repo)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)
    agent = repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_response(agent, skill_repo)


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)
    agent = repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    fields = data.model_dump(exclude_unset=True, exclude={"skill_ids"})
    if "is_public" in fields:
        fields["is_public"] = 1 if fields["is_public"] else 0
    if "is_active" in fields:
        fields["is_active"] = 1 if fields["is_active"] else 0
    if "capabilities" in fields and fields["capabilities"] is not None:
        fields["capabilities"] = fields["capabilities"].model_dump() if hasattr(fields["capabilities"], "model_dump") else fields["capabilities"]
    if "type" in fields and fields["type"] is not None:
        # AgentType 枚举转成字符串值写 DB
        fields["type"] = fields["type"].value if hasattr(fields["type"], "value") else fields["type"]

    for key, val in fields.items():
        setattr(agent, key, val)
    db.flush()

    if data.skill_ids is not None:
        skill_repo.sync_agent_skills(agent_id, data.skill_ids)

    db.commit()
    db.refresh(agent)

    # type 变更后重建 registry 里的 Adapter，使新类型立即生效
    if "type" in fields:
        from backend.adapters.registry import registry
        from backend.adapters.registry import _build_adapter
        try:
            registry.register(agent_id, _build_adapter(agent))
        except Exception:
            logger.warning("update_agent: rebuild adapter failed for agent %s", agent_id)

    return _to_response(agent, skill_repo)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    agent = repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()


@router.post("/agents/{agent_id}/activate", response_model=AgentResponse)
def activate_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)
    agent = repo.set_active(agent_id, True)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.commit()
    return _to_response(agent, skill_repo)


@router.post("/agents/{agent_id}/deactivate", response_model=AgentResponse)
def deactivate_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    repo = AgentRepository(db)
    skill_repo = SkillRepository(db)
    agent = repo.set_active(agent_id, False)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.commit()
    return _to_response(agent, skill_repo)


# ---------------------------------------------------------------------------
# 对话式创建 Agent（/agents/build 和 /agents/build/confirm）
# 注意：这两个路由必须注册在 /agents/{agent_id} 系列之前，否则 FastAPI 会把
# "build" 当作 agent_id path param 匹配，导致 404。
# 当前文件结构已保证：build 路由在文件末尾，FastAPI 按注册顺序匹配，
# 路径字面量 /agents/build 比 /agents/{agent_id} 更精确，会优先匹配。
# 如后续重构路由顺序，请保持 build 路由在 {agent_id} 路由之前注册。
# ---------------------------------------------------------------------------

@router.post("/agents/build", response_model=AgentBuildResponse, status_code=status.HTTP_201_CREATED)
async def build_agent(
    data: AgentBuildRequest,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    """
    LLM 辅助生成 Agent 草稿。返回 session_id 和草稿，供前端展示 / 编辑。
    草稿在内存中暂存（生产环境换 Redis），TTL 1 小时。
    """
    svc = AgentBuilderService(db)
    try:
        session_id, draft = await svc.build(user_id, data.description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AgentBuildResponse(session_id=session_id, draft=draft)


@router.post("/agents/build/confirm", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def confirm_agent_build(
    data: AgentBuildConfirm,
    db: Session = Depends(get_db),
    user_id: Annotated[str, Depends(get_current_user)] = ...,
):
    """
    用户确认（可编辑）草稿后落库。

    - 校验 session_id 归属
    - suggested_skill_names → skill_id（找不到报 422）
    - 写入 agents 表 + agent_skills 表
    - 删除草稿
    """
    svc = AgentBuilderService(db)
    skill_repo = SkillRepository(db)
    try:
        agent = svc.confirm(user_id, data.session_id, data.edited_draft)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(agent)
    return _to_response(agent, skill_repo)
