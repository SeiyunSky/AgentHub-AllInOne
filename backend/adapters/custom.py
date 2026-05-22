"""CustomAdapter — OpenAI-compatible API streaming with MCP tool support.

Works with any OpenAI-compatible endpoint: OpenAI, Ollama, vLLM, Together, etc.
"""
from __future__ import annotations

import json
import uuid
import logging
from typing import Any, AsyncGenerator

import openai

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


class CustomAdapter(AgentAdapter):
    """Streams responses from any OpenAI-compatible API endpoint.

    Supports custom base_url for Ollama, vLLM, Together, Groq, etc.
    Optionally attaches an MCPClient to expose MCP tools.
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
        self.model = model or settings.openai_model_id
        self.system_prompt = system_prompt
        self._mcp_client = mcp_client
        self._client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key or "sk-placeholder",
            base_url=base_url or settings.openai_base_url,
        )

    def get_capabilities(self) -> dict[str, bool]:
        return {
            "supports_diff": True,
            "supports_approval": self._mcp_client is not None,
        }

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

        messages = _build_openai_messages(self.system_prompt, skills, history, prompt)

        tool_definitions: list[dict[str, Any]] = []
        mcp_tools_by_name: dict[str, MCPTool] = {}
        if self._mcp_client is not None:
            try:
                mcp_tools = await self._mcp_client.list_tools()
                for t in mcp_tools:
                    tool_definitions.append(_mcp_tool_to_openai(t))
                    mcp_tools_by_name[t.name] = t
            except Exception as exc:
                logger.warning("Failed to fetch MCP tools for %s: %s", self.agent_id, exc)

        try:
            # Collect tool calls during streaming (delta accumulation)
            pending_tool_calls: dict[int, dict[str, Any]] = {}

            create_kwargs: dict[str, Any] = dict(
                model=self.model,
                messages=messages,
                stream=True,
            )
            if tool_definitions:
                create_kwargs["tools"] = tool_definitions
                create_kwargs["tool_choice"] = "auto"

            stream = await self._client.chat.completions.create(**create_kwargs)

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Text token
                if delta.content:
                    yield TokenEvent(
                        agent_id=self.agent_id,
                        message_id=message_id,
                        content=delta.content,
                    )

                # Tool call delta accumulation
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "args_str": "",
                            }
                        entry = pending_tool_calls[idx]
                        if tc_delta.id:
                            entry["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                entry["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                entry["args_str"] += tc_delta.function.arguments

                finish_reason = chunk.choices[0].finish_reason
                if finish_reason == "tool_calls":
                    for entry in pending_tool_calls.values():
                        tool_name = entry["name"]
                        try:
                            tool_input = json.loads(entry["args_str"] or "{}")
                        except json.JSONDecodeError:
                            tool_input = {}

                        mcp_tool = mcp_tools_by_name.get(tool_name)

                        if mcp_tool and mcp_tool.has_side_effects:
                            yield ApprovalRequestEvent(
                                agent_id=self.agent_id,
                                message_id=message_id,
                                action=tool_name,
                                detail=str(tool_input),
                            )

                        if mcp_tool and self._mcp_client is not None:
                            try:
                                result = await self._mcp_client.call_tool(tool_name, tool_input)
                                result_text = _extract_tool_result_text(result)
                                yield TokenEvent(
                                    agent_id=self.agent_id,
                                    message_id=message_id,
                                    content=f"\n[Tool result: {result_text}]\n",
                                )
                            except Exception as exc:
                                logger.error("MCP tool call failed (%s): %s", tool_name, exc)

                    pending_tool_calls.clear()

        except openai.APIError as exc:
            logger.error("OpenAI API error for agent %s: %s", self.agent_id, exc)
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

def _build_openai_messages(
    system_prompt: str | None,
    skills: list[SkillEntity],
    history: list[MessageEntity],
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
        messages.append({"role": role, "content": msg.content})
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
