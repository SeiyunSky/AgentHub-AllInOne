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
import tempfile
import os
from pathlib import Path
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
from backend.domain.agent import AgentCapabilities, MCPServerConfig
from backend.domain.message import ContentBlock, TextBlock
from backend.schemas.message import MessageInHistory

logger = logging.getLogger(__name__)


class ClaudeAdapter(AgentAdapter):
    """Streams Claude responses by invoking the Claude Code CLI as a subprocess.

    Requires `claude` to be installed and logged in (`claude login`).
    No API key configuration needed.
    """

    def __init__(self, bin_path: str | None = None, mcp_configs: list[MCPServerConfig] | None = None) -> None:
        self._bin_path = bin_path or "claude"
        self._mcp_configs = mcp_configs or []

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
            agent_name=inp.agent_name or inp.agent_id,
            agent_avatar=inp.agent_avatar,
        )

        bin_path = shutil.which(self._bin_path) or self._bin_path
        prompt = _build_prompt(inp)

        cmd = [
            bin_path, "-p",
            "--output-format", "stream-json",
            "--verbose",
        ]

        if inp.system_prompt:
            cmd += ["--append-system-prompt", _flatten_for_cli(inp.system_prompt)]

        # 写临时 MCP 配置文件（每次 stream() 都独立一份，避免并发污染）
        mcp_config_path: str | None = None
        if self._mcp_configs:
            mcp_config_path = _write_mcp_config(self._mcp_configs)
            if mcp_config_path:
                cmd += ["--mcp-config", mcp_config_path]
                # Claude CLI 非交互模式默认拒绝 MCP 工具调用，需显式授权
                cmd += ["--allowedTools", "mcp__*"]

        logger.debug("CCADAPTER CMD : %s", cmd)

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
            _cleanup_temp(mcp_config_path)
            yield AgentErrorEvent(**_base(), error="stdin write failed")
            return

        text_block_id: str | None = None
        # 从 result 事件抠出 token usage,在 AgentDoneEvent 里上报给 thread_service
        # claude stream-json 通常在 result 行里给 {"usage":{"input_tokens":N,"output_tokens":N}}
        last_tokens_input = 0
        last_tokens_output = 0

        assert proc.stdout is not None
        # 用 read() 全量读取，避免 readline() 默认 64KB 限制导致 LimitOverrunError。
        # Claude CLI 输出的每行可能是超大 JSON（含代码/文件内容），readline 会炸。
        raw_stdout = await proc.stdout.read()
        raw_lines = raw_stdout.split(b"\n")

        for raw_line in raw_lines:
            if inp.cancel_event and inp.cancel_event.is_set():
                proc.terminate()
                if text_block_id:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                _cleanup_temp(mcp_config_path)
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

                # 从 result 行解析 usage(claude CLI 当前版本会带,缺省 0)
                usage = event.get("usage") or {}
                last_tokens_input = int(
                    usage.get("input_tokens")
                    or usage.get("prompt_tokens")
                    or event.get("input_tokens")
                    or 0
                )
                last_tokens_output = int(
                    usage.get("output_tokens")
                    or usage.get("completion_tokens")
                    or event.get("output_tokens")
                    or 0
                )

                if event.get("subtype") != "success" or event.get("is_error"):
                    error_msg = event.get("result") or "Claude CLI returned an error"
                    _cleanup_temp(mcp_config_path)
                    yield AgentErrorEvent(**_base(), error=error_msg)
                    return

        await proc.wait()

        if proc.returncode not in (0, None):
            if text_block_id is not None:
                yield BlockStopEvent(**_base(), block_id=text_block_id)
            assert proc.stderr is not None
            stderr = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
            _cleanup_temp(mcp_config_path)
            yield AgentErrorEvent(
                **_base(),
                error=stderr or f"claude exited with code {proc.returncode}",
            )
            return

        # Guard: close block if result line was never received
        if text_block_id is not None:
            yield BlockStopEvent(**_base(), block_id=text_block_id)

        _cleanup_temp(mcp_config_path)
        yield AgentDoneEvent(
            **_base(),
            tokens_input=last_tokens_input,
            tokens_output=last_tokens_output,
        )


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


def _write_mcp_config(mcp_configs: list[MCPServerConfig]) -> str | None:
    """Write a temporary --mcp-config JSON file for the Claude CLI.

    Claude CLI format (supports both stdio and SSE/http):
        {"mcpServers": {
            "<server_id>": {
                "type": "stdio",
                "command": "...", "args": [...], "env": {...}
            },
            "<server_id>": {
                "type": "http",
                "url": "http://...", "headers": {...}
            }
        }}

    Returns the temp file path, or None if nothing was written.
    """
    servers: dict = {}
    for cfg in mcp_configs:
        if cfg.transport == "stdio":
            if not cfg.command:
                logger.warning("ClaudeAdapter: stdio MCP server '%s' has no command, skipping", cfg.server_id)
                continue
            entry: dict = {"type": "stdio", "command": cfg.command, "args": cfg.args}
            if cfg.env:
                entry["env"] = cfg.env
            servers[cfg.server_id] = entry
        elif cfg.transport == "sse":
            if not cfg.url:
                logger.warning("ClaudeAdapter: sse MCP server '%s' has no url, skipping", cfg.server_id)
                continue
            entry: dict = {"type": "sse", "url": cfg.url}
            if cfg.headers:
                entry["headers"] = cfg.headers
            servers[cfg.server_id] = entry
        else:
            logger.warning(
                "ClaudeAdapter: MCP server '%s' has unknown transport '%s', skipping",
                cfg.server_id, cfg.transport,
            )
            continue

    if not servers:
        return None

    try:
        fd, path = tempfile.mkstemp(prefix="agenthub-claude-mcp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump({"mcpServers": servers}, f)
        return path
    except Exception as exc:
        logger.warning("ClaudeAdapter: failed to write MCP config file: %s", exc)
        return None


def _cleanup_temp(path: str | None) -> None:
    """Remove a temporary file created by _write_mcp_config."""
    if path is None:
        return
    try:
        os.unlink(path)
    except OSError:
        pass
