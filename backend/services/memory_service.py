"""
memory_service —— 长期记忆文件读写助手

记忆按 user + conversation 隔离,目录结构:
    runtime/memory/{user_id}/{conversation_id}/
        ├── MEMORY.md          ← 索引(一行一条)
        └── {name}.md          ← 单条记忆(YAML frontmatter + 正文)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from backend.core.frontmatter import parse_frontmatter, render_frontmatter
from backend.domain.memory import (
    MemoryEntry,
    MemoryFrontmatter,
    MemoryIndexLine,
    MemoryType,
)

logger = logging.getLogger(__name__)


# ============================================================
# 配置
# ============================================================

_DEFAULT_MEMORY_ROOT = Path(__file__).resolve().parent.parent / "runtime" / "memory"
MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(_DEFAULT_MEMORY_ROOT)))
_MEMORY_ROOT_RESOLVED = MEMORY_ROOT.resolve()

INDEX_FILE_NAME = "MEMORY.md"

NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
INDEX_LINE_RE = re.compile(r"^- \[(?P<name>[^\]]+)\]\([^)]+\)\s*—\s*(?P<desc>.*)$")


# ============================================================
# 异常
# ============================================================

class InvalidMemoryNameError(ValueError):
    """记忆 name 不符合命名规范"""


class InvalidMemoryPathError(ValueError):
    """user_id / conversation_id 解析后路径逃出 MEMORY_ROOT"""


class MemoryNotFoundError(FileNotFoundError):
    """指定记忆文件不存在"""


# ============================================================
# 路径
# ============================================================

def get_memory_dir(user_id: str, conversation_id: str) -> Path:
    """返回某用户某会话的记忆目录(不保证存在)。"""
    candidate = (MEMORY_ROOT / user_id / conversation_id).resolve()
    try:
        candidate.relative_to(_MEMORY_ROOT_RESOLVED)
    except ValueError as exc:
        raise InvalidMemoryPathError(
            f"非法路径:user_id={user_id!r} conversation_id={conversation_id!r}"
        ) from exc
    return candidate


def ensure_memory_dir(user_id: str, conversation_id: str) -> Path:
    """保证记忆目录存在(含父目录),并初始化空 MEMORY.md。"""
    dir_path = get_memory_dir(user_id, conversation_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    index_path = dir_path / INDEX_FILE_NAME
    if not index_path.exists():
        index_path.write_text("", encoding="utf-8", newline="\n")
    return dir_path


def get_memory_file_path(user_id: str, conversation_id: str, name: str) -> Path:
    """根据 name 计算单条记忆文件路径。"""
    if not NAME_PATTERN.match(name):
        raise InvalidMemoryNameError(
            f"记忆 name 必须匹配 ^[a-z0-9_-]+$,实际收到: {name!r}"
        )
    return get_memory_dir(user_id, conversation_id) / f"{name}.md"


# ============================================================
# 渲染
# ============================================================

def _render_memory_frontmatter(meta: MemoryFrontmatter) -> str:
    payload = {
        "name": meta.name,
        "description": meta.description,
        "type": meta.type.value,
        "created_at": meta.created_at.isoformat(),
        "updated_at": meta.updated_at.isoformat(),
    }
    return render_frontmatter(payload)


def render_memory_file(entry: MemoryEntry) -> str:
    """渲染完整 .md 文件内容(frontmatter + 正文)。"""
    return _render_memory_frontmatter(entry.frontmatter) + "\n" + entry.content.rstrip() + "\n"


# ============================================================
# 单条记忆读写
# ============================================================

def read_memory(user_id: str, conversation_id: str, name: str) -> MemoryEntry:
    """读取一条记忆。文件不存在抛 MemoryNotFoundError。"""
    path = get_memory_file_path(user_id, conversation_id, name)
    if not path.exists():
        raise MemoryNotFoundError(str(path))

    raw = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)

    try:
        frontmatter = MemoryFrontmatter(
            name=meta.get("name", name),
            description=meta.get("description", ""),
            type=meta.get("type", MemoryType.REFERENCE.value),
            created_at=_parse_dt(meta.get("created_at"), path),
            updated_at=_parse_dt(meta.get("updated_at"), path),
        )
    except ValidationError as exc:
        logger.warning("记忆 %s 的 frontmatter 字段校验失败: %s,降级用兜底值", name, exc)
        now = datetime.now(timezone.utc)
        frontmatter = MemoryFrontmatter(
            name=name,
            description="(元数据缺失)",
            type=MemoryType.REFERENCE,
            created_at=now,
            updated_at=now,
        )

    return MemoryEntry(frontmatter=frontmatter, content=body.strip())


def write_memory(user_id: str, conversation_id: str, entry: MemoryEntry) -> Path:
    """
    写入(或覆盖)一条记忆,同时维护 MEMORY.md 索引。
    updated_at 始终被刷新为当前 UTC 时间。
    """
    ensure_memory_dir(user_id, conversation_id)
    path = get_memory_file_path(user_id, conversation_id, entry.frontmatter.name)

    fresh_frontmatter = entry.frontmatter.model_copy(
        update={"updated_at": datetime.now(timezone.utc)}
    )
    snapshot = MemoryEntry(frontmatter=fresh_frontmatter, content=entry.content)

    path.write_text(render_memory_file(snapshot), encoding="utf-8", newline="\n")
    _upsert_index_line(
        user_id,
        conversation_id,
        snapshot.frontmatter.name,
        snapshot.frontmatter.description,
    )
    return path


def delete_memory(user_id: str, conversation_id: str, name: str) -> bool:
    """删除一条记忆 + 移除索引行。返回是否实际删除了文件。"""
    path = get_memory_file_path(user_id, conversation_id, name)
    existed = path.exists()
    if existed:
        path.unlink()
    _remove_index_line(user_id, conversation_id, name)
    return existed


# ============================================================
# 列表 / 索引
# ============================================================

def list_memories(user_id: str, conversation_id: str) -> list[MemoryEntry]:
    """列出该会话下所有记忆(全量解析,含正文)。"""
    dir_path = get_memory_dir(user_id, conversation_id)
    if not dir_path.exists():
        return []

    entries: list[MemoryEntry] = []
    for md_path in sorted(dir_path.glob("*.md")):
        if md_path.name == INDEX_FILE_NAME:
            continue
        try:
            entry = read_memory(user_id, conversation_id, md_path.stem)
        except InvalidMemoryNameError:
            logger.warning("跳过非法命名的记忆文件: %s", md_path)
            continue
        except MemoryNotFoundError:
            continue
        except Exception as exc:
            logger.warning("跳过损坏的记忆文件 %s: %s", md_path, exc)
            continue
        entries.append(entry)
    return entries


def list_index(user_id: str, conversation_id: str) -> list[MemoryIndexLine]:
    """解析 MEMORY.md 拿到精简索引(name + description)。"""
    dir_path = get_memory_dir(user_id, conversation_id)
    index_path = dir_path / INDEX_FILE_NAME
    if not index_path.exists():
        return []

    raw = index_path.read_text(encoding="utf-8")
    lines: list[MemoryIndexLine] = []
    for line in raw.splitlines():
        match = INDEX_LINE_RE.match(line.strip())
        if not match:
            continue
        try:
            lines.append(
                MemoryIndexLine(
                    name=match.group("name"),
                    description=match.group("desc"),
                )
            )
        except ValidationError:
            continue
    return lines


# ============================================================
# 内部:索引行维护
# ============================================================

def _format_index_line(name: str, description: str) -> str:
    return f"- [{name}]({name}.md) — {description}"


def _upsert_index_line(
    user_id: str,
    conversation_id: str,
    name: str,
    description: str,
) -> None:
    dir_path = ensure_memory_dir(user_id, conversation_id)
    index_path = dir_path / INDEX_FILE_NAME
    new_line = _format_index_line(name, description)

    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    pattern = re.compile(rf"^- \[{re.escape(name)}\]\([^)]+\).*$", re.MULTILINE)

    if pattern.search(existing):
        updated = pattern.sub(new_line, existing)
    else:
        suffix = "" if existing.endswith("\n") or not existing else "\n"
        updated = f"{existing}{suffix}{new_line}\n"

    index_path.write_text(updated, encoding="utf-8", newline="\n")


def _remove_index_line(user_id: str, conversation_id: str, name: str) -> None:
    dir_path = get_memory_dir(user_id, conversation_id)
    index_path = dir_path / INDEX_FILE_NAME
    if not index_path.exists():
        return
    pattern = re.compile(rf"^- \[{re.escape(name)}\]\([^)]+\).*\n?", re.MULTILINE)
    raw = index_path.read_text(encoding="utf-8")
    updated = pattern.sub("", raw)
    index_path.write_text(updated, encoding="utf-8", newline="\n")


# ============================================================
# 内部:时间字段宽容解析
# ============================================================

def _parse_dt(value: Optional[object], fallback_path: Path) -> datetime:
    """解析 frontmatter 时间字段,统一返回 aware datetime,失败时用 mtime 兜底。"""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return datetime.now(timezone.utc)
