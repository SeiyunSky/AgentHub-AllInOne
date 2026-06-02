"""
DiffService —— 构造文件变更 CodeBlock

把工具执行前后的文件内容对比，用 difflib 生成 additions/deletions 统计，
构造 domain.message.CodeBlock 供 post_execution hook 推给前端展示。

不依赖 git，只用标准库 difflib，MVP 阶段不需要真实 git 操作。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import difflib

from backend.core.utils import gen_uuid
from backend.domain.message import CodeBlock


_LANGUAGE_MAP: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "jsx",
    "vue": "vue",
    "md": "markdown",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "sh": "bash",
    "bash": "bash",
    "html": "html",
    "css": "css",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "swift": "swift",
    "cpp": "cpp",
    "c": "c",
    "sql": "sql",
}


def _guess_language(filename: str) -> str:
    if "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return _LANGUAGE_MAP.get(ext, ext)
    return ""


class DiffService:
    def build_code_block(
        self,
        filename: str,
        old_content: str,
        new_content: str,
    ) -> CodeBlock:
        """
        根据文件前后内容构造 CodeBlock。

        - old_content 为空字符串时表示新建文件（纯新增 diff）
        - additions / deletions 用 difflib.ndiff 统计
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        diff = list(difflib.ndiff(old_lines, new_lines))
        additions = sum(1 for line in diff if line.startswith("+ "))
        deletions = sum(1 for line in diff if line.startswith("- "))

        return CodeBlock(
            block_id=gen_uuid(),
            language=_guess_language(filename),
            code=new_content,
            filename=filename,
            old_code=old_content if old_content else None,
            additions=additions,
            deletions=deletions,
        )


diff_service = DiffService()
