"""AnthropicSDKAdapter — Anthropic Python SDK streaming with native MCP tool support.

使用 anthropic.AsyncAnthropic SDK 直接调用 Anthropic API，支持通过 MCPClient
实例调用 MCP 工具（不依赖 Claude CLI 子进程，无 OAuth session 限制）。

适用场景：需要连接 HTTP MCP 服务（如 SAP l2a-sap-mcp-glorepo）的子 Agent，
这类服务无法通过 Claude Code CLI 的 MCP 配置注入 AgentHub 的 token。

队伍：咕嘎一辈子队
修改者：咕嘎
修改日期：2026-06-09
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import anthropic

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
from backend.adapters.mcp_client import MCPClient, MCPTool
from backend.core.utils import gen_uuid
from backend.domain.agent import AgentCapabilities
from backend.domain.message import ContentBlock, TextBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory

logger = logging.getLogger(__name__)


class AnthropicSDKAdapter(AgentAdapter):
    """Streams responses via Anthropic Python SDK with native MCP tool support.

    Unlike ClaudeAdapter (which spawns a claude CLI subprocess), this adapter
    directly calls the Anthropic API through the official SDK. This allows
    injecting custom HTTP headers for MCP servers (e.g. SAP API tokens).
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        mcp_clients: list[MCPClient] | None = None,
        mcp_server_configs: list[dict] | None = None,
    ) -> None:
        from backend.config import settings
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or settings.EXTERNAL_MODEL
        self._mcp_clients = mcp_clients or []
        self._mcp_server_configs = mcp_server_configs or []
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.EXTERNAL_API_KEY,
            base_url=base_url or settings.EXTERNAL_API_BASE or None,
        )

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=bool(self._mcp_clients or self._mcp_server_configs),
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:  # type: ignore[override]
        yield AgentStartEvent(
            agent_id=inp.agent_id,
            thread_id=inp.thread_id,
            message_id=inp.message_id,
            agent_name=inp.agent_name or inp.agent_id,
            agent_avatar=inp.agent_avatar,
        )

        # Build Anthropic system string + message list
        system_text, messages = _build_anthropic_messages(
            inp.system_prompt, inp.skills, inp.history, inp.prompt
        )

        # Collect MCP tool definitions — dynamically reconnect if mcp_server_configs provided
        # (ensures latest token from DB is used, rather than the stale connection from startup)
        tool_definitions: list[dict[str, Any]] = []
        mcp_tools_by_name: dict[str, tuple[MCPClient, MCPTool]] = {}

        if self._mcp_server_configs:
            from backend.adapters.mcp_client import MCPRegistry
            effective_clients: list[MCPClient] = []
            user_id = getattr(inp, "user_id", None)
            for cfg in self._mcp_server_configs:
                try:
                    client = await MCPRegistry.get_or_connect_streamable_http(
                        cfg["server_id"],
                        cfg["url"],
                        headers=cfg.get("headers"),
                        user_id=user_id or cfg.get("user_id"),
                    )
                    effective_clients.append(client)
                except Exception as exc:
                    logger.warning("Failed to connect MCP %s: %s", cfg["server_id"], exc)
        else:
            effective_clients = self._mcp_clients

        for mcp_client in effective_clients:
            try:
                mcp_tools = await mcp_client.list_tools()
                for t in mcp_tools:
                    tool_definitions.append(_mcp_tool_to_anthropic(t))
                    mcp_tools_by_name[t.name] = (mcp_client, t)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch MCP tools from %s for %s: %s",
                    mcp_client.server_id, inp.agent_id, exc,
                )

        def _base() -> dict[str, str]:
            return {
                "agent_id": inp.agent_id,
                "thread_id": inp.thread_id,
                "message_id": inp.message_id,
            }

        # Multi-turn loop: keep calling the API until no more tool_use
        total_input_tokens = 0
        total_output_tokens = 0

        try:
            while True:
                create_kwargs: dict[str, Any] = dict(
                    model=self.model,
                    max_tokens=8096,
                    messages=messages,
                )
                if system_text:
                    create_kwargs["system"] = system_text
                if tool_definitions:
                    create_kwargs["tools"] = tool_definitions

                text_block_id: str | None = None
                # tool_use blocks accumulated during this turn
                pending_tool_blocks: list[dict[str, Any]] = []
                # current tool being accumulated
                current_tool_id: str | None = None
                current_tool_name: str | None = None
                current_tool_input_str: str = ""
                current_tool_index: int | None = None
                stop_reason: str | None = None
                assistant_content: list[dict[str, Any]] = []
                # track whether any tool_use block was started
                has_tool_use = False

                async with self._client.messages.stream(**create_kwargs) as sdk_stream:
                    async for event in sdk_stream:
                        if inp.cancel_event and inp.cancel_event.is_set():
                            yield AgentErrorEvent(**_base(), error="cancelled")
                            return

                        event_type = getattr(event, "type", None)

                        # --- content_block_start ---
                        if event_type == "content_block_start":
                            blk = event.content_block
                            blk_type = getattr(blk, "type", None)
                            if blk_type == "text":
                                text_block_id = gen_uuid()
                                yield BlockStartEvent(
                                    **_base(),
                                    block=TextBlock(block_id=text_block_id, content=""),
                                )
                                assistant_content.append({"type": "text", "text": ""})
                            elif blk_type == "tool_use":
                                has_tool_use = True
                                current_tool_id = getattr(blk, "id", None)
                                current_tool_name = getattr(blk, "name", None)
                                current_tool_input_str = ""
                                current_tool_index = event.index

                        # --- content_block_delta ---
                        elif event_type == "content_block_delta":
                            delta = event.delta
                            delta_type = getattr(delta, "type", None)
                            if delta_type == "text_delta" and text_block_id:
                                text = getattr(delta, "text", "")
                                yield BlockDeltaEvent(
                                    **_base(),
                                    block_id=text_block_id,
                                    delta={"content": text},
                                )
                                if assistant_content and assistant_content[-1]["type"] == "text":
                                    assistant_content[-1]["text"] += text
                            elif delta_type == "input_json_delta" and current_tool_name is not None:
                                current_tool_input_str += getattr(delta, "partial_json", "")

                        # --- content_block_stop ---
                        elif event_type == "content_block_stop":
                            if text_block_id is not None and not has_tool_use:
                                yield BlockStopEvent(**_base(), block_id=text_block_id)
                                text_block_id = None
                            elif current_tool_name is not None:
                                # Finish accumulating this tool_use block
                                try:
                                    tool_input = json.loads(current_tool_input_str or "{}")
                                except json.JSONDecodeError:
                                    tool_input = {}
                                pending_tool_blocks.append({
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": tool_input,
                                })
                                assistant_content.append({
                                    "type": "tool_use",
                                    "id": current_tool_id,
                                    "name": current_tool_name,
                                    "input": tool_input,
                                })
                                current_tool_id = None
                                current_tool_name = None
                                current_tool_input_str = ""

                        # --- message_delta (stop_reason) ---
                        elif event_type == "message_delta":
                            delta = event.delta
                            stop_reason = getattr(delta, "stop_reason", None)
                            usage = getattr(event, "usage", None)
                            if usage:
                                total_output_tokens += getattr(usage, "output_tokens", 0)

                        # --- message_start (input tokens) ---
                        elif event_type == "message_start":
                            msg = getattr(event, "message", None)
                            if msg:
                                usage = getattr(msg, "usage", None)
                                if usage:
                                    total_input_tokens += getattr(usage, "input_tokens", 0)

                        # --- message_stop ---
                        elif event_type == "message_stop":
                            # Close any open text block
                            if text_block_id is not None:
                                yield BlockStopEvent(**_base(), block_id=text_block_id)
                                text_block_id = None

                # No tool calls → done
                if not pending_tool_blocks:
                    break

                # Add assistant turn with tool_use blocks to message history
                messages.append({"role": "assistant", "content": assistant_content})

                # Execute each MCP tool and collect tool_result blocks
                tool_result_content: list[dict[str, Any]] = []
                for tool_block in pending_tool_blocks:
                    tool_name = tool_block["name"]
                    tool_input = tool_block.get("input", {})
                    tool_use_id = tool_block["id"]

                    tool_bid = gen_uuid()
                    yield BlockStartEvent(
                        **_base(),
                        block=ToolUseBlock(block_id=tool_bid, tool_name=tool_name, status="running"),
                    )

                    result_text: str | None = None
                    if tool_name in mcp_tools_by_name:
                        owning_client, _ = mcp_tools_by_name[tool_name]
                        logger.info(
                            "AnthropicSDKAdapter: calling MCP tool=%s input=%s agent=%s",
                            tool_name, tool_input, inp.agent_id,
                        )
                        try:
                            result = await owning_client.call_tool(tool_name, tool_input)
                            result_text = _extract_tool_result_text(result)
                            logger.info(
                                "AnthropicSDKAdapter: MCP tool=%s succeeded, result_len=%d",
                                tool_name, len(result_text or ""),
                            )
                        except Exception as exc:
                            logger.error("MCP tool call failed (%s): %s", tool_name, exc)
                            result_text = f"error: {exc}"
                    else:
                        logger.warning(
                            "AnthropicSDKAdapter: tool=%s not found in mcp_tools_by_name (available: %s)",
                            tool_name, list(mcp_tools_by_name.keys()),
                        )

                    yield BlockStopEvent(
                        **_base(),
                        block_id=tool_bid,
                        final_fields={
                            "input": tool_input,
                            "output": result_text,
                            "status": "completed" if result_text is not None else "error",
                        },
                    )

                    # Anthropic tool_result format
                    tool_result_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_text or "",
                    })

                # Add tool results as user turn → continue loop
                messages.append({"role": "user", "content": tool_result_content})

        except anthropic.APIError as exc:
            logger.error("Anthropic API error for agent %s: %s", inp.agent_id, exc)
            yield AgentErrorEvent(**_base(), error=str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected error in AnthropicSDKAdapter for agent %s", inp.agent_id)
            yield AgentErrorEvent(**_base(), error=str(exc))
            return

        yield AgentDoneEvent(
            **_base(),
            tokens_input=total_input_tokens,
            tokens_output=total_output_tokens,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blocks_to_text(blocks: list[ContentBlock]) -> str:
    """Convert content blocks to plain text for history injection."""
    parts: list[str] = []
    for b in blocks:
        if b.type == "text":
            parts.append(b.content)
        elif b.type == "tool_use":
            output = b.output or "pending"
            parts.append(f"[Tool: {b.tool_name} -> {output}]")
        elif b.type == "code":
            fname = b.filename or "file"
            parts.append(f"[Code: {fname}]")
        elif b.type == "approval":
            parts.append(f"[Approval: {b.action} ({b.status})]")
    return "\n".join(parts)


def _build_anthropic_messages(
    system_prompt: str | None,
    skills: list,
    history: list[MessageInHistory],
    prompt: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Build Anthropic system string and messages list.

    Anthropic separates system from messages (unlike OpenAI where system is a message).
    Returns (system_text, messages).
    """
    system_parts: list[str] = []
    if system_prompt:
        system_parts.append(system_prompt)
    for skill in skills:
        if skill.content:
            system_parts.append(f"\n---\n{skill.content}")
    system_text = "\n".join(system_parts)

    messages: list[dict[str, Any]] = []
    for msg in history:
        role = "user" if msg.role == "user" else "assistant"
        text = _blocks_to_text(msg.blocks)
        if msg.sender and role == "assistant":
            text = f"[{msg.sender}]: {text}"
        if text:
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": prompt})
    return system_text, messages


def _mcp_tool_to_anthropic(tool: MCPTool) -> dict[str, Any]:
    """Convert MCPTool to Anthropic tool schema format."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.input_schema or {"type": "object", "properties": {}},
    }


def _extract_tool_result_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)
    return str(result)
