"""A2AAdapter — calls a remote A2A-protocol agent and streams the response.

Connects to any agent that implements the A2A JSON-RPC protocol
(e.g. poc-margin-analysis-agent running on localhost:9000).

The agent's response is expected to be a JSON object with:
  - message: str (markdown text)
  - suggested_drilldowns: list[str] (optional quick-reply buttons)
  - chart_info: dict | None (optional chart data)

All fields are rendered as text blocks in AgentHub.

队伍：咕嘎一辈子队
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

import httpx

from backend.adapters.base import AgentAdapter, StreamInput
from backend.adapters.events import (
    AgentDoneEvent,
    AgentErrorEvent,
    AgentEvent,
    AgentStartEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.core.utils import gen_uuid
from backend.domain.agent import AgentCapabilities
from backend.domain.message import TextBlock

logger = logging.getLogger(__name__)


class A2AAdapter(AgentAdapter):
    """Calls a remote A2A agent and streams its response as text blocks."""

    def __init__(self, base_url: str) -> None:
        # e.g. "http://localhost:9000"
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            supports_code=False,
            supports_diff=False,
            supports_approval=False,
        )

    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:  # type: ignore[override]
        def _base() -> dict:
            return {
                "agent_id": inp.agent_id,
                "thread_id": inp.thread_id,
                "message_id": inp.message_id,
            }

        yield AgentStartEvent(
            **_base(),
            agent_name=inp.agent_name or inp.agent_id,
            agent_avatar=inp.agent_avatar,
        )

        # Build A2A JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid.uuid4()),
            "params": {
                "message": {
                    "messageId": gen_uuid(),
                    "role": "user",
                    "parts": [{"kind": "text", "text": inp.prompt}],
                    "contextId": inp.thread_id,
                }
            },
        }

        try:
            response = await self._client.post(
                f"{self._base_url}/",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            rpc_result = response.json()
        except Exception as exc:
            logger.error("A2AAdapter: request failed for agent %s: %s", inp.agent_id, exc)
            yield AgentErrorEvent(**_base(), error=f"Failed to reach agent: {exc}")
            return

        # Extract artifact data from A2A response
        try:
            task = rpc_result.get("result", {})
            artifacts = task.get("artifacts", [])
            if not artifacts:
                yield AgentErrorEvent(**_base(), error="Agent returned no artifacts")
                return

            part = artifacts[0]["parts"][0]
            # A2A agents can return either "data" (structured JSON) or "text"
            raw = part.get("data") or part.get("text") or {}
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"message": raw}
            else:
                data = raw

        except (KeyError, IndexError, TypeError) as exc:
            logger.error("A2AAdapter: failed to parse response for agent %s: %s", inp.agent_id, exc)
            yield AgentErrorEvent(**_base(), error=f"Failed to parse agent response: {exc}")
            return

        # --- Emit main text block ---
        message_text = data.get("message", "")
        if message_text:
            block_id = gen_uuid()
            yield BlockStartEvent(
                **_base(),
                block=TextBlock(block_id=block_id, content=message_text),
            )
            yield BlockStopEvent(**_base(), block_id=block_id)

        # --- Emit chart_info as a formatted text block ---
        chart_info = data.get("chart_info")
        if chart_info:
            chart_text = _format_chart_as_text(chart_info)
            block_id = gen_uuid()
            yield BlockStartEvent(
                **_base(),
                block=TextBlock(block_id=block_id, content=chart_text),
            )
            yield BlockStopEvent(**_base(), block_id=block_id)

        # --- Emit suggested drilldowns as a text block ---
        drilldowns = data.get("suggested_drilldowns", [])
        if drilldowns:
            drilldown_text = "**Suggested next steps:**\n" + "\n".join(
                f"- {d}" for d in drilldowns
            )
            block_id = gen_uuid()
            yield BlockStartEvent(
                **_base(),
                block=TextBlock(block_id=block_id, content=drilldown_text),
            )
            yield BlockStopEvent(**_base(), block_id=block_id)

        yield AgentDoneEvent(**_base())


def _format_chart_as_text(chart_info: dict) -> str:
    """Render chart_info as a readable markdown table."""
    chart_type = chart_info.get("chart_type", "chart")
    title = chart_info.get("title", "")
    description = chart_info.get("description", "")
    unit = chart_info.get("unit", "")
    dimensions = chart_info.get("dimensions", [])
    measures = chart_info.get("measures", [])
    results = chart_info.get("results", [])

    lines = [f"**📊 {title}** ({chart_type})"]
    if description:
        lines.append(f"_{description}_")
    if unit:
        lines.append(f"Unit: {unit}")
    lines.append("")

    if not results:
        return "\n".join(lines)

    # Build markdown table
    dim_props = [d["Property"] for d in dimensions]
    mea_props = [m["Property"] for m in measures]
    dim_labels = [d["Description"] for d in dimensions]
    mea_labels = [m["Description"] for m in measures]

    headers = dim_labels + mea_labels
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in results:
        cells = []
        for prop in dim_props:
            cells.append(str(row.get(prop, "")))
        for prop in mea_props:
            val = row.get(prop, "")
            cells.append(f"{val:.1f}" if isinstance(val, float) else str(val))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)
