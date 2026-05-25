"""
orchestrator 子模块统一导出。

外部代码通过 `from backend.services.orchestrator import orchestrator_service` 使用,
chat_service 已通过 `from backend.services.orchestrator_service import ...` 引用,
为保证兼容,暴露一个同名常量。
"""

from backend.services.orchestrator.context_compactor import context_compactor
from backend.services.orchestrator.error_recovery import error_recovery
from backend.services.orchestrator.llm_client import llm_client
from backend.services.orchestrator.prompt_builder import prompt_builder
from backend.services.orchestrator.service import (
    OrchestratorService,
    orchestrator_service,
)
from backend.services.orchestrator.tool_registry import (
    TOOL_HANDLERS,
    TOOL_SCHEMAS,
    ToolContext,
    ToolResult,
    build_tools_payload,
    dispatch_tool_call,
    register_tool,
    wrap_tool_result,
)

__all__ = [
    "OrchestratorService",
    "orchestrator_service",
    "llm_client",
    "prompt_builder",
    "error_recovery",
    "context_compactor",
    # tool_registry
    "TOOL_HANDLERS",
    "TOOL_SCHEMAS",
    "ToolContext",
    "ToolResult",
    "register_tool",
    "build_tools_payload",
    "dispatch_tool_call",
    "wrap_tool_result",
]
