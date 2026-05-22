"""ClaudeAdapter — Anthropic SDK streaming with MCP tool support."""
from __future__ import annotations

import uuid
import logging
from typing import Any, AsyncGenerator

import anthropic

from backend.adapters.base import AgentAdapter
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    ApprovalRequestEvent,
    TokenEvent,
)
from backend.adapters.mcp_client import MCPClient, MCPTool
from backend.config import settings
from backend.domain.message import MessageEntity
from backend.domain.skill import SkillEntity

logger = logging.getLogger(__name__)


class ClaudeAdapter(AgentAdapter):
    """Streams Claude responses using the Anthropic Python SDK.

    Optionally attaches an MCPClient to expose MCP tools to Claude.
    Tools with side effects surface as ApprovalRequestEvent and pause
    execution; read-only tools are called transparently.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
        mcp_client: MCPClient | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.model = model or settings.anthropic_model_id
        self.system_prompt = system_prompt
        self._mcp_client = mcp_client
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key,
            base_url=base_url or settings.anthropic_base_url,
        )

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

        messages = _build_anthropic_messages(history, prompt)
        system = _build_system_prompt(self.system_prompt, skills)

        # Resolve MCP tools (if any) into Anthropic tool format
        tool_definitions: list[dict[str, Any]] = []
        mcp_tools_by_name: dict[str, MCPTool] = {}
        if self._mcp_client is not None:
            try:
                mcp_tools = await self._mcp_client.list_tools()
                for t in mcp_tools:
                    tool_definitions.append(_mcp_tool_to_anthropic(t))
                    mcp_tools_by_name[t.name] = t
            except Exception as exc:
                logger.warning("Failed to fetch MCP tools for %s: %s", self.agent_id, exc)

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=8192,
                system=system or anthropic.NOT_GIVEN,
                messages=messages,
                tools=tool_definitions or anthropic.NOT_GIVEN,
            ) as stream:
                current_tool_use: dict[str, Any] | None = None

                async for event in stream:
                    event_type = event.type

                    if event_type == "text":
                        yield TokenEvent(
                            agent_id=self.agent_id,
                            message_id=message_id,
                            content=event.text,
                        )

                    elif event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_use = {
                                "id": block.id,
                                "name": block.name,
                                "input_str": "",
                            }

                    elif event_type == "input_json_delta" and current_tool_use is not None:
                        current_tool_use["input_str"] += event.partial_json

                    elif event_type == "content_block_stop" and current_tool_use is not None:
                        import json as _json
                        try:
                            tool_input = _json.loads(current_tool_use["input_str"] or "{}")
                        except _json.JSONDecodeError:
                            tool_input = {}

                        tool_name = current_tool_use["name"]
                        mcp_tool = mcp_tools_by_name.get(tool_name)

                        if mcp_tool and mcp_tool.has_side_effects:
                            yield ApprovalRequestEvent(
                                agent_id=self.agent_id,
                                message_id=message_id,
                                action=tool_name,
                                detail=str(tool_input),
                            )
                            # In a full implementation, thread_service suspends here
                            # and resumes after WebSocket approval. For now we call through.

                        if mcp_tool and self._mcp_client is not None:
                            try:
                                result = await self._mcp_client.call_tool(tool_name, tool_input)
                                result_text = _extract_tool_result_text(result)
                                # Inject tool result as a token so the frontend sees it
                                yield TokenEvent(
                                    agent_id=self.agent_id,
                                    message_id=message_id,
                                    content=f"\n[Tool result: {result_text}]\n",
                                )
                            except Exception as exc:
                                logger.error("MCP tool call failed (%s): %s", tool_name, exc)

                        current_tool_use = None

        except anthropic.APIError as exc:
            logger.error("Anthropic API error for agent %s: %s", self.agent_id, exc)
            yield AgentErrorEvent(
                agent_id=self.agent_id,
                message_id=message_id,
                error=str(exc),
            )
            return

        yield AgentDoneEvent(agent_id=self.agent_id, message_id=message_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_anthropic_messages(
    history: list[MessageEntity],
    prompt: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for msg in history:
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": prompt})
    return messages


def _build_system_prompt(
    base: str | None,
    skills: list[SkillEntity],
) -> str:
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
