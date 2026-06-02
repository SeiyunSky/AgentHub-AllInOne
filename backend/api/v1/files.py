"""
api/v1/files.py —— 文件上传端点

端点：
- POST /api/v1/files/upload   上传一个或多个文件到服务器临时目录，返回服务器端路径

上传的文件存放在 {BACKEND_ROOT}/runtime/uploads/，文件名加 UUID 前缀防冲突。
返回的路径是绝对路径，agent 可以直接读取。

队伍：咕嘎一辈子队
修改者：I778387
修改日期：2026-06-01
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel

from backend.api.deps import get_current_user

router = APIRouter()

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "runtime" / "uploads"


def _ensure_upload_dir() -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR


# ============================================================
# 响应 Schema
# ============================================================

class UploadResponse(BaseModel):
    paths: list[str]


# ============================================================
# POST /api/v1/files/upload
# ============================================================

@router.post(
    "/files/upload",
    summary="上传文件，返回服务器端绝对路径列表",
    response_model=UploadResponse,
)
async def upload_files(
    files: Annotated[list[UploadFile], File(description="上传的文件，支持多文件")],
    user_id: Annotated[str, Depends(get_current_user)],
) -> UploadResponse:
    upload_dir = _ensure_upload_dir()
    saved_paths: list[str] = []

    for file in files:
        suffix = Path(file.filename or "file").suffix
        filename = f"{uuid.uuid4().hex}{suffix}"
        dest = upload_dir / filename
        content = await file.read()
        dest.write_bytes(content)
        saved_paths.append(str(dest))

    return UploadResponse(paths=saved_paths)
