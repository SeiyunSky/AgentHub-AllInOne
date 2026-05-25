"""ClaudeAdapter — Anthropic SDK streaming with MCP tool support."""
from __future__ import annotations

import json as _json
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
from backend.domain.message import ApprovalBlock, ContentBlock, TextBlock, ThinkingBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory

logger = logging.getLogger(__name__)


class ClaudeAdapter(AgentAdapter):
    """Streams Claude responses using the Anthropic Python SDK.

    Optionally attaches an MCPClient to expose MCP tools to Claude.
    Tools with side effects surface as an ApprovalBlock and pause
    execution; read-only tools are called transparently.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self.model = model or os.environ.get("ANTHROPIC_MODEL_ID", "claude-sonnet-4-6")
        self._mcp_client = mcp_client
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            base_url=base_url or os.environ.get("ANTHROPIC_BASE_URL") or None,
        )

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

        messages = _build_anthropic_messages(inp.history, inp.prompt)
        system = _build_system_prompt(inp.system_prompt, inp.skills)

        tool_definitions: list[dict[str, Any]] = []
        mcp_tools_by_name: dict[str, MCPTool] = {}
        if self._mcp_client is not None:
            try:
                mcp_tools = await self._mcp_client.list_tools()
                for t in mcp_tools:
                    tool_definitions.append(_mcp_tool_to_anthropic(t))
                    mcp_tools_by_name[t.name] = t
            except Exception as exc:
                logger.warning("Failed to fetch MCP tools for %s: %s", inp.agent_id, exc)

        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=8192,
                system=system or anthropic.NOT_GIVEN,
                messages=messages,
                tools=tool_definitions or anthropic.NOT_GIVEN,
            ) as sdk_stream:
                # Per-block accumulation state
                current_block_id: str | None = None
                current_tool_input_str: str = ""
                current_tool_name: str = ""

                async for event in sdk_stream:
                    if inp.cancel_event and inp.cancel_event.is_set():
                        yield AgentErrorEvent(**_base(), error="cancelled")
                        return

                    et = event.type

                    if et == "content_block_start":
                        block = event.content_block
                        bid = gen_uuid()
                        current_block_id = bid

                        if block.type == "thinking":
                            yield BlockStartEvent(
                                **_base(),
                                block=ThinkingBlock(block_id=bid, content=""),
                            )
                        elif block.type == "text":
                            yield BlockStartEvent(
                                **_base(),
                                block=TextBlock(block_id=bid, content=""),
                            )
                        elif block.type == "tool_use":
                            current_tool_name = block.name
                            current_tool_input_str = ""
                            yield BlockStartEvent(
                                **_base(),
                                block=ToolUseBlock(block_id=bid, tool_name=block.name, status="running"),
                            )

                    elif et == "content_block_delta" and current_block_id:
                        d = event.delta
                        if d.type == "thinking_delta":
                            yield BlockDeltaEvent(
                                **_base(),
                                block_id=current_block_id,
                                delta={"content": d.thinking},
                            )
                        elif d.type == "text_delta":
                            yield BlockDeltaEvent(
                                **_base(),
                                block_id=current_block_id,
                                delta={"content": d.text},
                            )
                        elif d.type == "input_json_delta":
                            current_tool_input_str += d.partial_json

                    elif et == "content_block_stop" and current_block_id:
                        bid = current_block_id

                        # Resolve and execute tool if this was a tool_use block
                        if current_tool_name:
                            try:
                                tool_input = _json.loads(current_tool_input_str or "{}")
                            except _json.JSONDecodeError:
                                tool_input = {}

                            mcp_tool = mcp_tools_by_name.get(current_tool_name)

                            if mcp_tool and mcp_tool.has_side_effects:
                                # Emit approval block before executing
                                approval_bid = gen_uuid()
                                yield BlockStartEvent(
                                    **_base(),
                                    block=ApprovalBlock(
                                        block_id=approval_bid,
                                        action=current_tool_name,
                                        detail=str(tool_input),
                                        status="pending",
                                    ),
                                )
                                yield BlockStopEvent(
                                    **_base(),
                                    block_id=approval_bid,
                                    final_fields={"status": "approved"},
                                )

                            result_text: str | None = None
                            if mcp_tool and self._mcp_client is not None:
                                try:
                                    result = await self._mcp_client.call_tool(
                                        current_tool_name, tool_input
                                    )
                                    result_text = _extract_tool_result_text(result)
                                except Exception as exc:
                                    logger.error("MCP tool call failed (%s): %s", current_tool_name, exc)
                                    result_text = f"error: {exc}"

                            yield BlockStopEvent(
                                **_base(),
                                block_id=bid,
                                final_fields={
                                    "input": tool_input,
                                    "output": result_text,
                                    "status": "completed" if result_text is not None else "error",
                                },
                            )
                            current_tool_name = ""
                            current_tool_input_str = ""
                        else:
                            yield BlockStopEvent(**_base(), block_id=bid)

                        current_block_id = None

        except anthropic.APIError as exc:
            logger.error("Anthropic API error for agent %s: %s", inp.agent_id, exc)
            yield AgentErrorEvent(**_base(), error=str(exc))
            return

        yield AgentDoneEvent(**_base())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blocks_to_text(blocks: list[ContentBlock]) -> str:
    """Serialize ContentBlock list to natural language for LLM context."""
    parts: list[str] = []
    for b in blocks:
        if b.type == "text":
            parts.append(b.content)
        elif b.type == "thinking":
            pass  # skip — don't feed internal thinking back to LLM
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


def _build_anthropic_messages(
    history: list[MessageInHistory],
    prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for msg in history:
        role = "user" if msg.role == "user" else "assistant"
        text = _blocks_to_text(msg.blocks)
        if msg.sender and role == "assistant":
            text = f"[{msg.sender}]: {text}"
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": prompt})
    return messages


def _build_system_prompt(base: str | None, skills: list) -> str:
    parts: list[str] = []
    if base:
        parts.append(base)
    for skill in skills:
        if skill.content:
            parts.append(f"\n---\n{skill.content}")
    return "\n".join(parts)


def _mcp_tool_to_anthropic(tool: MCPTool) -> dict[str, Any]:
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
