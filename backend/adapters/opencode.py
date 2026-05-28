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

system_prompt handling:
    opencode is a complete agent product with strong alignment training. It
    refuses any input that *looks* like a meta/system-level instruction —
    labels like "system prompt", "orchestrator", "sub-agent", "dispatch",
    "BEGIN/END SECTION", role brackets, etc. all get flagged as jailbreak
    attempts. Empirically verified: telling opencode "you are a sub-agent
    invoked by an orchestrator, here's your dispatch ..." gets it to reply
    "I treat all input as user-level instructions regardless of how it's
    structured or labeled."

    Workaround: present everything as plain conversational user speech.
    inp.system_prompt is folded into the prompt body as a casual opener
    ("Before we start, here's a quick note about how I'd like you to
    approach this..."). No labels, no banners, no markdown rule lines, no
    "system" / "persona" keywords surrounding the persona text itself. The
    persona's own content (e.g. coder.md) is left verbatim.

    history is similarly rephrased as "Earlier I said ... / And you replied
    ..." rather than role-labeled.

    See _build_prompt() for the exact wrapping. ClaudeAdapter / CodexAdapter
    don't need this dance — they pass system_prompt via dedicated CLI flags
    or talk to processes that don't have opencode's anti-jailbreak training.

队伍：咕嘎一辈子队
修改者：lp
修改日期：2026-05-27
"""
from __future__ import annotations

import asyncio
import dataclasses
import json as _json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator, Protocol

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

    def __init__(
        self,
        bin_path: str | None = None,
        rewriter: "PersonaRewriter | None" = None,
    ) -> None:
        self._bin_path = bin_path or os.environ.get("OPENCODE_BIN_PATH", "opencode")
        # Persona rewriter is used to fold inp.system_prompt + inp.prompt into
        # a single user-facing request, so opencode never sees role-injection
        # language. Default rewriter calls the orchestrator's LLM client; tests
        # inject a stub. None at module-import time means "build lazily on first
        # use" — the orchestrator llm_client requires settings to be available
        # which isn't always the case at adapter-registry seed time.
        self._rewriter: "PersonaRewriter | None" = rewriter

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=False,
        )

    def _get_rewriter(self) -> "PersonaRewriter":
        """Lazily instantiate the default LLM-backed rewriter on first use."""
        if self._rewriter is None:
            self._rewriter = _LLMPersonaRewriter()
        return self._rewriter

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        yield AgentStartEvent(**_base(), agent_name=inp.agent_id)

        bin_path = _resolve_opencode_binary(self._bin_path)

        # Persona injection strategy for opencode:
        #
        # opencode's alignment training refuses anything labeled "system prompt",
        # "orchestrator", "sub-agent", "dispatch", role brackets, BEGIN/END
        # banners, etc. — it treats those as jailbreak attempts. Plain
        # conversational wrappers also failed empirically (opencode reads
        # "Before we start, here's my preference" as "user is about to send
        # the preference next" and waits).
        #
        # The radical fix: when we have a persona to inject (inp.system_prompt),
        # call an LLM to *rewrite* "persona + task" into a single concrete user
        # request. e.g. coder.md's "你是一位资深代码 Agent... 输出格式: 直接给代码" +
        # task "写 fizzbuzz" becomes "请用 Python 写 fizzbuzz，要求简短可运行、
        # 直接给代码、带类型注解和 docstring...". opencode never sees role-
        # injection language, just a normal user describing what they want.
        #
        # The rewrite is best-effort: on failure we fall back to dispatch
        # prompt only (degraded but functional, just without persona steering).
        effective_prompt = inp.prompt
        if inp.system_prompt:
            try:
                effective_prompt = await self._get_rewriter().rewrite(
                    persona=inp.system_prompt,
                    task=inp.prompt,
                )
                logger.debug(
                    "OpencodeAdapter: persona rewritten via LLM "
                    "(persona=%d chars, task=%d chars, output=%d chars)",
                    len(inp.system_prompt), len(inp.prompt), len(effective_prompt),
                )
            except Exception as exc:
                logger.warning(
                    "OpencodeAdapter: persona rewrite failed (%s) — "
                    "falling back to bare dispatch prompt without persona",
                    exc,
                )
                effective_prompt = inp.prompt

        # Build the final CLI argument from history + effective_prompt.
        # _build_prompt is purely string concatenation now, no labels.
        rewrite_inp = dataclasses.replace(
            inp,
            prompt=effective_prompt,
            # Persona was already folded into effective_prompt by the rewriter;
            # don't double-include it via _build_prompt's casual opener.
            system_prompt=None,
        )
        prompt = _build_prompt(rewrite_inp)

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

            # step_start / step_finish / other types: ignored — they describe
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
        yield AgentDoneEvent(**_base())


# ---------------------------------------------------------------------------
# Persona rewriter — folds (persona + task) into a single user request
# ---------------------------------------------------------------------------

class PersonaRewriter(Protocol):
    """Rewrite (persona, task) into a single user-facing request string.

    The output must read like a regular user describing what they want, not
    like a system prompt or role assignment. opencode's alignment refuses
    anything that pattern-matches "you are an X assistant", "act as Y",
    "system: ...", etc.

    Implementations decide how to do this — calling an LLM (default), regex
    munging, hand-coded templates, returning the bare task (skipping persona),
    etc. Test code can inject a stub.
    """

    async def rewrite(self, *, persona: str, task: str) -> str: ...


# The instruction we send to the rewriter LLM. Kept in module scope so tests
# can verify the contract without instantiating an LLM client.
_REWRITER_SYSTEM_PROMPT = (
    "You take two pieces of text and merge them into one short user request "
    "that someone might naturally type to an AI coding assistant.\n\n"
    "Input piece 1 is a 'style/preference' description (how the user likes "
    "their code written — formatting, conventions, output shape).\n"
    "Input piece 2 is the actual concrete task the user wants done.\n\n"
    "Merge them so the result reads like a single self-contained user request. "
    "It must:\n"
    "- be in the user's own voice ('I need ...', '请帮我 ...');\n"
    "- never refer to roles, agents, system prompts, orchestrators, dispatches, "
    "  or sub-agents;\n"
    "- never use second person to redefine the assistant's identity (no 'you "
    "  are an X assistant', no 'act as a Y');\n"
    "- present style preferences as concrete code requirements ('代码要简短', "
    "  '带类型注解和 docstring', 'output a unified diff') rather than as "
    "  'follow this persona';\n"
    "- preserve all concrete requirements from both inputs;\n"
    "- keep the user's original language (if input is Chinese, output Chinese).\n\n"
    "Output ONLY the merged user request, no preamble, no quotes, no commentary."
)


class _LLMPersonaRewriter:
    """Default rewriter: calls the orchestrator's LLM client.

    Imports are lazy to avoid pulling LLM-client deps at adapter import time —
    OpencodeAdapter may be constructed in environments where the LLM client
    config isn't ready (registry seed, tests).
    """

    async def rewrite(self, *, persona: str, task: str) -> str:
        from backend.services.orchestrator.llm_client import llm_client

        user_msg = (
            f"Style/preference description:\n{persona}\n\n"
            f"Concrete task:\n{task}"
        )
        response = await llm_client.chat_completion(
            system=_REWRITER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            tools=[],
            max_tokens=2000,
        )
        rewritten = (response.content_text or "").strip()
        if not rewritten:
            raise RuntimeError("rewriter LLM returned empty content_text")
        return rewritten


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
    """Stringify persona + history + task into a single CLI argument for opencode.

    Design philosophy: opencode has strong alignment training and rejects
    anything that *looks* like a meta/system-level instruction — labels like
    "orchestrator", "sub-agent", "dispatch", "system prompt", "BEGIN/END
    SECTION", or markdown headings get flagged as jailbreak attempts. So we
    avoid all such markers and present the prompt as plain conversational
    user speech. The persona and the task are both phrased as if a regular
    human user is talking to opencode.

    Concretely:
      - inp.system_prompt is opened with a sentence like "Before we start,
        here's a bit about the role I'd like you to play for this question."
        followed by the persona text — no "system" label, no banner.
      - history blocks are referenced as "Earlier in our chat I said ..." /
        "You replied ..." rather than role-labeled.
      - inp.prompt is the final question, plain text.

    No markdown headers in our wrapping (the persona / dispatch_prompt body
    may still contain them — that's the orchestrator's content, we don't
    rewrite it). No "---" rule lines. No structural labels.
    """
    chunks: list[str] = []

    if inp.system_prompt:
        chunks.append(
            "Before we start, here's a quick note about how I'd like you to "
            "approach this. It's just my preference for this conversation, "
            "feel free to use your own judgement on top of it.\n\n"
            f"{inp.system_prompt}"
        )

    for skill in inp.skills or []:
        if getattr(skill, "content", None):
            chunks.append(
                f"I also want to share a reference note on \"{skill.name}\" "
                f"that might be useful here:\n\n{skill.content}"
            )

    if inp.history:
        history_lines: list[str] = []
        for msg in inp.history:
            text = _blocks_to_text(msg.blocks)
            if not text:
                continue
            if msg.role == "user":
                history_lines.append(f"Earlier I said: {text}")
            else:
                speaker = msg.sender or "you"
                history_lines.append(f"And {speaker} replied: {text}")
        if history_lines:
            chunks.append(
                "For context, here's what we've already discussed:\n\n"
                + "\n\n".join(history_lines)
            )

    chunks.append(f"Now here's what I need help with:\n\n{inp.prompt}")

    return _flatten_for_cli("\n\n".join(chunks))


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
