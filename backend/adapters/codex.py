"""CodexAdapter — OpenAI Codex CLI agent integration.

Supports two modes:
  1. MCP server mode: Launch codex CLI as an MCP server (stdio transport).
     Calls the `codex` MCP tool with a prompt.
  2. Subprocess mode (fallback): Run `codex --no-interactive <prompt>`,
     stream stdout line-by-line, detect diffs and approval requests.

Reference: https://github.com/openai/codex
"""
from __future__ import annotations

import asyncio
import re
import shutil
import uuid
import logging
from typing import Any, AsyncGenerator

from backend.adapters.base import AgentAdapter
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    ApprovalRequestEvent,
    ArtifactDiffEvent,
    TokenEvent,
)
from backend.adapters.mcp_client import MCPClient
from backend.config import settings
from backend.domain.message import MessageEntity
from backend.domain.skill import SkillEntity

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
        agent_id: str,
        agent_name: str,
        bin_path: str | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self._bin_path = bin_path or settings.codex_bin_path
        self._mcp_client = mcp_client  # Set if codex supports --mcp-server

    def get_capabilities(self) -> dict[str, bool]:
        return {"supports_diff": True, "supports_approval": True}

    async def stream(
        self,
        prompt: str,
        history: list[MessageEntity],
        skills: list[SkillEntity],
    ) -> AsyncGenerator[AgentEvent, None]:
        message_id = str(uuid.uuid4())
        yield AgentStartEvent(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            message_id=message_id,
        )

        if self._mcp_client is not None:
            async for event in self._stream_via_mcp(prompt, message_id):
                yield event
        else:
            async for event in self._stream_via_subprocess(prompt, message_id):
                yield event

    # ------------------------------------------------------------------
    # MCP server mode
    # ------------------------------------------------------------------

    async def _stream_via_mcp(
        self,
        prompt: str,
        message_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Call the codex MCP tool and stream its output as events."""
        try:
            result = await self._mcp_client.call_tool("codex", {"prompt": prompt})
            for block in result.content:
                if not hasattr(block, "text"):
                    continue
                text: str = block.text
                if _looks_like_diff(text):
                    for diff_event in _parse_diff_to_events(self.agent_id, message_id, text):
                        yield diff_event
                else:
                    for line in text.splitlines(keepends=True):
                        yield TokenEvent(
                            agent_id=self.agent_id,
                            message_id=message_id,
                            content=line,
                        )
            yield AgentDoneEvent(agent_id=self.agent_id, message_id=message_id)
        except Exception as exc:
            logger.error("CodexAdapter MCP call failed: %s", exc)
            yield AgentErrorEvent(
                agent_id=self.agent_id,
                message_id=message_id,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Subprocess mode
    # ------------------------------------------------------------------

    async def _stream_via_subprocess(
        self,
        prompt: str,
        message_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Launch codex CLI as a subprocess and stream stdout."""
        bin_path = shutil.which(self._bin_path) or self._bin_path

        try:
            proc = await asyncio.create_subprocess_exec(
                bin_path,
                "--no-interactive",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield AgentErrorEvent(
                agent_id=self.agent_id,
                message_id=message_id,
                error=(
                    f"Codex CLI not found at '{bin_path}'. "
                    "Install with: npm install -g @openai/codex"
                ),
            )
            return

        diff_buffer: list[str] = []
        in_diff = False

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace")

            # Detect start of a unified diff block
            if _DIFF_FILE_RE.match(line):
                in_diff = True
                diff_buffer = [line]
                continue

            if in_diff:
                diff_buffer.append(line)
                # Diff block ends on blank line or non-diff content
                if line.strip() == "" and len(diff_buffer) > 3:
                    for ev in _parse_diff_to_events(
                        self.agent_id, message_id, "".join(diff_buffer)
                    ):
                        yield ev
                    diff_buffer = []
                    in_diff = False
                continue

            # Detect approval requests like "? running: npm install"
            approval_match = _APPROVAL_RE.match(line.strip())
            if approval_match:
                command = approval_match.group(2).strip()
                yield ApprovalRequestEvent(
                    agent_id=self.agent_id,
                    message_id=message_id,
                    action="run_command",
                    detail=command,
                )
                # Auto-approve for now; full approval flow handled by thread_service
                if proc.stdin:
                    try:
                        proc.stdin.write(b"y\n")
                        await proc.stdin.drain()
                    except Exception:
                        pass
                continue

            yield TokenEvent(
                agent_id=self.agent_id,
                message_id=message_id,
                content=line,
            )

        # Flush any remaining diff buffer
        if diff_buffer:
            for ev in _parse_diff_to_events(
                self.agent_id, message_id, "".join(diff_buffer)
            ):
                yield ev

        await proc.wait()

        if proc.returncode not in (0, None):
            assert proc.stderr is not None
            stderr = await proc.stderr.read()
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            yield AgentErrorEvent(
                agent_id=self.agent_id,
                message_id=message_id,
                error=error_msg or f"codex exited with code {proc.returncode}",
            )
            return

        yield AgentDoneEvent(agent_id=self.agent_id, message_id=message_id)


# ---------------------------------------------------------------------------
# Diff parsing helpers
# ---------------------------------------------------------------------------

def _looks_like_diff(text: str) -> bool:
    return "--- a/" in text or "+++ b/" in text


def _parse_diff_to_events(
    agent_id: str,
    message_id: str,
    patch: str,
) -> list[ArtifactDiffEvent]:
    """Parse a unified diff string into ArtifactDiffEvent objects (one per file)."""
    events: list[ArtifactDiffEvent] = []
    current_file: str | None = None
    current_lines: list[str] = []

    def _flush(file: str, lines: list[str]) -> None:
        if not file or not lines:
            return
        text = "".join(lines)
        additions = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        deletions = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        events.append(
            ArtifactDiffEvent(
                agent_id=agent_id,
                message_id=message_id,
                file=file,
                patch=text,
                additions=additions,
                deletions=deletions,
            )
        )

    for line in patch.splitlines(keepends=True):
        m = _DIFF_FILE_RE.match(line)
        if m:
            _flush(current_file, current_lines)
            current_file = m.group(1)
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    _flush(current_file, current_lines)
    return events
