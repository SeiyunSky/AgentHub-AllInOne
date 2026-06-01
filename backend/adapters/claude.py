"""ClaudeAdapter — Claude Code CLI subprocess streaming.

Invokes the locally-installed `claude` CLI in non-interactive mode:
    claude -p <prompt> --output-format stream-json --verbose

No API key or base_url configuration needed — uses the CLI's own
login session (OAuth via `claude login`).

Stream-JSON line format (relevant types):
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
    {"type": "result",    "subtype": "success", "result": "..."}
    {"type": "result",    "subtype": "error_during_execution", ...}

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-26
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import shutil
from typing import AsyncIterator

from backend.adapters.base import AgentAdapter, StreamInput
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    BlockDeltaEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.core.utils import gen_uuid
from backend.domain.agent import AgentCapabilities
from backend.domain.message import ContentBlock, TextBlock
from backend.schemas.message import MessageInHistory

logger = logging.getLogger(__name__)


class ClaudeAdapter(AgentAdapter):
    """Streams Claude responses by invoking the Claude Code CLI as a subprocess.

    Requires `claude` to be installed and logged in (`claude login`).
    No API key configuration needed.
    """

    def __init__(self, bin_path: str | None = None) -> None:
        self._bin_path = bin_path or "claude"

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=False,
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        yield AgentStartEvent(
            **_base(),
            agent_name=inp.agent_id,
        )

        bin_path = shutil.which(self._bin_path) or self._bin_path
        prompt = _build_prompt(inp)

        # 不再用 -p 把 prompt 当命令行参数:Windows 命令行硬上限 8191 字符,
        # 一旦 prompt 含历史/代码长度超限,subprocess 直接报 "The command line is too long"。
        # 改成 stdin 喂入,长度由 CLI 内部缓冲处理,无 Windows CLI 长度限制。
        cmd = [
            bin_path, "-p",
            "--output-format", "stream-json",
            "--verbose",
        ]

        if inp.system_prompt:
            # 同 _build_prompt 的换行兼容处理:Windows CLI 不接受 `-p` / `--append-system-prompt`
            # 含真换行,会让 CLI 退化失败
            cmd += ["--append-system-prompt", _flatten_for_cli(inp.system_prompt)]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield AgentErrorEvent(
                **_base(),
                error=f"Claude CLI not found at '{bin_path}'. Run `claude login` to set up.",
            )
            return

        # 把 prompt 从 stdin 喂给 CLI,避免命令行长度限制。
        # 写完立刻 close,告诉 CLI "输入到此为止",触发它进入流式输出。
        try:
            assert proc.stdin is not None
            proc.stdin.write(prompt.encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()
        except Exception:
            logger.exception("Claude CLI stdin write failed")
            yield AgentErrorEvent(**_base(), error="stdin write failed")
            return

        text_block_id: str | None = None

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            if inp.cancel_event and inp.cancel_event.is_set():
                proc.terminate()
                if text_block_id:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                yield AgentErrorEvent(**_base(), error="cancelled")
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                event = _json.loads(line)
            except _json.JSONDecodeError:
                continue

            event_type = event.get("type")

            if event_type == "assistant":
                # Extract text content from message blocks
                message = event.get("message", {})
                for block in message.get("content", []):
                    if block.get("type") != "text":
                        continue
                    text = block.get("text", "")
                    if not text:
                        continue
                    if text_block_id is None:
                        text_block_id = gen_uuid()
                        yield BlockStartEvent(
                            **_base(),
                            block=TextBlock(block_id=text_block_id, content=""),
                        )
                    yield BlockDeltaEvent(
                        **_base(),
                        block_id=text_block_id,
                        delta={"content": text},
                    )

            elif event_type == "result":
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                    text_block_id = None

                if event.get("subtype") != "success" or event.get("is_error"):
                    error_msg = event.get("result") or "Claude CLI returned an error"
                    yield AgentErrorEvent(**_base(), error=error_msg)
                    return

        await proc.wait()

        if proc.returncode not in (0, None):
            if text_block_id is not None:
                yield BlockStopEvent(**_base(), block_id=text_block_id)
            assert proc.stderr is not None
            stderr = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            yield AgentErrorEvent(
                **_base(),
                error=stderr or f"claude exited with code {proc.returncode}",
            )
            return

        # Guard: close block if result line was never received
        if text_block_id is not None:
            yield BlockStopEvent(**_base(), block_id=text_block_id)

        yield AgentDoneEvent(**_base())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blocks_to_text(blocks: list[ContentBlock]) -> str:
    parts: list[str] = []
    for b in blocks:
        if b.type == "text":
            parts.append(b.content)
        elif b.type == "thinking":
            pass
        elif b.type == "tool_use":
            output = b.output or "pending"
            parts.append(f"[Tool: {b.tool_name} -> {output}]")
        elif b.type == "code":
            fname = b.filename or "file"
            add = b.additions or 0
            delete = b.deletions or 0
            parts.append(f"[Code: {fname} +{add}/-{delete}]")
        elif b.type == "approval":
            parts.append(f"[Approval: {b.action} ({b.status})]")
    return "\n".join(parts)


def _build_prompt(inp: StreamInput) -> str:
    """Prepend conversation history to the prompt as plain text context.

    Windows 兼容性:`claude` CLI 在 Windows 上不正确处理 `-p` 参数中的真换行符
    —— 含换行的 prompt 会让 CLI 退化成对话模式直接返回普通文本(不再输出 stream-json
    事件流),导致 ClaudeAdapter 解析全失败。
    返回前调 _flatten_for_cli 把换行压成空格,跨平台行为一致。
    """
    if not inp.history:
        return _flatten_for_cli(inp.prompt)

    parts: list[str] = []
    for msg in inp.history:
        role = "User" if msg.role == "user" else (msg.sender or "Assistant")
        text = _blocks_to_text(msg.blocks)
        if text:
            parts.append(f"{role}: {text}")

    parts.append(f"User: {inp.prompt}")
    return _flatten_for_cli("\n\n".join(parts))


def _flatten_for_cli(text: str) -> str:
    """
    把 prompt 中的换行符压成空格,适配 Windows `claude` CLI 的 `-p` 参数限制。

    处理顺序:
    1. \\r\\n / \\r → \\n  (统一行终止符)
    2. \\n → ' '          (换行变空格)
    3. 多个连续空格 → 单空格(避免 markdown 段落间的双空行变成多空格)
    """
    if not text:
        return text
    flat = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    # 折叠连续空格(包括 tab 等空白字符)
    return " ".join(flat.split())


def _build_system_prompt(base: str | None, skills: list) -> str:
    parts: list[str] = []
    if base:
        parts.append(base)
    for skill in skills:
        if skill.content:
            parts.append(f"\n---\n{skill.content}")
    return "\n".join(parts)
