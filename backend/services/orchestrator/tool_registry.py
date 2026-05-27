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

import copy
import json
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
        schema = pydantic_to_json_schema(input_model)
        _validate_tool_schema(name, schema)
        TOOL_HANDLERS[name] = handler
        TOOL_SCHEMAS[name] = {
            "name": name,
            "description": description,
            "input_schema": schema,
        }
        return handler

    return _decorator


# ============================================================
# Pydantic → JSON Schema
# ============================================================

# 单次工具执行 output 序列化后的最大字节数。超出截断 + 补 "...truncated"
# 提示，避免单条 tool_result 撑爆 LLM context（Anthropic tools 单 response
# 内多条 tool_result 会全部进下轮 prompt）。
# 4KB 是经验值:典型工具输出几百字节,长 read_file 会超;真要读大文件应分批读。
_TOOL_RESULT_MAX_BYTES = 4 * 1024


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
    Anthropic 兼容 JSON Schema draft 2020-12,但**对 $ref + $defs 支持不稳定**:
    嵌套 BaseModel(如 CreateTaskPlanInput.plan: TaskPlan)会被拆成
    `{"$ref": "#/$defs/TaskPlan"}`,Anthropic 模型常常解析不出这是什么类型,
    工具入参直接乱填。所以这里必须把所有 $ref **inline 展开**成完整 schema 再发。

    展开后:
    1. 所有 $ref 替换为对应 $defs 条目的拷贝(递归展开,深嵌套也能处理)
    2. 顶层 $defs 键删掉(已被展开,不再需要)
    3. 各层 title 删掉(Anthropic 不需要,只增加 prompt 体积)
    """
    schema = model.model_json_schema()
    schema = _inline_refs(schema)
    schema.pop("$defs", None)
    _strip_titles(schema)
    return schema


def _inline_refs(node: Any, defs: Optional[dict[str, Any]] = None) -> Any:
    """
    递归展开 $ref。

    - 顶层调用时 defs=None,从 node["$defs"] 取定义表
    - 后续递归把 defs 透传
    - 遇到 {"$ref": "#/$defs/Name"} 节点 → 替换为 deepcopy(defs["Name"]) 后再
      递归展开(处理嵌套 $ref)
    - 其他 dict/list 递归

    用 deepcopy 避免同一定义被多处引用时,展开后改一处影响其他处。

    防御:
    - 不支持的 $ref 路径(非 #/$defs/...) 原样返回,记 warning
    - 防环:_visiting 集合记录展开中的 def name,自引用时返回原 $ref 不展开
    """
    if defs is None and isinstance(node, dict):
        defs = node.get("$defs", {}) or {}

    return _inline_refs_walk(node, defs or {}, _visiting=set(), _copy=copy.deepcopy)


def _inline_refs_walk(
    node: Any,
    defs: dict[str, Any],
    *,
    _visiting: set[str],
    _copy: Callable[[Any], Any],
) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            # 仅支持本文档内的 #/$defs/Name
            prefix = "#/$defs/"
            if not ref.startswith(prefix):
                logger.warning("不支持的 $ref 路径,原样保留: %s", ref)
                return node
            name = ref[len(prefix):]
            if name in _visiting:
                # 自引用(理论上 Pydantic 不该产生,但防御性保留)
                logger.warning("$ref 循环展开,保留原引用: %s", ref)
                return node
            target = defs.get(name)
            if target is None:
                logger.warning("$ref 找不到定义,原样保留: %s", ref)
                return node
            _visiting.add(name)
            try:
                expanded = _inline_refs_walk(_copy(target), defs, _visiting=_visiting, _copy=_copy)
            finally:
                _visiting.discard(name)
            return expanded

        # 普通 dict:递归各 value;跳过 $defs 键(已经在外层处理)
        return {
            k: _inline_refs_walk(v, defs, _visiting=_visiting, _copy=_copy)
            for k, v in node.items()
            if k != "$defs"
        }

    if isinstance(node, list):
        return [
            _inline_refs_walk(item, defs, _visiting=_visiting, _copy=_copy)
            for item in node
        ]

    return node


def _strip_titles(node: Any) -> None:
    """
    递归删 schema 各层的 title 字段。Anthropic 不需要 title,只占 token。
    in-place 修改,无返回值。
    """
    if isinstance(node, dict):
        node.pop("title", None)
        for v in node.values():
            _strip_titles(v)
    elif isinstance(node, list):
        for item in node:
            _strip_titles(item)


def _validate_tool_schema(name: str, schema: dict[str, Any]) -> None:
    """
    校验工具 schema 满足 Anthropic tool_use 协议:
    - 必须 type='object'
    - 必须含 properties(允许空 dict,无入参工具用)
    - 不允许残留 $ref 或 $defs(说明展开有 bug)

    出错时抛 ValueError。注册期失败,启动就炸,不让坏 schema 跑到生产。
    """
    if schema.get("type") != "object":
        raise ValueError(
            f"工具 {name} 的 input_schema.type 必须是 'object',实际: {schema.get('type')!r}"
        )
    if "properties" not in schema:
        raise ValueError(f"工具 {name} 的 input_schema 缺 properties 字段")
    leftovers = _find_unresolved_refs(schema)
    if leftovers:
        raise ValueError(
            f"工具 {name} 的 input_schema 含未展开的 $ref / $defs: {leftovers}"
        )


def _find_unresolved_refs(node: Any, _path: str = "") -> list[str]:
    """递归找 schema 里残留的 $ref / $defs 节点路径(用于错误诊断)。"""
    found: list[str] = []
    if isinstance(node, dict):
        if "$ref" in node:
            found.append(f"{_path}.$ref={node['$ref']}")
        if "$defs" in node:
            found.append(f"{_path}.$defs")
        for k, v in node.items():
            found.extend(_find_unresolved_refs(v, f"{_path}.{k}"))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_find_unresolved_refs(item, f"{_path}[{i}]"))
    return found


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

    长度截断:
    - 拼上 "...truncated" 后总字节不超过 _TOOL_RESULT_MAX_BYTES (硬上限)
    - 截断按 utf-8 安全切片(避免切坏多字节字符,errors='ignore' 兜底)
    - 截断时保留原 is_error 标志,不把成功结果偷偷标成 error
    """
    payload = json.dumps(result.output, ensure_ascii=False)
    encoded = payload.encode("utf-8")
    if len(encoded) > _TOOL_RESULT_MAX_BYTES:
        # 给后缀预留空间:截断目标 = 上限 - 后缀字节数,确保总长不超
        suffix = "...truncated"
        budget = _TOOL_RESULT_MAX_BYTES - len(suffix.encode("utf-8"))
        truncated_bytes = encoded[:budget]
        # utf-8 安全切片:errors='ignore' 丢掉切口处可能残缺的多字节字符
        payload = truncated_bytes.decode("utf-8", errors="ignore") + suffix
        logger.warning(
            "tool_result %s 输出超 %d 字节,已截断 (原长 %d)",
            result.name,
            _TOOL_RESULT_MAX_BYTES,
            len(encoded),
        )
    return {
        "type": "tool_result",
        "tool_use_id": result.tool_use_id,
        "content": payload,
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
