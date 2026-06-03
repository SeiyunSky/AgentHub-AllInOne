"""
api/v1/sandbox.py —— 会话沙箱文件浏览端点

每个会话都有独立沙箱目录:`runtime/memory/{user_id}/{conversation_id}/`,
orchestrator 主 Agent 调 create_file / edit_file 工具时把文件写到这里。

本路由组让前端能浏览、读取、保存、下载沙箱内的文件,所有路径都强制
经过 memory_service.resolve_sandbox_path 校验,防止 `../foo` 之类越界。

端点:
- GET    /sandbox/{conv_id}/files                     列文件树(递归)
- GET    /sandbox/{conv_id}/files/raw?path=...        读文本内容
- PUT    /sandbox/{conv_id}/files/raw                 写文本内容
- GET    /sandbox/{conv_id}/files/download?path=...   下载二进制(StreamingResponse)

注:raw / download 把 path 放 query 而不是 path param,避免 FastAPI 把
`src/a.py` 的 `/` 当路径分隔。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-06-03
"""

from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user
from backend.services.conversation_service import conversation_service
from backend.services.memory_service import (
    InvalidMemoryPathError,
    ensure_memory_dir,
    relative_to_sandbox,
    resolve_sandbox_path,
)


logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# Schemas
# ============================================================

class SandboxFileNode(BaseModel):
    """单个沙箱文件 / 目录条目。"""

    name: str = Field(description="文件或目录名(不含路径)")
    path: str = Field(description="相对沙箱根的 POSIX 风格路径")
    size: int = Field(description="字节大小;目录为 0")
    mtime: float = Field(description="最后修改时间(Unix 秒,float)")
    is_dir: bool = Field(description="是否目录")


class ListFilesResponse(BaseModel):
    files: list[SandboxFileNode]


class ReadFileResponse(BaseModel):
    content: str
    mime_type: str
    size: int


class WriteFileRequest(BaseModel):
    path: str = Field(min_length=1)
    content: str


class WriteFileResponse(BaseModel):
    size: int


class UploadedFile(BaseModel):
    name: str = Field(description="保存到沙箱后的最终文件名(可能因重名加后缀)")
    path: str = Field(description="相对沙箱根的 POSIX 路径")
    size: int


class UploadResponse(BaseModel):
    files: list[UploadedFile]


# ============================================================
# 工具
# ============================================================

# 跳过这些隐藏 / 系统文件,前端不需要看到
_HIDDEN_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}

# 文件名清洗:只保留字母数字 / 下划线 / 短划线 / 点,其他全转 _,
# 连续 _ 折叠为单个,首尾 ._- 去掉。防止空格 / 中文 / 不可打印字符引起跨平台路径问题。
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(raw: str) -> str:
    """清洗上传文件名,保留扩展名,只允许 [A-Za-z0-9._-]。"""
    name = (raw or "file").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]  # 去路径
    cleaned = _SAFE_FILENAME_RE.sub("_", name)
    # 防止纯点(. / ..)
    if cleaned in {".", ".."}:
        cleaned = "file"
    # stem 全是非法字符时(纯中文等)cleaned 形如 "_.ext",保留 _ 不去
    # 只把首尾的 - 去掉(. 和 _ 都可能是合法 stem 的开头)
    cleaned = cleaned.strip("-")
    return cleaned or "file"


def _next_available(base_dir: Path, filename: str) -> Path:
    """重名时加 (1) / (2) 后缀直到找到不存在的路径。"""
    candidate = base_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    n = 1
    while True:
        candidate = base_dir / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _safe_resolve(user_id: str, conversation_id: str, rel_path: str) -> Path:
    """resolve_sandbox_path 包装,把 InvalidMemoryPathError 转 400。"""
    try:
        return resolve_sandbox_path(user_id, conversation_id, rel_path)
    except InvalidMemoryPathError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# ============================================================
# 端点
# ============================================================

@router.get(
    "/sandbox/{conv_id}/files",
    summary="列出会话沙箱所有文件(递归)",
    response_model=ListFilesResponse,
)
async def list_sandbox_files(
    conv_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
) -> ListFilesResponse:
    await conversation_service.assert_owned_by(conv_id, user_id)
    base = ensure_memory_dir(user_id, conv_id).resolve()

    files: list[SandboxFileNode] = []
    for entry in sorted(base.rglob("*")):
        if entry.name.startswith(".") or entry.name in _HIDDEN_NAMES:
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        rel = str(entry.relative_to(base)).replace("\\", "/")
        files.append(SandboxFileNode(
            name=entry.name,
            path=rel,
            size=0 if entry.is_dir() else stat.st_size,
            mtime=stat.st_mtime,
            is_dir=entry.is_dir(),
        ))
    return ListFilesResponse(files=files)


@router.get(
    "/sandbox/{conv_id}/files/raw",
    summary="读取沙箱内某文件文本内容",
    response_model=ReadFileResponse,
)
async def read_sandbox_file(
    conv_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    path: Annotated[str, Query(min_length=1, description="相对沙箱根的路径")],
) -> ReadFileResponse:
    await conversation_service.assert_owned_by(conv_id, user_id)
    abs_path = _safe_resolve(user_id, conv_id, path)

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if abs_path.is_dir():
        raise HTTPException(status_code=400, detail=f"{path} 是目录,不是文件")

    try:
        content = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=415,
            detail=f"文件不是 UTF-8 文本,请用下载端点: {e}",
        ) from e

    mime_type = mimetypes.guess_type(abs_path.name)[0] or "text/plain"
    return ReadFileResponse(
        content=content,
        mime_type=mime_type,
        size=len(content.encode("utf-8")),
    )


@router.put(
    "/sandbox/{conv_id}/files/raw",
    summary="写入沙箱内某文件文本内容(覆盖)",
    response_model=WriteFileResponse,
)
async def write_sandbox_file(
    conv_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    body: WriteFileRequest,
) -> WriteFileResponse:
    await conversation_service.assert_owned_by(conv_id, user_id)
    abs_path = _safe_resolve(user_id, conv_id, body.path)

    if abs_path.is_dir():
        raise HTTPException(status_code=400, detail=f"{body.path} 是目录")

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    # newline='' 保 LF,避免 Windows 上写出 CRLF
    abs_path.write_text(body.content, encoding="utf-8", newline="")

    size = len(body.content.encode("utf-8"))
    logger.info(
        "sandbox write conv=%s user=%s path=%s size=%d",
        conv_id, user_id, body.path, size,
    )
    return WriteFileResponse(size=size)


@router.get(
    "/sandbox/{conv_id}/files/download",
    summary="下载沙箱内某文件(浏览器附件)",
)
async def download_sandbox_file(
    conv_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    path: Annotated[str, Query(min_length=1, description="相对沙箱根的路径")],
) -> FileResponse:
    await conversation_service.assert_owned_by(conv_id, user_id)
    abs_path = _safe_resolve(user_id, conv_id, path)

    if not abs_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if abs_path.is_dir():
        raise HTTPException(status_code=400, detail=f"{path} 是目录")

    rel = relative_to_sandbox(user_id, conv_id, abs_path)
    return FileResponse(
        path=str(abs_path),
        filename=Path(rel).name,
        media_type="application/octet-stream",
    )


@router.post(
    "/sandbox/{conv_id}/files/upload",
    summary="上传文件到会话沙箱根目录",
    response_model=UploadResponse,
)
async def upload_sandbox_files(
    conv_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    files: Annotated[list[UploadFile], File(description="上传的文件,支持多个")],
) -> UploadResponse:
    """
    把上传文件直接落到当前会话沙箱根目录,Agent 立即能用 read_file 读到。

    - 文件名清洗:只允许 [A-Za-z0-9._-],其他字符转 _
    - 重名:加 ` (1)` / ` (2)` 后缀
    - 路径校验复用 resolve_sandbox_path,杜绝越界
    """
    await conversation_service.assert_owned_by(conv_id, user_id)
    base = ensure_memory_dir(user_id, conv_id).resolve()

    saved: list[UploadedFile] = []
    for upload in files:
        safe_name = _safe_filename(upload.filename or "file")
        # 用 _next_available 在沙箱根挑一个不冲突的名字
        target = _next_available(base, safe_name)
        # 通过 resolve_sandbox_path 再校一遍,防止 _safe_filename 残留越界字符
        # (理论上 _safe_filename 已过滤掉 / 和 \,这里是双保险)
        final_path = _safe_resolve(user_id, conv_id, target.name)

        content = await upload.read()
        final_path.write_bytes(content)

        rel = relative_to_sandbox(user_id, conv_id, final_path)
        size = final_path.stat().st_size
        saved.append(UploadedFile(name=final_path.name, path=rel, size=size))
        logger.info(
            "sandbox upload conv=%s user=%s name=%s size=%d",
            conv_id, user_id, final_path.name, size,
        )

    return UploadResponse(files=saved)
