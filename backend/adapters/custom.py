"""CustomAdapter — OpenAI-compatible API streaming with MCP tool support.

Works with any OpenAI-compatible endpoint: OpenAI, Ollama, vLLM, Together, etc.

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-25
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import openai

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
from backend.domain.message import ApprovalBlock, ContentBlock, TextBlock, ToolUseBlock
from backend.schemas.message import MessageInHistory

logger = logging.getLogger(__name__)


class CustomAdapter(AgentAdapter):
    """Streams responses from any OpenAI-compatible API endpoint.

    Supports custom base_url for Ollama, vLLM, Together, Groq, etc.
    Optionally attaches an MCPClient to expose MCP tools.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        mcp_clients: list[MCPClient] | None = None,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL_ID", "gpt-4o")
        self._mcp_clients = mcp_clients or []
        self._client = openai.AsyncOpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or "sk-placeholder",
            base_url=base_url or os.environ.get("OPENAI_BASE_URL") or None,
        )

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=True,
            supports_diff=True,
            supports_approval=bool(self._mcp_clients),
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        yield AgentStartEvent(
            agent_id=inp.agent_id,
            thread_id=inp.thread_id,
            message_id=inp.message_id,
            agent_name=inp.agent_name or inp.agent_id,
            agent_avatar=inp.agent_avatar,
        )

        messages = _build_openai_messages(inp.system_prompt, inp.skills, inp.history, inp.prompt)

        tool_definitions: list[dict[str, Any]] = []
        mcp_tools_by_name: dict[str, MCPTool] = {}
        for mcp_client in self._mcp_clients:
            try:
                mcp_tools = await mcp_client.list_tools()
                for t in mcp_tools:
                    tool_definitions.append(_mcp_tool_to_openai(t))
                    mcp_tools_by_name[t.name] = t
            except Exception as exc:
                logger.warning("Failed to fetch MCP tools from %s for %s: %s", mcp_client.server_id, inp.agent_id, exc)

        def _base() -> dict[str, str]:
            return {"agent_id": inp.agent_id, "thread_id": inp.thread_id, "message_id": inp.message_id}

        try:
            pending_tool_calls: dict[int, dict[str, Any]] = {}
            text_block_id: str | None = None

            create_kwargs: dict[str, Any] = dict(
                model=self.model,
                messages=messages,
                stream=True,
            )
            if tool_definitions:
                create_kwargs["tools"] = tool_definitions
                create_kwargs["tool_choice"] = "auto"

            sdk_stream = await self._client.chat.completions.create(**create_kwargs)

            async for chunk in sdk_stream:
                if inp.cancel_event and inp.cancel_event.is_set():
                    yield AgentErrorEvent(**_base(), error="cancelled")
                    return

                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                if delta.content:
                    if text_block_id is None:
                        text_block_id = gen_uuid()
                        yield BlockStartEvent(
                            **_base(),
                            block=TextBlock(block_id=text_block_id, content=""),
                        )
                    yield BlockDeltaEvent(
                        **_base(),
                        block_id=text_block_id,
                        delta={"content": delta.content},
                    )

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {"id": "", "name": "", "args_str": ""}
                        entry = pending_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["args_str"] += tc_delta.function.arguments

                finish_reason = chunk.choices[0].finish_reason

                if finish_reason == "stop" and text_block_id is not None:
                    yield BlockStopEvent(**_base(), block_id=text_block_id)
                    text_block_id = None

                if finish_reason == "tool_calls":
                    # Close any open text block first
                    if text_block_id is not None:
                        yield BlockStopEvent(**_base(), block_id=text_block_id)
                        text_block_id = None

                    for entry in pending_tool_calls.values():
                        tool_name = entry["name"]
                        try:
                            tool_input = json.loads(entry["args_str"] or "{}")
                        except json.JSONDecodeError:
                            tool_input = {}

                        mcp_tool = mcp_tools_by_name.get(tool_name)
                        tool_bid = gen_uuid()

                        if mcp_tool and mcp_tool.has_side_effects:
                            approval_bid = gen_uuid()
                            yield BlockStartEvent(
                                **_base(),
                                block=ApprovalBlock(
                                    block_id=approval_bid,
                                    action=tool_name,
                                    detail=str(tool_input),
                                    status="pending",
                                ),
                            )
                            yield BlockStopEvent(
                                **_base(),
                                block_id=approval_bid,
                                final_fields={"status": "approved"},
                            )

                        yield BlockStartEvent(
                            **_base(),
                            block=ToolUseBlock(block_id=tool_bid, tool_name=tool_name, status="running"),
                        )

                        result_text: str | None = None
                        if mcp_tool:
                            # 找到注册了该工具的 MCPClient
                            owning_client: MCPClient | None = None
                            for c in self._mcp_clients:
                                try:
                                    tools = await c.list_tools()
                                    if any(t.name == tool_name for t in tools):
                                        owning_client = c
                                        break
                                except Exception:
                                    pass
                            if owning_client is not None:
                                try:
                                    result = await owning_client.call_tool(tool_name, tool_input)
                                    result_text = _extract_tool_result_text(result)
                                except Exception as exc:
                                    logger.error("MCP tool call failed (%s): %s", tool_name, exc)
                                    result_text = f"error: {exc}"

                        yield BlockStopEvent(
                            **_base(),
                            block_id=tool_bid,
                            final_fields={
                                "input": tool_input,
                                "output": result_text,
                                "status": "completed" if result_text is not None else "error",
                            },
                        )

                    pending_tool_calls.clear()

            # Close text block if stream ended without finish_reason="stop"
            if text_block_id is not None:
                yield BlockStopEvent(**_base(), block_id=text_block_id)

        except openai.APIError as exc:
            logger.error("OpenAI API error for agent %s: %s", inp.agent_id, exc)
            yield AgentErrorEvent(**_base(), error=str(exc))
            return

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


def _build_openai_messages(
    system_prompt: str | None,
    skills: list,
    history: list[MessageInHistory],
    prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    system_parts: list[str] = []
    if system_prompt:
        system_parts.append(system_prompt)
    for skill in skills:
        if skill.content:
            system_parts.append(f"\n---\n{skill.content}")
    if system_parts:
        messages.append({"role": "system", "content": "\n".join(system_parts)})

    for msg in history:
        role = "user" if msg.role == "user" else "assistant"
        text = _blocks_to_text(msg.blocks)
        if msg.sender and role == "assistant":
            text = f"[{msg.sender}]: {text}"
        if text:
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": prompt})
    return messages


def _mcp_tool_to_openai(tool: MCPTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


def _extract_tool_result_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)
    return str(result)
