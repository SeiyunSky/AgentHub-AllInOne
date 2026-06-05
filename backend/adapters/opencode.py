"""OpencodeAdapter — opencode CLI subprocess streaming.

Invokes the locally-installed `opencode` CLI in non-interactive mode:
    opencode run --format json --dangerously-skip-permissions <prompt>

The `--format json` flag emits one JSON object per line, each describing a
streaming event from opencode's runtime. We translate those events into
AgentHub's block-level streaming protocol (AgentEvent / ContentBlock).

Stream-JSON line format (relevant types we consume):
    {"type":"step_start", ...}                       # ignored (internal)
    {"type":"step_finish",
        "part":{"tokens":{"input":N,"output":M,...}, ...}}  # → token accounting
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

system_prompt handling:
    opencode has strong alignment training and flags inputs that look like
    meta/system-level instructions — Latin role labels ("system prompt",
    "orchestrator", "sub-agent", "dispatch"), BEGIN/END banners, etc. But
    plain Chinese conversational user speech goes through fine, even when
    the body of the message contains markdown structure.

    Strategy: pass everything through plainly. _build_prompt() conditionally
    prepends a tiny Chinese opener — "你是一个子 agent，现在我给你一个任务，
    任务描述如下" — only when the dispatch prompt itself contains structural
    markers (markdown ATX headers, BEGIN/END banners, role-section labels
    like "任务："). For plain prose user-style prompts, no opener is added;
    the prompt passes through verbatim. inp.system_prompt is included as a
    "风格偏好" (style preference) framing, again only when present.

    Empirically verified that this works for the common case of a main-Agent
    dispatch with `## 任务 / ## 要求 / ## 交付物` headings: opencode reads
    the opener as "yes, here's a task description from a user" and executes
    the structured body as task content. ClaudeAdapter / CodexAdapter don't
    need this dance — they have dedicated CLI flags for system prompts.

队伍：咕嘎一辈子队
修改者：lp
修改日期：2026-05-27
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
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

        yield AgentStartEvent(**_base(), agent_name=inp.agent_name or inp.agent_id, agent_avatar=inp.agent_avatar)

        bin_path = _resolve_opencode_binary(self._bin_path)

        # Persona / task formatting is handled by _build_prompt — see its
        # docstring. Short version: structured dispatches get a tiny Chinese
        # opener ("你是一个子 agent..."); plain prose passes through unchanged.
        prompt = _build_prompt(inp)

        # Run opencode in an isolated empty cwd so it doesn't auto-load
        # project-level AGENTS.md / .opencode/ config from whatever directory
        # the AgentHub server happens to live in. Without this, opencode
        # treats the dispatch as "continue working on the current project"
        # and tends to read directory listings instead of executing the task.
        # User-level config (~/.opencode/skills/, ~/.local/share/opencode/auth.json)
        # still applies — those are the user's intentional global setup.
        sandbox_cwd: str | None = None
        try:
            sandbox_cwd = tempfile.mkdtemp(prefix="agenthub-opencode-")
        except OSError as exc:
            logger.warning(
                "OpencodeAdapter: failed to create sandbox cwd (%s); "
                "falling back to inherited cwd",
                exc,
            )

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
                cwd=sandbox_cwd,
            )
        except FileNotFoundError:
            _cleanup_sandbox(sandbox_cwd)
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
        # Per-stream() token accumulators. opencode emits a `step_finish`
        # event after each LLM round (including ones triggered by tool
        # invocations), each carrying part.tokens={input, output, ...}. We
        # sum across all rounds and surface the total in AgentDoneEvent so
        # thread_service can roll it into threads.tokens_total.
        total_tokens_input = 0
        total_tokens_output = 0

        assert proc.stdout is not None
        async for raw_line in proc.stdout:
            if inp.cancel_event and inp.cancel_event.is_set():
                proc.terminate()
                if text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                yield AgentErrorEvent(**_base(), error="cancelled")
                _cleanup_sandbox(sandbox_cwd)
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

            elif event_type == "step_finish":
                # Accumulate token usage. opencode reports per-round usage in
                # `part.tokens.{input, output}` after each LLM round. Other
                # fields (reasoning, cache.read/write, cost) are richer than
                # AgentHub's AgentDoneEvent currently models — we pull only
                # the two fields the protocol exposes and drop the rest.
                tokens = (part.get("tokens") if isinstance(part, dict) else None) or {}
                try:
                    total_tokens_input += int(tokens.get("input", 0) or 0)
                    total_tokens_output += int(tokens.get("output", 0) or 0)
                except (TypeError, ValueError):
                    # Defensive: a malformed tokens object shouldn't sink the
                    # whole stream — just skip this round's contribution.
                    logger.debug(
                        "OpencodeAdapter: malformed step_finish.part.tokens=%r, skipping",
                        tokens,
                    )

            # step_start and any other types: ignored — they describe
            # internal opencode runtime state with no AgentHub equivalent.

        # Close any still-open text block
        if text_block_id is not None:
            yield BlockStopEvent(**_base(), block_id=text_block_id)

        await proc.wait()

        if proc.returncode not in (0, None):
            assert proc.stderr is not None
            stderr = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            _cleanup_sandbox(sandbox_cwd)
            yield AgentErrorEvent(
                **_base(),
                error=stderr or f"opencode exited with code {proc.returncode}",
            )
            return

        _cleanup_sandbox(sandbox_cwd)
        yield AgentDoneEvent(
            **_base(),
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
        )


# ---------------------------------------------------------------------------
# Sandbox cwd cleanup
# ---------------------------------------------------------------------------

def _resolve_opencode_binary(bin_hint: str) -> str:
    """Resolve to the real opencode executable, bypassing .cmd shims on Windows.

    Why: npm installs `opencode` on Windows as `opencode.cmd` (a batch file
    that forwards to `node_modules\\opencode-ai\\bin\\opencode.exe`).
    `shutil.which("opencode")` returns the .cmd. Running a .cmd through
    `subprocess.create_subprocess_exec` makes cmd.exe interpret the prompt
    argv — and cmd.exe treats `>`, `<`, `|`, `&` etc. as shell metacharacters,
    even inside quoted args, breaking on prompts that mention them (e.g. a
    docstring containing `>>> fib(7)`). Empirically observed:
    "> was unexpected at this time."

    Fix: if which() returned a .cmd, peek inside it to find the real .exe
    being forwarded to. Fall back to the .cmd if we can't parse it (the
    failure mode is just back to the original problem; no regression).
    """
    found = shutil.which(bin_hint) or bin_hint
    # If we got a .cmd shim, try to extract the real executable path from it.
    if not found.lower().endswith(".cmd"):
        return found
    try:
        text = Path(found).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return found
    # npm shims look like:  "%dp0%\node_modules\opencode-ai\bin\opencode.exe" %*
    # Extract the first .exe path mentioned.
    import re as _re
    match = _re.search(r'"([^"]+\.exe)"', text)
    if not match:
        return found
    real = match.group(1)
    # %dp0% is the shim's own directory
    real = real.replace("%dp0%", str(Path(found).parent))
    real = real.replace("%~dp0", str(Path(found).parent))
    real_path = Path(real).resolve()
    if real_path.is_file():
        return str(real_path)
    return found


def _cleanup_sandbox(path: str | None) -> None:
    """Remove the temporary sandbox cwd created in stream(), best-effort.

    Safe to call with None (when sandbox creation failed). Errors during
    rmtree are logged at debug level and swallowed — a leaked tmp dir is
    cosmetic, not functional.
    """
    if not path:
        return
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception as exc:  # pragma: no cover — defensive only
        logger.debug("OpencodeAdapter: failed to clean up sandbox %s: %s", path, exc)


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

def _blocks_to_text(blocks) -> str:
    """Reduce a heterogeneous block list to plain text.

    Accepts both shapes the codebase passes around in practice:
      - Pydantic ContentBlock instances (from MessageInHistory.blocks) —
        access fields via attribute (b.type, b.content, ...)
      - dicts (from ORM Message.content, which is a JSON column) — access
        fields via .get(...)

    thread_service.list_recent currently returns ORM Message rows directly
    into StreamInput.history (despite the type hint saying MessageInHistory),
    so we have to be tolerant. See backend/repositories/message_repo.py.
    """
    parts: list[str] = []
    for b in blocks or []:
        if isinstance(b, dict):
            btype = b.get("type")
            get = b.get
        else:
            btype = getattr(b, "type", None)
            get = lambda k, default=None, _b=b: getattr(_b, k, default)

        if btype == "text":
            parts.append(get("content") or "")
        elif btype == "thinking":
            pass
        elif btype == "tool_use":
            output = get("output") or "pending"
            parts.append(f"[Tool: {get('tool_name')} -> {output}]")
        elif btype == "code":
            fname = get("filename") or "file"
            add = get("additions") or 0
            delete = get("deletions") or 0
            parts.append(f"[Code: {fname} +{add}/-{delete}]")
        elif btype == "approval":
            parts.append(f"[Approval: {get('action')} ({get('status')})]")
    return "\n".join(parts)


def _msg_field(msg, name: str, default=None):
    """Read `msg.<name>` from either a Pydantic schema or an ORM model.

    For ORM Message, the body is in `.content` (JSON list), not `.blocks`.
    Pydantic shapes can use either name. We fall back to dict access too,
    since some call sites pass plain dicts.
    """
    # Special-case the blocks/content rename: Pydantic schema uses .blocks,
    # ORM Message uses .content. Try blocks first since that's the protocol.
    if name == "blocks":
        if isinstance(msg, dict):
            return msg.get("blocks") or msg.get("content") or default
        val = getattr(msg, "blocks", None)
        if val is None:
            val = getattr(msg, "content", None)
        return val if val is not None else default
    if isinstance(msg, dict):
        return msg.get(name, default)
    val = getattr(msg, name, default)
    # role might be an enum on the ORM model; normalise to plain str
    if name == "role" and hasattr(val, "value"):
        return val.value
    return val


def _build_prompt(inp: StreamInput) -> str:
    """Stringify persona + history + task into a single CLI argument for opencode.

    Design philosophy: opencode's alignment training is fine with normal
    conversational user speech, but flags inputs that look like a meta/system-
    level instruction — markdown headings as section labels, BEGIN/END banners,
    orchestrator-style "Task: / Requirements: / Deliverable:" templates, etc.
    AgentHub's main Agent (orchestrator) tends to dispatch in exactly that
    structured style. So we conditionally soften it:

      - if the dispatch prompt looks structured (markdown headers / banners /
        explicit role-section labels), we prepend a short, plain Chinese
        opener telling opencode "you're a sub-agent and here's a task" so it
        knows the structure that follows is just the task description, not
        a jailbreak attempt;
      - if the dispatch prompt is already plain prose (no structural markers),
        we pass it through unchanged — adding an opener would only add noise.

    The opener is intentionally short and conversational, with no Latin
    keywords like "orchestrator" / "system prompt" / "dispatch" / "BEGIN" /
    "END" — these specific tokens are what opencode flags. Empirically
    verified that this minimal Chinese opener works.

    inp.system_prompt is treated the same way — its content is included as
    a "preference for this task" framing, but only when present.
    """
    chunks: list[str] = []

    if inp.system_prompt:
        chunks.append(
            "另外，关于我希望你处理这个任务的风格偏好，参考下面这段说明：\n\n"
            + inp.system_prompt
        )

    for skill in inp.skills or []:
        if getattr(skill, "content", None):
            chunks.append(
                f"还有一份关于 {skill.name} 的参考资料可能用得上：\n\n{skill.content}"
            )

    if inp.history:
        history_lines: list[str] = []
        for msg in inp.history:
            text = _blocks_to_text(_msg_field(msg, "blocks"))
            if not text:
                continue
            role = _msg_field(msg, "role", "user")
            if role == "user":
                history_lines.append(f"我之前说过：{text}")
            else:
                speaker = _msg_field(msg, "sender") or "你"
                history_lines.append(f"{speaker} 当时回复：{text}")
        if history_lines:
            chunks.append("先回顾一下之前聊到的内容：\n\n" + "\n\n".join(history_lines))

    # The dispatch prompt itself — wrap with an opener only if it looks
    # structured enough to confuse opencode's alignment.
    task = inp.prompt
    if _looks_structured(task) or _looks_structured(inp.system_prompt or ""):
        chunks.append(
            "你是一个子 agent，现在我给你一个任务，任务描述如下：\n\n" + task
        )
    else:
        chunks.append(task)

    return _flatten_for_cli("\n\n".join(chunks))


# Patterns that indicate a prompt is "structured" enough that opencode might
# read it as a jailbreak template. Any single match counts.
_ATX_HEADER_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_BANNER_RE = re.compile(r"^(?:[-=*]{3,}|.*\b(?:BEGIN|END)\b.*)$", re.MULTILINE)
# Section labels — line starts with a known role/section word followed by
# colon (Chinese or ASCII), nothing else on the line. Tightened so prose
# sentences ending in `:` don't trip it.
_SECTION_LABEL_RE = re.compile(
    r"^(?:任务|背景|要求|交付物|输入|输出|约束|目标|步骤|说明|注意|备注"
    r"|Task|Background|Requirements?|Deliverable|Inputs?|Outputs?|"
    r"Constraints?|Goals?|Steps?|Notes?)\s*[:：]\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _looks_structured(text: str) -> bool:
    """Return True if the prompt looks structured enough to need a softening opener.

    Heuristic — we don't want false positives on prose that happens to mention
    'task' or use a colon. Triggers:
      - any markdown ATX header (`# foo` through `###### foo`)
      - banner / rule lines (`---`, `===`, lines containing BEGIN/END markers)
      - explicit role-section labels on their own line (`任务：`, `Requirements:`)

    Empirically: a dispatch prompt with all four sections (Task/Background/
    Requirements/Deliverable) trips this; a plain "请帮我写一段代码 ..."
    user message does not.
    """
    if not text:
        return False
    if _ATX_HEADER_RE.search(text):
        return True
    if _BANNER_RE.search(text):
        return True
    if _SECTION_LABEL_RE.search(text):
        return True
    return False


def _flatten_for_cli(text: str) -> str:
    """Collapse newlines into spaces so the prompt survives Windows CreateProcess.

    Why: Windows passes a multi-arg subprocess.exec command to CreateProcess
    by joining args into a single command-line string and re-quoting. argv
    elements that contain real newlines (\\n / \\r\\n) get truncated at the
    first newline by some intermediate (the .cmd shim, cmd.exe, or the way
    opencode's bun-bundled binary parses argv). Empirically observed:
    opencode receives only the first line of a multi-line prompt and replies
    "your message got cut off". ClaudeAdapter has the same defense for the
    same reason; see backend/adapters/claude.py:_flatten_for_cli.

    Effect: paragraph breaks are lost, but the prompt content survives.
    opencode handles whitespace-collapsed prose fine — much better than it
    handles a truncated prompt.
    """
    if not text:
        return text
    flat = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return " ".join(flat.split())
