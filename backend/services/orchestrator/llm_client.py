"""
OrchestratorLLMClient —— 主 Agent 专用 LLM 客户端

封装 anthropic SDK,只暴露主 Agent loop 需要的能力:
- chat_completion(system, messages, tools) → 一次调用,拿 stop_reason / content / tool_calls
- 不实现 AgentAdapter 接口(主 Agent 不是被派活的,不该套子 Agent 接口)
- 主 Agent 内部调 LLM 的输出**不**经 stream_service 广播给前端
  (前端只看子 Adapter 输出,主 Agent 思考过程对用户不可见)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from dataclasses import dataclass, field
from typing import Any, Optional


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

    async def chat_completion(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 8000,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        一次 LLM 调用。

        - system: 已组装的 System Prompt(六层管道结果)
        - messages: 对话历史 + 当前轮 user 消息(含工具结果回传)
        - tools: orchestrator 19 个工具的 schema(JSON Schema 形态,Anthropic tool_use 协议)

        TODO[F-llm]: 接 anthropic SDK 实装。MVP 先支持 anthropic Messages API,
        后续按需扩展 OpenAI 兼容入口。
        """
        raise NotImplementedError(
            "[TODO/F-llm] OrchestratorLLMClient.chat_completion 未实装,"
            "需接 anthropic.AsyncAnthropic.messages.create"
        )


llm_client = OrchestratorLLMClient()
