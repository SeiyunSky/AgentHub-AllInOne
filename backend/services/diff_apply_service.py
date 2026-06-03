"""
DiffApplyService —— 一键应用 CodeBlock 到沙箱文件

用户在前端点击 Diff 卡片的"应用"按钮后，调本服务把 CodeBlock 里的
new_content（code 字段）写入对应沙箱路径（runtime/memory/{user_id}/{conv_id}/）。

MVP 阶段：直接写沙箱文件，不做 git commit（git 集成在后续迭代）。

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import logging

from backend.services.memory_service import InvalidMemoryPathError, resolve_sandbox_path
from backend.services.message_service import message_service

logger = logging.getLogger(__name__)


class DiffApplyService:
    async def apply(
        self,
        message_id: str,
        *,
        user_id: str,
        edited_code: str | None = None,
    ) -> dict:
        """
        把指定消息里所有 type=code 且有 filename 的 CodeBlock 写入沙箱。

        user_id：当前用户，用于定位沙箱路径。
        edited_code：用户在 Monaco 里编辑后的内容；传入时覆盖消息里的原始 code。
        返回：{"success": True, "applied_files": ["path/to/file", ...]}
        消息不存在时抛 ValueError。
        """
        msg = await message_service.get(message_id)
        if msg is None:
            raise ValueError(f"消息 {message_id} 不存在")

        conversation_id = msg.conversation_id

        applied: list[str] = []
        first_code_block = True
        for block in msg.content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "code":
                continue
            filename = block.get("filename") or ""
            code = (edited_code if edited_code is not None and first_code_block else None) \
                   or block.get("code") or ""
            first_code_block = False
            if not filename or not code:
                continue

            try:
                abs_path = resolve_sandbox_path(user_id, conversation_id, filename)
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(code, encoding="utf-8")
                applied.append(filename)
                logger.info(
                    "DiffApplyService: applied %s → sandbox conv=%s user=%s",
                    filename, conversation_id, user_id,
                )
            except InvalidMemoryPathError as e:
                logger.warning(
                    "DiffApplyService: path rejected %s conv=%s: %s",
                    filename, conversation_id, e,
                )
            except Exception:
                logger.exception(
                    "DiffApplyService: failed to write %s (message=%s)", filename, message_id
                )

        return {"success": True, "applied_files": applied}


diff_apply_service = DiffApplyService()
