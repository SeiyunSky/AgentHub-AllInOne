"""OpencodeAdapter — opencode CLI subprocess streaming.

Invokes the locally-installed `opencode` CLI in non-interactive mode:
    opencode run --format json --dangerously-skip-permissions <prompt>

The `--format json` flag emits one JSON object per line, each describing a
streaming event from opencode's runtime. We translate those events into
AgentHub's block-level streaming protocol (AgentEvent / ContentBlock).

Stream-JSON line format (relevant types we consume):
    {"type":"step_start", ...}                       # ignored (internal)
    {"type":"step_finish", ...}                      # ignored (internal)
    {"type":"text", "part":{"text":"..."}}           # → TextBlock delta
    {"type":"tool_use", "part":{"tool":"...",
        "callID":"...",
        "state":{"status":"completed",
                 "input":{...}, "output":"..."}}}    # → ToolUseBlock (start+delta+stop)

Why `--dangerously-skip-permissions`:
    AgentHub adapters do not implement the bidirectional approval round-trip.
    See codex.py for the parallel auto-approve choice. Approval-requiring
    workflows belong above the adapter layer.

Why CLI subprocess and not the HTTP server:
    Consistent with ClaudeAdapter / CodexAdapter — opencode is treated as a
    single-shot text generator per `stream()` call. Session reuse, model
    switching, fork, etc. are out of scope for the AgentHub adapter contract.

队伍：咕嘎一辈子队
修改者：lp
修改日期：2026-05-27
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import shutil
from typing import Any, AsyncIterator

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
from backend.domain.message import ContentBlock, TextBlock, ToolUseBlock

logger = logging.getLogger(__name__)


class OpencodeAdapter(AgentAdapter):
    """Streams opencode responses by invoking the opencode CLI as a subprocess.

    Requires `opencode` to be installed (npm install -g opencode-ai) and
    a configured provider/model (run `opencode auth` once to set up).
    """

    def __init__(self, bin_path: str | None = None) -> None:
        self._bin_path = bin_path or os.environ.get("OPENCODE_BIN_PATH", "opencode")

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=False,
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        yield AgentStartEvent(**_base(), agent_name=inp.agent_id)

        bin_path = shutil.which(self._bin_path) or self._bin_path
        prompt = _build_prompt(inp)

        cmd = [
            bin_path, "run",
            "--format", "json",
            "--dangerously-skip-permissions",
            prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            yield AgentErrorEvent(
                **_base(),
                error=(
                    f"Opencode CLI not found at '{bin_path}'. "
                    "Install with: npm install -g opencode-ai"
                ),
            )
            return

        # Track the currently-open text block so streamed text accumulates into
        # one block. Tool-use events interrupt and close the text block.
        text_block_id: str | None = None
        # Map opencode tool callID → our internal block_id (so we could in
        # principle support streaming tool output; opencode currently emits
        # tool_use only after completion, so this is forward-looking).
        tool_block_ids: dict[str, str] = {}

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            if inp.cancel_event and inp.cancel_event.is_set():
                proc.terminate()
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                yield AgentErrorEvent(**_base(), error="cancelled")
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                event = _json.loads(line)
            except _json.JSONDecodeError:
                # opencode banner / non-JSON noise on stdout — skip silently
                continue

            event_type = event.get("type")
            part = event.get("part") or {}

            if event_type == "text":
                text = part.get("text", "")
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

            elif event_type == "tool_use":
                # Close any open text block before emitting the tool block
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                    text_block_id = None

                async for ev in _emit_tool_use(_base, part, tool_block_ids):
                    yield ev

            # step_start / step_finish / other types: ignored — they describe
            # internal opencode runtime state with no AgentHub equivalent.

        # Close any still-open text block
        if text_block_id is not None:
            yield BlockStopEvent(**_base(), block_id=text_block_id)

        await proc.wait()

        if proc.returncode not in (0, None):
            assert proc.stderr is not None
            stderr = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            yield AgentErrorEvent(
                **_base(),
                error=stderr or f"opencode exited with code {proc.returncode}",
            )
            return

        yield AgentDoneEvent(**_base())


# ---------------------------------------------------------------------------
# Tool-use translation
# ---------------------------------------------------------------------------

async def _emit_tool_use(
    base_fn,
    part: dict[str, Any],
    tool_block_ids: dict[str, str],
) -> AsyncIterator[AgentEvent]:
    """Translate one opencode `tool_use` part into block_start/delta/stop.

    Opencode emits the tool event after the tool finishes, so input/output
    are both available. We still split into start+delta+stop to fit the
    block-level streaming protocol cleanly (and to leave room for future
    in-flight tool reporting).
    """
    base = base_fn()
    tool_name: str = part.get("tool", "unknown_tool")
    call_id: str | None = part.get("callID")
    state: dict[str, Any] = part.get("state") or {}
    status: str = state.get("status", "completed")
    tool_input = state.get("input") if isinstance(state.get("input"), dict) else None
    tool_output = state.get("output")
    if tool_output is not None and not isinstance(tool_output, str):
        tool_output = _json.dumps(tool_output, ensure_ascii=False)

    block_id = tool_block_ids.get(call_id) if call_id else None
    if block_id is None:
        block_id = gen_uuid()
        if call_id:
            tool_block_ids[call_id] = block_id

        yield BlockStartEvent(
            **base,
            block=ToolUseBlock(
                block_id=block_id,
                tool_name=tool_name,
                input=tool_input,
                status="running",
            ),
        )

    final_status = "completed" if status == "completed" else (
        "error" if status == "error" else "running"
    )
    delta: dict[str, Any] = {"status": final_status}
    if tool_output is not None:
        delta["output"] = tool_output
    error_message = state.get("error") if isinstance(state.get("error"), str) else None
    if error_message:
        delta["error_message"] = error_message

    yield BlockDeltaEvent(**base, block_id=block_id, delta=delta)
    yield BlockStopEvent(**base, block_id=block_id, final_fields=delta)


# ---------------------------------------------------------------------------
# Prompt building (mirrors ClaudeAdapter — string-concatenated history)
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

    Opencode does not consume an external messages array via the CLI, so we
    follow ClaudeAdapter's approach: stringify history into the prompt body.
    System prompt (if any) is also prepended since opencode CLI has no
    --append-system-prompt-equivalent flag in `run` mode.
    """
    chunks: list[str] = []

    if inp.system_prompt:
        chunks.append(f"System: {inp.system_prompt}")

    for skill in inp.skills or []:
        if getattr(skill, "content", None):
            chunks.append(f"Skill ({skill.name}):\n{skill.content}")

    for msg in inp.history or []:
        role = "User" if msg.role == "user" else (msg.sender or "Assistant")
        text = _blocks_to_text(msg.blocks)
        if text:
            chunks.append(f"{role}: {text}")

    chunks.append(f"User: {inp.prompt}")
    return "\n\n".join(chunks)
