"""
ToolRegistry —— 主 Agent 工具协议适配层

职责:
- 把主 Agent 的 Pydantic Input Schema 转成 Anthropic tool_use 协议要的 JSON Schema
- 维护 TOOL_HANDLERS 注册表 (tool_name → async handler)
- 把 LLM 的 tool_use 输出转成 handler 调用,handler 输出再包成 tool_result block
- 提供 LLMResponse 解析助手 (结束条件判断 / tool_use 抽取)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel

from backend.services.orchestrator.llm_client import LLMResponse, LLMToolCall


logger = logging.getLogger(__name__)


# ============================================================
# 类型别名
# ============================================================

# 工具 handler 签名:接收解析后的 input dict + 上下文(thread_id / conversation_id 等),
# 返回 dict (会被 json 序列化进 tool_result.content)
ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


# ============================================================
# 注册表 (模块级全局)
# ============================================================
# TOOL_HANDLERS: tool_name → handler
# TOOL_SCHEMAS: tool_name → 已转好的 JSON Schema (Anthropic tools list 用)
# orchestrator_tools.py import 完成后,这两份表就完整了。
# 主 Agent loop 启动时调 build_tools_payload() 拿 tools 列表给 LLM。

TOOL_HANDLERS: dict[str, ToolHandler] = {}
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {}


# ============================================================
# 注册装饰器 / 函数
# ============================================================

def register_tool(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
) -> Callable[[ToolHandler], ToolHandler]:
    """
    注册一个工具到 TOOL_HANDLERS / TOOL_SCHEMAS。
    用作装饰器:

        @register_tool(name="dispatch_to_agent", description="...", input_model=DispatchInput)
        async def dispatch_to_agent(tool_input: dict, *, ctx: ToolContext) -> dict:
            ...

    - name 必须在工具命名内,重复注册抛 ValueError
    - description 是给 LLM 看的工具说明(写清楚什么时候该用)
    - input_model 是 Pydantic BaseModel,内部转 JSON Schema

    TODO[F-registry-1]: 校验 input_model.model_validate(input) 后再喂给 handler,
    现在 handler 自己解析。
    """

    def _decorator(handler: ToolHandler) -> ToolHandler:
        if name in TOOL_HANDLERS:
            raise ValueError(f"重复注册工具: {name}")
        TOOL_HANDLERS[name] = handler
        TOOL_SCHEMAS[name] = {
            "name": name,
            "description": description,
            "input_schema": pydantic_to_json_schema(input_model),
        }
        return handler

    return _decorator


# ============================================================
# Pydantic → JSON Schema
# ============================================================

def pydantic_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """
    把 Pydantic BaseModel 转成 Anthropic tool_use 协议要求的 input_schema。

    Anthropic 要的形态(参考官方文档):
        {
            "type": "object",
            "properties": {...},
            "required": [...]
        }

    Pydantic v2 model.model_json_schema() 自带这三个键 + $defs 等 OpenAPI 扩展。
    Anthropic 兼容 JSON Schema draft 2020-12,直接透传基本能用。

    TODO[F-registry-2]: 处理嵌套 BaseModel ($defs 展开 / $ref 解引用),
    Anthropic 对 $ref 支持有限,复杂嵌套时要 inline。MVP 阶段先简单透传,
    工具 input 都尽量扁平化。
    """
    schema = model.model_json_schema()
    # 去掉 Pydantic 加的 title 字段(Anthropic 不需要,会增加 prompt 体积)
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        if isinstance(prop, dict):
            prop.pop("title", None)
    return schema


# ============================================================
# 给 LLM 的 tools payload
# ============================================================

def build_tools_payload() -> list[dict[str, Any]]:
    """
    返回 anthropic.messages.create(tools=...) 直接吃的 tools 列表。
    主 Agent loop 每次调 LLM 时传这个。
    """
    return list(TOOL_SCHEMAS.values())


# ============================================================
# Tool 调用上下文
# ============================================================

@dataclass
class ToolContext:
    """
    handler 执行时的上下文。orchestrator service 在 dispatch_tool_call 时填好。

    - thread_id: 当前主 Agent 的 thread_id (read_thread_status 等工具会反查到自己 / 子 Thread)
    - conversation_id: 当前会话
    - user_message_id: 触发本轮的用户消息 id (派子 Thread 时用)
    - user_id: 发起人 (审批 / 权限校验用)
    """
    thread_id: str
    conversation_id: str
    user_message_id: str
    user_id: str


# ============================================================
# 派发 tool_use → handler
# ============================================================

@dataclass
class ToolResult:
    """单次工具执行结果。orchestrator loop 把这个包成 tool_result block 回传 LLM。"""
    tool_use_id: str
    name: str
    output: dict[str, Any]
    is_error: bool = False


async def dispatch_tool_call(
    call: LLMToolCall,
    *,
    ctx: ToolContext,
) -> ToolResult:
    """
    把 LLM 的一次 tool_use 输出 (LLMToolCall) 派给对应 handler,捕获异常包成 is_error。

    - 未注册的 tool_name → is_error=True,output={"error": "..."}
    - handler 抛异常 → is_error=True,output={"error": str(exc)},日志 exception
    - 正常返回 → is_error=False,output=handler 返回的 dict

    TODO[F-registry-3]: handler 调用前用 input_model.model_validate(call.input) 校验,
    校验失败也走 is_error 分支。
    """
    handler = TOOL_HANDLERS.get(call.name)
    if handler is None:
        logger.warning("未注册的工具: %s", call.name)
        return ToolResult(
            tool_use_id=call.id,
            name=call.name,
            output={"error": f"未注册的工具: {call.name}"},
            is_error=True,
        )
    try:
        output = await handler(call.input, ctx=ctx)
        return ToolResult(
            tool_use_id=call.id,
            name=call.name,
            output=output,
            is_error=False,
        )
    except Exception as exc:
        logger.exception("工具 %s 执行失败", call.name)
        return ToolResult(
            tool_use_id=call.id,
            name=call.name,
            output={"error": str(exc)},
            is_error=True,
        )


# ============================================================
# tool_result 包装(回传 LLM)
# ============================================================

def wrap_tool_result(result: ToolResult) -> dict[str, Any]:
    """
    把 ToolResult 包成 Anthropic messages 协议要的 tool_result content block。

    协议形态:
        {
            "type": "tool_result",
            "tool_use_id": "...",
            "content": "<json string>",
            "is_error": false
        }

    content 用 json 序列化的字符串(Anthropic 也支持 list[{"type":"text","text":...}],
    MVP 先用最简形态)。

    TODO[F-registry-4]: 长 output (> 4KB) 截断 + 补 "...truncated" 提示,
    避免单次 tool_result 把 context 撑爆。
    """
    import json
    return {
        "type": "tool_result",
        "tool_use_id": result.tool_use_id,
        "content": json.dumps(result.output, ensure_ascii=False),
        "is_error": result.is_error,
    }


# ============================================================
# LLMResponse 解析助手
# ============================================================

def is_terminal_stop_reason(response: LLMResponse) -> bool:
    """
    判断 LLM 输出是否表示"本轮主 Agent 思考结束"。
    - end_turn: 主 Agent 主动结束
    - stop_sequence: 命中停止符
    其他(tool_use / max_tokens)都还要继续 loop。
    """
    return response.stop_reason in {"end_turn", "stop_sequence"}


def has_tool_calls(response: LLMResponse) -> bool:
    """有未处理的工具调用 → loop 继续(执行工具 → 回灌 → 再调 LLM)。"""
    return bool(response.tool_calls)


def needs_recovery(response: LLMResponse) -> Optional[str]:
    """
    判断是否需要走 error_recovery:
    - max_tokens: 输出被截断,需要 micro_compact 后续接
    返回需要处理的 stop_reason,或 None。
    """
    if response.stop_reason == "max_tokens":
        return "max_tokens"
    return None


# ============================================================
# 注册触发 (orchestrator_tools.py 实装时 import 即注册)
# ============================================================
# 模式: orchestrator_tools.py 内每个 handler 用 @register_tool 装饰,
# orchestrator/service.py 启动时 import orchestrator_tools 触发注册。
#
# 这里不做 import,避免循环依赖:
#   orchestrator_tools → tool_registry (拿 register_tool)
#   service → orchestrator_tools (触发注册) → tool_registry
#
# TODO[F-registry-5]: orchestrator_tools 实装后,在 service.py 顶部加
#   `import backend.services.orchestrator_tools  # noqa: F401`
#   或在 OrchestratorService.__init__ 里 lazy import。
