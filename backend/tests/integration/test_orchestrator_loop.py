"""
orchestrator _agent_loop 八步循环测试

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import asyncio
from typing import Any

import anthropic
import pytest

from backend.services.orchestrator.service import OrchestratorService
from backend.tests.integration.conftest import (
    make_max_tokens_response,
    make_text_response,
    make_tool_use_response,
)


# ============================================================
# 1. end_turn 直接收敛
# ============================================================

@pytest.mark.asyncio
async def test_end_turn_converges_immediately(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
):
    """LLM 第一轮就 end_turn -> loop 跑 1 轮 break,token 累加正确。"""
    llm_response_queue.append(make_text_response("done", tokens_in=120, tokens_out=30))

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    assert total_in == 120
    assert total_out == 30
    assert len(llm_response_queue) == 0  # 队列被消费完


# ============================================================
# 2. tool_use 派发 + 工具 handler 被正确调用
# ============================================================

@pytest.mark.asyncio
async def test_tool_use_dispatches_to_handler(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
    temp_tool,
):
    """
    LLM 第 1 轮返 tool_use(my_tool),第 2 轮返 end_turn:
    - 验证 my_tool handler 被调一次
    - 验证 input 内容传递正确
    - 验证 token 累加 = 两轮之和
    """
    handler_calls: list[dict] = []

    async def my_handler(input_dict, *, ctx):
        handler_calls.append({"input": input_dict, "ctx": ctx})
        return {"echo": input_dict.get("msg", "")}

    temp_tool("my_test_tool", my_handler)

    llm_response_queue.append(make_tool_use_response(
        tool_calls=[("call-1", "my_test_tool", {"msg": "hello"})],
        tokens_in=100, tokens_out=50,
    ))
    llm_response_queue.append(make_text_response("ack", tokens_in=80, tokens_out=20))

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    assert len(handler_calls) == 1
    assert handler_calls[0]["input"] == {"msg": "hello"}
    assert handler_calls[0]["ctx"].thread_id == loop_kwargs["thread_id"]
    assert handler_calls[0]["ctx"].user_id == loop_kwargs["user_id"]
    assert total_in == 180
    assert total_out == 70


# ============================================================
# 3. PRE_TOOL_USE hook replace_input 改写 tool 入参
# ============================================================

@pytest.mark.asyncio
async def test_pre_tool_use_replace_input_takes_effect(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
    temp_tool,
):
    """
    注册 PRE_TOOL_USE hook 把 tool_input 改成 {"msg": "PATCHED"};
    handler 应收到改写后的 input。
    """
    from backend.hooks.base import HookContext, HookEvent, HookResult, SyncHook
    from backend.hooks.manager import hook_manager

    class PatchInputHook(SyncHook):
        async def handle(self, ctx: HookContext) -> HookResult:
            return HookResult(
                decision="replace_input",
                updated_input={"msg": "PATCHED"},
            )

    hook_manager.register_sync(HookEvent.PRE_TOOL_USE, PatchInputHook())

    received_inputs: list[dict] = []

    async def my_handler(input_dict, *, ctx):
        received_inputs.append(input_dict)
        return {"ok": True}

    temp_tool("my_test_tool", my_handler)

    llm_response_queue.append(make_tool_use_response(
        tool_calls=[("call-1", "my_test_tool", {"msg": "ORIGINAL"})],
    ))
    llm_response_queue.append(make_text_response())

    svc = OrchestratorService()
    await svc._agent_loop(**loop_kwargs)

    assert received_inputs == [{"msg": "PATCHED"}]


# ============================================================
# 4. PRE_TOOL_USE hook block -> HookBlockedException
# ============================================================

@pytest.mark.asyncio
async def test_pre_tool_use_block_raises(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
    temp_tool,
):
    """注册 block hook,_agent_loop 应让 HookBlockedException 抛出去。"""
    from backend.hooks.base import (
        HookBlockedException, HookContext, HookEvent, HookResult, SyncHook,
    )
    from backend.hooks.manager import hook_manager

    class BlockHook(SyncHook):
        async def handle(self, ctx: HookContext) -> HookResult:
            return HookResult(decision="block", block_reason="forbidden in test")

    hook_manager.register_sync(HookEvent.PRE_TOOL_USE, BlockHook())

    handler_called = False

    async def my_handler(input_dict, *, ctx):
        nonlocal handler_called
        handler_called = True
        return {"ok": True}

    temp_tool("my_test_tool", my_handler)

    llm_response_queue.append(make_tool_use_response(
        tool_calls=[("call-1", "my_test_tool", {})],
    ))

    svc = OrchestratorService()
    with pytest.raises(HookBlockedException):
        await svc._agent_loop(**loop_kwargs)

    assert handler_called is False


# ============================================================
# 5. max_tokens 重试 -> 注入"请继续"-> end_turn 收敛
# ============================================================

@pytest.mark.asyncio
async def test_max_tokens_recovery_retries_then_converges(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
):
    """
    LLM 第 1 轮 max_tokens(被截断),第 2 轮 end_turn:
    - error_recovery.on_max_tokens 触发,注入"请继续"
    - 第 2 轮正常收敛
    - token 两轮累加
    """
    llm_response_queue.append(make_max_tokens_response(text="partial output"))
    llm_response_queue.append(make_text_response("complete", tokens_in=200, tokens_out=80))

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    # 第一轮 input=100 / output=16000(make_max_tokens_response 内默认),第二轮 200/80
    assert total_in == 100 + 200
    assert total_out == 16000 + 80


# ============================================================
# 6. max_tokens 连续达上限 -> 抛 RuntimeError(give up)
# ============================================================

@pytest.mark.asyncio
async def test_max_tokens_recovery_gives_up_after_limit(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
):
    """连续 4 次 max_tokens(上限 3 次)-> 抛 RuntimeError。"""
    for _ in range(4):
        llm_response_queue.append(make_max_tokens_response("..."))

    svc = OrchestratorService()
    with pytest.raises(RuntimeError, match="give up|max_tokens"):
        await svc._agent_loop(**loop_kwargs)


# ============================================================
# 7. prompt_too_long -> global_summarize 后重试
# ============================================================

@pytest.mark.asyncio
async def test_prompt_too_long_triggers_summarize_then_retry(
    orch_loop_env,
    llm_exception_queue,
    loop_kwargs,
    monkeypatch,
):
    """
    第 1 次调 LLM 抛 BadRequestError("prompt is too long"),
    error_recovery.on_prompt_too_long 决策 truncate_history=True,
    走 global_summarize -> 第 2 次成功 end_turn。

    需要单独 monkeypatch global_summarize 防它真去调摘要 LLM。
    """
    from backend.services.orchestrator import service as _service_module

    async def _stub_summarize(messages):
        return [{"role": "user", "content": "[summary]"}]

    monkeypatch.setattr(
        _service_module.context_compactor, "global_summarize", _stub_summarize,
    )

    # mock 一个 BadRequestError 实例(anthropic 要 response 参数)
    import httpx
    fake_response = httpx.Response(
        status_code=400,
        request=httpx.Request("POST", "http://test"),
    )
    too_long = anthropic.BadRequestError(
        message="prompt is too long: 250000 > 200000",
        response=fake_response,
        body=None,
    )

    llm_exception_queue.append(too_long)
    llm_exception_queue.append(make_text_response("recovered", tokens_in=50, tokens_out=20))

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    assert total_in == 50
    assert total_out == 20


# ============================================================
# 8. API 错误退避 -> 重试 -> 收敛
# ============================================================

@pytest.mark.asyncio
async def test_api_error_backoff_then_retry(
    orch_loop_env,
    llm_exception_queue,
    loop_kwargs,
    monkeypatch,
):
    """
    第 1 次抛 RateLimitError -> error_recovery.on_api_error 决策退避 + 重试 ->
    第 2 次 end_turn 成功。

    monkeypatch asyncio.sleep 跳过真实退避等待(避免测试跑几秒)。
    """
    sleep_calls: list[float] = []

    async def _instant_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)

    import httpx
    fake_response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "http://test"),
    )
    rate_limit = anthropic.RateLimitError(
        message="rate limit",
        response=fake_response,
        body=None,
    )

    llm_exception_queue.append(rate_limit)
    llm_exception_queue.append(make_text_response("ok"))

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    # 验证退避 sleep 至少被调用过一次
    assert len(sleep_calls) >= 1
    assert sleep_calls[0] > 0  # 退避时间 > 0


# ============================================================
# 9. dispatch_to_agent + wake_event 唤醒(没有真子 Thread,只测主 loop 等待逻辑)
# ============================================================

@pytest.mark.asyncio
async def test_wake_event_resumes_loop(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
    monkeypatch,
):
    """
    第 1 轮 end_turn,但 _has_unfinished_children=True -> 主 loop await wake_event;
    我们手动 set wake_event,然后下一轮(回 round 1 消费 pending events)
    第 2 轮 has_unfinished_children=False + LLM end_turn -> 真收敛。
    """
    from backend.services.orchestrator.service import OrchestratorService as _Orch

    # 第一次返 True,第二次返 False
    has_unfinished_call_count = 0

    def _has_unfinished_dynamic(self, session, conv_id, orch_id):
        nonlocal has_unfinished_call_count
        has_unfinished_call_count += 1
        return has_unfinished_call_count == 1  # 第一次 True,后续 False

    monkeypatch.setattr(_Orch, "_has_unfinished_children", _has_unfinished_dynamic)

    llm_response_queue.append(make_text_response("first"))
    llm_response_queue.append(make_text_response("second"))

    # 提前 set wake_event,_wait_for_wake 立即返回 True
    loop_kwargs["wake_event"].set()

    svc = OrchestratorService()
    total_in, total_out = await svc._agent_loop(**loop_kwargs)

    # 两轮都被消费
    assert len(llm_response_queue) == 0
    assert has_unfinished_call_count >= 1


# ============================================================
# 10. 多个 tool_call 串行处理 + tool_result 拼回
# ============================================================

@pytest.mark.asyncio
async def test_multiple_tool_calls_serial_execution(
    orch_loop_env,
    llm_response_queue,
    loop_kwargs,
    temp_tool,
):
    """
    一轮 LLM 返 2 个 tool_call:
    - 验证两个 handler 都被调
    - 验证调用顺序与 LLM 输出顺序一致
    """
    call_order: list[str] = []

    async def handler_a(input_dict, *, ctx):
        call_order.append("a")
        return {"name": "a"}

    async def handler_b(input_dict, *, ctx):
        call_order.append("b")
        return {"name": "b"}

    temp_tool("tool_a", handler_a)
    temp_tool("tool_b", handler_b)

    llm_response_queue.append(make_tool_use_response(
        tool_calls=[
            ("call-a", "tool_a", {}),
            ("call-b", "tool_b", {}),
        ],
    ))
    llm_response_queue.append(make_text_response())

    svc = OrchestratorService()
    await svc._agent_loop(**loop_kwargs)

    assert call_order == ["a", "b"]
