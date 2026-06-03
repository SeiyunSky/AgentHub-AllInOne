"""
api/v1/squads.py —— Agent 小组预设端点

GET /api/v1/squads   返回所有预设小组列表
GET /api/v1/squads/{squad_id}  返回单个小组详情（含参与 Agent 的完整信息）

预设数据来自 backend/squads/*.json，纯静态文件，不入库。
每个 json 文件结构：
  {
    "id": "code_squad",
    "name": "代码小队",
    "description": "...",
    "icon": "code",
    "agent_ids": ["agent-coder-builtin", ...]
  }

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.repositories.agent_repo import AgentRepository


logger = logging.getLogger(__name__)
router = APIRouter()

_SQUADS_DIR = Path(__file__).resolve().parent.parent.parent / "squads"


# ── Schema ──────────────────────────────────────────────────

class AgentSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    avatar_url: Optional[str] = None


class SquadResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    agent_ids: list[str]
    agents: list[AgentSummary] = []


# ── Helpers ──────────────────────────────────────────────────

def _load_squads() -> list[dict]:
    squads = []
    if not _SQUADS_DIR.exists():
        return squads
    for path in sorted(_SQUADS_DIR.glob("*.json")):
        try:
            squads.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            logger.warning("squads: 解析 %s 失败，跳过", path.name)
    return squads


def _enrich(squad: dict, db: Session) -> SquadResponse:
    """把 agent_ids 解析成 AgentSummary 列表（找不到的 id 直接跳过）。"""
    repo = AgentRepository(db)
    agents = []
    for aid in squad.get("agent_ids", []):
        row = repo.get(aid)
        if row:
            agents.append(AgentSummary(
                id=row.id,
                name=row.name,
                description=row.description,
                type=row.type,
                avatar_url=row.avatar_url,
            ))
    return SquadResponse(**squad, agents=agents)


# ── Routes ───────────────────────────────────────────────────

@router.get(
    "/squads",
    response_model=list[SquadResponse],
    summary="获取所有预设 Agent 小组",
)
def list_squads(
    db: Annotated[Session, Depends(get_db)],
) -> list[SquadResponse]:
    return [_enrich(s, db) for s in _load_squads()]


@router.get(
    "/squads/{squad_id}",
    response_model=SquadResponse,
    summary="获取单个预设小组详情",
)
def get_squad(
    squad_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> SquadResponse:
    for s in _load_squads():
        if s.get("id") == squad_id:
            return _enrich(s, db)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"小组 {squad_id} 不存在")
