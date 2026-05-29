"""
skills API — Skill CRUD 端点

GET    /skills              列表（当前用户可见，不含正文）
POST   /skills              创建（正文写文件 + 元数据写 DB）
GET    /skills/{id}         详情（含正文）
PATCH  /skills/{id}         更新
DELETE /skills/{id}         删除

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-28
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.schemas.skill import SkillCreate, SkillResponse, SkillUpdate, SkillWithContent
from backend.services.skill_service import SkillService

router = APIRouter()

_DEMO_USER_ID = "GUGA"


@router.get("/skills", response_model=list[SkillResponse])
def list_skills(db: Session = Depends(get_db)):
    svc = SkillService(db)
    skills = svc._repo.list_visible_for_user(_DEMO_USER_ID)
    return [SkillResponse.model_validate(s) for s in skills]


@router.post("/skills", response_model=SkillWithContent, status_code=status.HTTP_201_CREATED)
def create_skill(data: SkillCreate, db: Session = Depends(get_db)):
    svc = SkillService(db)
    existing = svc._repo.get_by_name(data.name, _DEMO_USER_ID)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Skill '{data.name}' already exists")
    skill = svc.create(_DEMO_USER_ID, data)
    return svc._read_content(skill)


@router.get("/skills/{skill_id}", response_model=SkillWithContent)
def get_skill(skill_id: str, db: Session = Depends(get_db)):
    svc = SkillService(db)
    result = svc.get_with_content(skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return result


@router.patch("/skills/{skill_id}", response_model=SkillWithContent)
def update_skill(skill_id: str, data: SkillUpdate, db: Session = Depends(get_db)):
    svc = SkillService(db)
    skill = svc.update(skill_id, _DEMO_USER_ID, data)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found or not owned by you")
    return svc._read_content(skill)


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: str, db: Session = Depends(get_db)):
    svc = SkillService(db)
    if not svc.delete(skill_id, _DEMO_USER_ID):
        raise HTTPException(status_code=404, detail="Skill not found or not owned by you")
