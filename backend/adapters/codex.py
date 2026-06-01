"""CodexAdapter — OpenAI Codex CLI agent integration.

Supports two modes:
  1. MCP server mode: Launch codex CLI as an MCP server (stdio transport).
     Calls the `codex` MCP tool with a prompt.
  2. Subprocess mode (fallback): Run `codex exec <prompt>`,
     stream stdout line-by-line, detect diffs and approval requests.

Reference: https://github.com/openai/codex

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-25
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import logging
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
from backend.adapters.mcp_client import MCPClient
from backend.core.utils import gen_uuid
from backend.domain.agent import AgentCapabilities
from backend.domain.message import ApprovalBlock, CodeBlock, TextBlock

logger = logging.getLogger(__name__)

# Regex to detect unified diff headers
_DIFF_FILE_RE = re.compile(r"^--- a/(.+)$")
_APPROVAL_RE = re.compile(r"^\?\s*(running|run):\s*(.+)$", re.IGNORECASE)


class CodexAdapter(AgentAdapter):
    """Integrates with the OpenAI Codex CLI coding agent.

    Prefer MCP server mode when available; fall back to subprocess streaming
    if the installed Codex CLI does not support --mcp-server.
    """

    def __init__(
        self,
        bin_path: str | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self._bin_path = bin_path or os.environ.get("CODEX_BIN_PATH", "codex")
        self._mcp_client = mcp_client

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=True,
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        yield AgentStartEvent(
            agent_id=inp.agent_id,
            thread_id=inp.thread_id,
            message_id=inp.message_id,
            agent_name=inp.agent_id,
        )

        if self._mcp_client is not None:
            async for event in self._stream_via_mcp(inp):
                yield event
        else:
            async for event in self._stream_via_subprocess(inp):
                yield event

    # ------------------------------------------------------------------
    # MCP server mode
    # ------------------------------------------------------------------

    async def _stream_via_mcp(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        try:
            result = await self._mcp_client.call_tool("codex", {"prompt": inp.prompt})
            for block in result.content:
                if not hasattr(block, "text"):
                    continue
                text: str = block.text
                if _looks_like_diff(text):
                    async for ev in _emit_diff_blocks(_base, text):
                        yield ev
                else:
                    bid = gen_uuid()
                    yield BlockStartEvent(**_base(), block=TextBlock(block_id=bid, content=""))
                    for line in text.splitlines(keepends=True):
                        if inp.cancel_event and inp.cancel_event.is_set():
                            yield BlockStopEvent(**_base(), block_id=bid)
                            yield AgentErrorEvent(**_base(), error="cancelled")
                            return
                        yield BlockDeltaEvent(**_base(), block_id=bid, delta={"content": line})
                    yield BlockStopEvent(**_base(), block_id=bid)
            yield AgentDoneEvent(**_base())
        except Exception as exc:
            logger.error("CodexAdapter MCP call failed: %s", exc)
            yield AgentErrorEvent(
                agent_id=inp.agent_id,
                thread_id=inp.thread_id,
                message_id=inp.message_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Subprocess mode
    # ------------------------------------------------------------------

    async def _stream_via_subprocess(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        bin_path = shutil.which(self._bin_path) or self._bin_path

        try:
            proc = await asyncio.create_subprocess_exec(
                bin_path,
                "exec",
                inp.prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield AgentErrorEvent(
                **_base(),
                error=(
                    f"Codex CLI not found at '{bin_path}'. "
                    "Install with: npm install -g @openai/codex"
                ),
            )
            return

        diff_buffer: list[str] = []
        in_diff = False
        text_block_id: str | None = None

        assert proc.stdout is not None

        async for raw_line in proc.stdout:
            if inp.cancel_event and inp.cancel_event.is_set():
                proc.terminate()
                if text_block_id:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                yield AgentErrorEvent(**_base(), error="cancelled")
                return

            line = raw_line.decode("utf-8", errors="replace")

            if _DIFF_FILE_RE.match(line):
                # Close any open text block before starting diff
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                    text_block_id = None
                in_diff = True
                diff_buffer = [line]
                continue

            if in_diff:
                diff_buffer.append(line)
                if line.strip() == "" and len(diff_buffer) > 3:
                    async for ev in _emit_diff_blocks(_base, "".join(diff_buffer)):
                        yield ev
                    diff_buffer = []
                    in_diff = False
                continue

            approval_match = _APPROVAL_RE.match(line.strip())
            if approval_match:
                # Close text block before approval
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                    text_block_id = None
                command = approval_match.group(2).strip()
                approval_bid = gen_uuid()
                yield BlockStartEvent(
                    **_base(),
                    block=ApprovalBlock(
                        block_id=approval_bid,
                        action="run_command",
                        detail=command,
                        status="pending",
                    ),
                )
                # Auto-approve; full approval flow handled by thread_service
                yield BlockStopEvent(**_base(), block_id=approval_bid, final_fields={"status": "approved"})
                if proc.stdin:
                    try:
                        proc.stdin.write(b"y\n")
                        await proc.stdin.drain()
                    except Exception:
                        pass
                continue

            # Regular text output
            if text_block_id is None:
                text_block_id = gen_uuid()
                yield BlockStartEvent(**_base(), block=TextBlock(block_id=text_block_id, content=""))
            yield BlockDeltaEvent(**_base(), block_id=text_block_id, delta={"content": line})

        # Flush any remaining diff buffer
        if diff_buffer:
            async for ev in _emit_diff_blocks(_base, "".join(diff_buffer)):
                yield ev

        # Close text block
        if text_block_id is not None:
            yield BlockStopEvent(**_base(), block_id=text_block_id)

        await proc.wait()

        if proc.returncode not in (0, None):
            assert proc.stderr is not None
            stderr = await proc.stderr.read()
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            yield AgentErrorEvent(
                **_base(),
                error=error_msg or f"codex exited with code {proc.returncode}",
            )
            return

        yield AgentDoneEvent(**_base())


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def _looks_like_diff(text: str) -> bool:
    return "--- a/" in text or "+++ b/" in text


async def _emit_diff_blocks(base_fn, patch: str) -> AsyncIterator[AgentEvent]:
    """Parse a unified diff and emit a CodeBlock per file."""
    current_file: str | None = None
    current_lines: list[str] = []

    def _flush(file: str, lines: list[str]):
        if not file or not lines:
            return None
        text = "".join(lines)
        additions = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
        deletions = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
        return (file, text, additions, deletions)

    file_patches: list[tuple[str, str, int, int]] = []

    for line in patch.splitlines(keepends=True):
        m = _DIFF_FILE_RE.match(line)
        if m:
            entry = _flush(current_file, current_lines)
            if entry:
                file_patches.append(entry)
            current_file = m.group(1)
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    entry = _flush(current_file, current_lines)
    if entry:
        file_patches.append(entry)

    base = base_fn()
    for file_path, text, additions, deletions in file_patches:
        bid = gen_uuid()
        yield BlockStartEvent(
            **base,
            block=CodeBlock(
                block_id=bid,
                language="diff",
                code="",
                filename=file_path,
            ),
        )
        yield BlockDeltaEvent(**base, block_id=bid, delta={"code": text})
        yield BlockStopEvent(
            **base,
            block_id=bid,
            final_fields={"additions": additions, "deletions": deletions},
        )