"""
DiffApplyService —— 一键应用 CodeBlock 到本地文件

用户在前端点击 Diff 卡片的"应用"按钮后，调本服务把 CodeBlock 里的
new_content（code 字段）写入对应文件路径。

MVP 阶段：直接写本地文件，不做 git commit（git 集成在后续迭代）。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.services.message_service import message_service

logger = logging.getLogger(__name__)


class DiffApplyService:
    async def apply(self, message_id: str) -> dict:
        """
        把指定消息里所有 type=code 且有 filename 的 CodeBlock 写入磁盘。

        返回：{"success": True, "applied_files": ["path/to/file", ...]}
        消息不存在时抛 ValueError。
        """
        msg = await message_service.get(message_id)
        if msg is None:
            raise ValueError(f"消息 {message_id} 不存在")

        applied: list[str] = []
        for block in msg.content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "code":
                continue
            filename = block.get("filename") or ""
            code = block.get("code") or ""
            if not filename or not code:
                continue

            try:
                path = Path(filename)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(code, encoding="utf-8")
                applied.append(filename)
                logger.info("DiffApplyService: applied %s (message=%s)", filename, message_id)
            except Exception:
                logger.exception(
                    "DiffApplyService: failed to write %s (message=%s)", filename, message_id
                )

        return {"success": True, "applied_files": applied}


diff_apply_service = DiffApplyService()
