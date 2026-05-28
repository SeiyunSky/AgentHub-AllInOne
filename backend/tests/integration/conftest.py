"""
orchestrator loop 集成测试 fixture

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.hooks.manager import hook_manager
from backend.services.orchestrator.llm_client import LLMResponse, LLMToolCall
from backend.services.orchestrator.tool_registry import (
    TOOL_HANDLERS,
    TOOL_SCHEMAS,
    ToolContext,
)


# ============================================================
# LLMResponse 队列
# ============================================================

@pytest.fixture
def llm_response_queue(monkeypatch):
    """mock chat_completion,按队列依次返回 LLMResponse。队列空时抛异常,避免测试静默挂起。"""
    queue: list[LLMResponse] = []

    async def _fake_chat_completion(
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 16000,
        model: Optional[str] = None,
    ) -> LLMResponse:
        if not queue:
            raise RuntimeError("llm_response_queue 已耗尽")
        return queue.pop(0)

    from backend.services.orchestrator.llm_client import llm_client as _llm_singleton
    monkeypatch.setattr(_llm_singleton, "chat_completion", _fake_chat_completion)

    return queue


@pytest.fixture
def llm_exception_queue(monkeypatch):
    """队列元素可为 Exception(抛)或 LLMResponse(返)。用于测 error_recovery 三路。"""
    queue: list[Any] = []

    async def _fake_chat_completion(**kwargs) -> LLMResponse:
        if not queue:
            raise RuntimeError("llm_exception_queue 已耗尽")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    from backend.services.orchestrator.llm_client import llm_client as _llm_singleton
    monkeypatch.setattr(_llm_singleton, "chat_completion", _fake_chat_completion)

    return queue


# ============================================================
# LLMResponse 构造助手
# ============================================================

def make_text_response(text: str = "ok", tokens_in: int = 100, tokens_out: int = 50) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        content_text=text,
        tool_calls=[],
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )


def make_tool_use_response(
    tool_calls: list[tuple[str, str, dict]],
    text: Optional[str] = None,
    tokens_in: int = 100,
    tokens_out: int = 50,
) -> LLMResponse:
    """tool_calls: list of (id, name, input_dict)"""
    return LLMResponse(
        stop_reason="tool_use",
        content_text=text,
        tool_calls=[
            LLMToolCall(id=tid, name=tname, input=tinput)
            for tid, tname, tinput in tool_calls
        ],
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )


def make_max_tokens_response(text: Optional[str] = None) -> LLMResponse:
    return LLMResponse(
        stop_reason="max_tokens",
        content_text=text,
        tool_calls=[],
        tokens_input=100,
        tokens_output=16000,
    )


# ============================================================
# tool handler 临时注册
# ============================================================

@pytest.fixture
def temp_tool():
    """注册测试用 handler 到 TOOL_HANDLERS,测完自动清理。"""
    registered: list[str] = []

    def _register(name: str, handler, schema: Optional[dict] = None) -> None:
        if name in TOOL_HANDLERS:
            raise ValueError(f"工具 {name!r} 已存在,测试不能覆盖生产工具")
        TOOL_HANDLERS[name] = handler
        TOOL_SCHEMAS[name] = schema or {
            "name": name,
            "description": f"test tool {name}",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
        registered.append(name)

    yield _register

    for name in registered:
        TOOL_HANDLERS.pop(name, None)
        TOOL_SCHEMAS.pop(name, None)


# ============================================================
# 模块级全局状态自动清理
# ============================================================

@pytest.fixture(autouse=True)
def clean_hook_manager():
    yield
    hook_manager.clear()


@pytest.fixture(autouse=True)
def clean_orchestrator_state():
    """清 thread_service 模块级:_listeners / _pending_events / _running_tasks。"""
    from backend.services import thread_service as _ts_module

    yield

    _ts_module._listeners.clear()
    _ts_module._pending_events.clear()
    for task in list(_ts_module._running_tasks.values()):
        if not task.done():
            task.cancel()
    _ts_module._running_tasks.clear()


# ============================================================
# _agent_loop 入参模板
# ============================================================

@pytest.fixture
def loop_kwargs():
    """session 用 MagicMock —— _agent_loop 只用 session.expire_all() 和 ThreadService(session),
    后者也会被 patch_no_unfinished_children 拦掉。"""
    return {
        "thread_id": "test-orch-thread-1",
        "conversation_id": "test-conv-1",
        "user_message_id": "test-msg-1",
        "user_id": "test-user-1",
        "wake_event": asyncio.Event(),
        "session": MagicMock(),
    }


# ============================================================
# 子系统 stub
# ============================================================

@pytest.fixture
def patch_prompt_builder(monkeypatch):
    from backend.services.orchestrator import service as _service_module

    async def _stub_static(ctx):
        return "[test-static-prompt]"

    async def _stub_dynamic(ctx):
        return "[test-dynamic-prompt]"

    monkeypatch.setattr(_service_module.prompt_builder, "build_static", _stub_static)
    monkeypatch.setattr(_service_module.prompt_builder, "build_dynamic", _stub_dynamic)


@pytest.fixture
def patch_compactor_noop(monkeypatch):
    from backend.services.orchestrator import service as _service_module

    async def _noop(messages):
        return list(messages)

    monkeypatch.setattr(_service_module.context_compactor, "maybe_compact", _noop)


@pytest.fixture
def patch_no_unfinished_children(monkeypatch):
    """默认无未完成子 Thread。测 wake 路径的用例自行覆盖。"""
    from backend.services.orchestrator.service import OrchestratorService

    monkeypatch.setattr(
        OrchestratorService,
        "_has_unfinished_children",
        lambda self, session, conv_id, orch_id: False,
    )


@pytest.fixture
def patch_tools_payload_empty(monkeypatch):
    """避免把真实 19 个工具 schema 塞进 LLM 入参,保持测试参数干净。"""
    from backend.services.orchestrator import service as _service_module

    monkeypatch.setattr(
        _service_module,
        "build_tools_payload",
        lambda: [],
    )


@pytest.fixture
def orch_loop_env(
    patch_prompt_builder,
    patch_compactor_noop,
    patch_no_unfinished_children,
    patch_tools_payload_empty,
):
    """复合 fixture:apply 上面四个 patch。"""
    return None
