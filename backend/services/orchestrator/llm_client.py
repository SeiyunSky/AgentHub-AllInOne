"""
OrchestratorLLMClient —— 主 Agent 专用 LLM 客户端

封装 anthropic SDK,只暴露主 Agent loop 需要的能力:
  chat_completion(system, messages, tools) → 一次调用,拿 stop_reason / content / tool_calls
  主 Agent 内部调 LLM 的输出不经 stream_service 广播给前端
  主 Agent 思考过程对用户不可见

走 Anthropic 兼容协议(配置见 settings.EXTERNAL_API_BASE / KEY / MODEL),
当前指向 Moonshot Kimi 的 /anthropic 端点。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from backend.config import settings


logger = logging.getLogger(__name__)


@dataclass
class LLMToolCall:
    """LLM 输出的一次工具调用"""
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResponse:
    """LLM 单次调用的返回"""
    stop_reason: str  # "end_turn" / "tool_use" / "max_tokens" / "stop_sequence" 等
    content_text: Optional[str] = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tokens_input: int = 0
    tokens_output: int = 0


class OrchestratorLLMClient:
    """主 Agent 专用 LLM 客户端,只服务 orchestrator/service.py"""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        # 默认从 settings 读,显式参数优先(测试 / 多租户场景下覆盖)
        self._api_key = api_key or settings.EXTERNAL_API_KEY
        self._base_url = base_url or settings.EXTERNAL_API_BASE
        self._model = model or settings.EXTERNAL_MODEL
        self._client = anthropic.AsyncAnthropic(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    async def chat_completion(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 16000,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        一次 LLM 调用。

        - system: 已组装的 System Prompt(六层管道结果)
        - messages: 对话历史 + 当前轮 user 消息(含工具结果回传)
        - tools: orchestrator 19 个工具的 schema(JSON Schema 形态,Anthropic tool_use 协议)

        返回 LLMResponse:
        - stop_reason: end_turn / tool_use / max_tokens / stop_sequence
        - content_text: 所有 text block 内容拼接(无 text block 时为 None)
        - tool_calls: 所有 tool_use block 解析后的 LLMToolCall 列表
        - tokens_input / tokens_output: 计费 / 上下文管理用

        注意:
        - 不流式(messages.create 而非 messages.stream),主 Agent loop 每轮需要完整结果
        - 抛 anthropic.APIError 由调用方(orchestrator service / error_recovery)处理
        """
        try:
            response = await self._client.messages.create(
                model=model or self._model,
                max_tokens=max_tokens,
                # 空字符串 / 空列表都走 NOT_GIVEN(不下发该字段)。
                # 显式 if/else 比 `x or NOT_GIVEN` 可读性更好——后者依赖 truthiness 心算。
                system=system if system else anthropic.NOT_GIVEN,
                messages=messages,
                tools=tools if tools else anthropic.NOT_GIVEN,
            )
        except anthropic.APIError:
            # 让上层 error_recovery 决策(重试 / 降级)
            raise

        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: Any) -> LLMResponse:
        """
        把 anthropic.types.Message 解析成 LLMResponse。

        Anthropic Messages API 返回结构:
        - response.stop_reason: "end_turn" / "tool_use" / "max_tokens" / "stop_sequence"
        - response.content: list[ContentBlock] —— 可能多个 text 块和 tool_use 块混排
        - response.usage.input_tokens / output_tokens
        """
        text_parts: list[str] = []
        tool_calls: list[LLMToolCall] = []

        for block in response.content or []:
            btype = getattr(block, "type", None)
            if btype == "text":
                text = getattr(block, "text", "")
                if text:
                    text_parts.append(text)
            elif btype == "tool_use":
                tool_calls.append(
                    LLMToolCall(
                        id=block.id,
                        name=block.name,
                        input=dict(block.input or {}),
                    )
                )

        usage = getattr(response, "usage", None)
        tokens_input = getattr(usage, "input_tokens", 0) if usage else 0
        tokens_output = getattr(usage, "output_tokens", 0) if usage else 0

        return LLMResponse(
            stop_reason=response.stop_reason or "end_turn",
            content_text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )


llm_client = OrchestratorLLMClient()
