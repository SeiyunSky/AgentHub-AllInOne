"""
OrchestratorService —— 主 Agent loop 入口与核心循环

start_loop 的完整生命周期:
1. 注册 thread_service event listener + 创建 wake_event(等待子 Thread 完成时挂起)
2. fire PRE_ORCHESTRATE hook
3. 跑 _agent_loop(八步循环)
4. fire POST_ORCHESTRATE hook
5. unregister listener
6. mark_done(orchestrator thread)
7. 调 chat_service.on_round_done(推 round_done + drain pending 消息)

_agent_loop 八步:
1. 消费 pending_events 队列(子 Thread 完成事件) → 转 user 消息追加到 messages
2. 构建 system prompt (六层管道) + tools payload (19 个工具 schema)
3. 调 llm_client.chat_completion (累计 token)
4. stop_reason=end_turn:
   - 还有未完成子 Thread → await wake_event,被唤醒后回步 1
   - 没有未完成子 Thread → break
5. stop_reason=tool_use:
   - assistant content (text + tool_use blocks) 拼回 messages
   - 串行处理每个 tool_call:
     - fire PRE_TOOL_USE hook (可 replace_input)
     - dispatch_tool_call → 拿 ToolResult
     - fire POST_TOOL_USE hook (异步 audit)
   - 把所有 tool_result 拼成 user 消息追加到 messages
   - 回步 1
6. checkpoint 持久化(MVP 阶段不写库,留内存)
7. token 累计(MVP 阶段只 log,不写 threads.tokens_total)
8. 回步 1

唤醒机制:
- listener 收到子 Thread 完成事件 → wake_event.set()
- _agent_loop 步 4 仅在 end_turn 且有未完成子 Thread 时 await wake_event
- 这样设计的原因:tool_use 期间 LLM 自己决定是否要 read_thread_status 等;
  end_turn 表示 LLM 觉得自己没事干了,这时如果还有 Thread 在跑,挂起等。

trace_id 约定:MVP 阶段用 orchestrator thread_id 作为 trace_id 串起 Hook 调用,
等 Step 16 (structlog) 接通后改成真 trace_id。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.hooks.base import HookContext, HookEvent
from backend.hooks.manager import hook_manager
from backend.schemas.thread import ThreadStatus
from backend.services.orchestrator.llm_client import LLMToolCall, llm_client
from backend.services.orchestrator.prompt_builder import (
    DYNAMIC_BOUNDARY,
    PromptContext,
    prompt_builder,
)
from backend.services.orchestrator.tool_registry import (
    ToolContext,
    build_tools_payload,
    dispatch_tool_call,
    has_tool_calls,
    is_terminal_stop_reason,
    wrap_tool_result,
)
from backend.services.thread_service import ThreadService


logger = logging.getLogger(__name__)


# 主 Agent loop 单轮"挂起等子 Thread 完成"的最长等待时间(秒)
# 防止子 Thread 永远不回报时主 loop 永久挂起,超时后退出 loop 走 mark_done
# 30 分钟对单个 IM round 来说足够长——超过表示子 Thread 出问题了
_WAKE_TIMEOUT_SECONDS = 30 * 60


class OrchestratorService:
    """
    主 Agent loop 业务编排。

    session 由调用方注入,但本 service 跑长循环,内部需要时会自起新 session
    (避免与 chat_service 调用方共享 session 引发并发问题)。
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session = session

    # --------------------------------------------------------
    # 公开入口
    # --------------------------------------------------------

    async def start_loop(
        self,
        *,
        thread_id: str,
        conversation_id: str,
        user_message_id: str,
        user_id: str,
    ) -> None:
        """
        启动主 Agent loop。被 chat_service._group_orchestrate_flow 调。

        生命周期管理:无论 _agent_loop 正常 break / 抛异常,
        都保证 unregister listener + mark_done + chat_service.on_round_done。

        session 由本方法自起(不依赖 self.session 注入):
        模块级单例 orchestrator_service 的 self.session 默认 None,
        统一用 SessionLocal() 起独立 session 贯穿整个 loop 生命周期,
        避免 session=None 时静默跳过写库 / 查库。
        """
        from backend.core.database import SessionLocal

        wake_event = asyncio.Event()

        # listener:子 Thread 进入终态时被 thread_service 调,只负责唤醒主 loop
        # 摘要由 thread_service._on_thread_terminal 自己写进 _pending_events 队列了,
        # 主 loop 下一轮 pop_pending_events 自然消费,不在 listener 里处理
        async def _on_child_thread_event(
            child_thread_id: str,
            summary: str,
            success: bool,
        ) -> None:
            logger.debug(
                "orchestrator %s woken by child %s, success=%s",
                thread_id,
                child_thread_id,
                success,
            )
            wake_event.set()

        ThreadService.register_event_listener(thread_id, _on_child_thread_event)

        base_hook_ctx_kwargs = {
            "trace_id": thread_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "thread_id": thread_id,
            "message_id": user_message_id,
            "agent_id": "orchestrator",
        }

        # PRE_ORCHESTRATE
        await hook_manager.fire(
            HookEvent.PRE_ORCHESTRATE,
            HookContext(event=HookEvent.PRE_ORCHESTRATE, **base_hook_ctx_kwargs),
        )

        loop_session = SessionLocal()
        loop_error: Optional[Exception] = None
        try:
            await self._agent_loop(
                thread_id=thread_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                user_id=user_id,
                wake_event=wake_event,
                session=loop_session,
            )
        except Exception as exc:
            loop_error = exc
            logger.exception(
                "orchestrator loop %s failed",
                thread_id,
            )
        finally:
            # POST_ORCHESTRATE 不论成败都 fire
            await hook_manager.fire(
                HookEvent.POST_ORCHESTRATE,
                HookContext(
                    event=HookEvent.POST_ORCHESTRATE,
                    **base_hook_ctx_kwargs,
                    extra={"error": str(loop_error)} if loop_error else {},
                ),
            )
            ThreadService.unregister_event_listener(thread_id)

            # 写 thread 终态:正常 done / 异常 error
            try:
                ts = ThreadService(loop_session)
                if loop_error is None:
                    await ts.mark_done(thread_id, "(orchestrator round complete)")
                else:
                    await ts.mark_error(thread_id, str(loop_error))
                loop_session.commit()
            except Exception:
                logger.exception(
                    "orchestrator %s mark final status failed",
                    thread_id,
                )
                loop_session.rollback()
            finally:
                loop_session.close()

            # 触发 chat_service 推 round_done + drain pending 消息
            # lazy import 防循环依赖(chat_service 也 import orchestrator)
            from backend.services.chat_service import on_round_done
            await on_round_done(conversation_id)

    # --------------------------------------------------------
    # 八步循环
    # --------------------------------------------------------

    async def _agent_loop(
        self,
        *,
        thread_id: str,
        conversation_id: str,
        user_message_id: str,
        user_id: str,
        wake_event: asyncio.Event,
        session: Session,
    ) -> None:
        """
        八步循环主体。

        messages 是主 Agent 的内部 messages_history,只在本函数生命周期内有效。
        MVP 阶段不持久化到 thread.checkpoint(单进程内 conversation 锁保证不会被打断)。

        session 由 start_loop 注入,本函数不负责 commit/close(那是 start_loop finally 块的事),
        只在需要查 thread 时通过 ThreadService(session) 用。
        """
        messages: list[dict[str, Any]] = []
        total_tokens_in = 0
        total_tokens_out = 0
        round_count = 0

        # 准备 prompt context(每轮重新 build_dynamic,但 thread_id 等不变,只在这里组装一次基础)
        prompt_ctx = PromptContext(
            user_id=user_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            # MVP 阶段先空 —— 主 Agent 通过 list_available_agents 工具按需查
            available_agent_ids=[],
        )

        # 静态 prompt 在 loop 期间不变(orchestrator.md / AGENTHUB.md 内容固定),
        # 一次构建缓存到局部变量,避免每轮重复 IO
        static_prompt = await prompt_builder.build_static(prompt_ctx)

        # tools schema 也在 loop 期间不变(19 个工具注册时即定型),一次构建缓存
        tools = build_tools_payload()

        tool_ctx = ToolContext(
            thread_id=thread_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            user_id=user_id,
        )

        while True:
            round_count += 1

            # ---- 步 1:消费 pending_events ----
            pending_summaries = ThreadService.pop_pending_events(thread_id)
            for summary in pending_summaries:
                messages.append({
                    "role": "user",
                    "content": f"[子 Thread 事件] {summary}",
                })

            # ---- 步 2:构建 system prompt ----
            # 静态层缓存复用,只重算动态层(长期记忆 / 任务图状态可能变)
            dynamic_prompt = await prompt_builder.build_dynamic(prompt_ctx)
            if static_prompt and dynamic_prompt:
                system_prompt = static_prompt + DYNAMIC_BOUNDARY + dynamic_prompt
            else:
                system_prompt = static_prompt or dynamic_prompt

            # ---- 步 3:调 LLM ----
            try:
                response = await llm_client.chat_completion(
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )
            except Exception:
                # TODO[F-loop-recovery]: 接 error_recovery 三路(max_tokens / prompt_too_long / API)
                # 现在直接抛,start_loop 的 try/except 兜底 mark_error
                raise

            total_tokens_in += response.tokens_input
            total_tokens_out += response.tokens_output

            logger.debug(
                "orchestrator %s round=%d stop_reason=%s tokens=%d/%d",
                thread_id,
                round_count,
                response.stop_reason,
                response.tokens_input,
                response.tokens_output,
            )

            # ---- 步 4:end_turn 收敛判断 ----
            if is_terminal_stop_reason(response):
                if self._has_unfinished_children(session, conversation_id, thread_id):
                    # 还有子 Thread 没回报,挂起等唤醒
                    logger.debug(
                        "orchestrator %s suspended waiting for children",
                        thread_id,
                    )
                    woke = await self._wait_for_wake(wake_event)
                    if not woke:
                        logger.warning(
                            "orchestrator %s wake timeout (%ds) — exit loop",
                            thread_id,
                            _WAKE_TIMEOUT_SECONDS,
                        )
                        break
                    # 唤醒后回步 1 消费新 pending_events
                    continue
                # 没有未完成子 Thread → 真正收敛
                break

            # ---- 步 5:tool_use 派发 ----
            if has_tool_calls(response):
                # 关键时序:先全部 fire PRE_TOOL_USE 拿到最终 input,**再**写 assistant_blocks
                # 否则:assistant_blocks 用改前 input,实际执行用改后 input,
                # messages 历史里 tool_use 块和 tool_result 的入参对不上 → LLM 看到错位易产生幻觉
                resolved_calls: list[tuple[Any, dict[str, Any]]] = []
                for call in response.tool_calls:
                    pre_ctx = HookContext(
                        event=HookEvent.PRE_TOOL_USE,
                        trace_id=thread_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        thread_id=thread_id,
                        message_id=user_message_id,
                        agent_id="orchestrator",
                        tool_name=call.name,
                        tool_input=call.input,
                    )
                    pre_result = await hook_manager.fire(HookEvent.PRE_TOOL_USE, pre_ctx)
                    if pre_result.decision == "replace_input" and pre_result.updated_input is not None:
                        final_input = pre_result.updated_input
                    else:
                        final_input = call.input
                    resolved_calls.append((call, final_input))

                # 现在用最终 input 写 assistant_blocks(messages 历史与实际执行一致)
                assistant_blocks: list[dict[str, Any]] = []
                if response.content_text:
                    assistant_blocks.append({
                        "type": "text",
                        "text": response.content_text,
                    })
                for call, final_input in resolved_calls:
                    assistant_blocks.append({
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": final_input,
                    })
                messages.append({"role": "assistant", "content": assistant_blocks})

                # 串行执行每个 tool_call(并行可能引起工具间状态竞争)
                tool_result_blocks: list[dict[str, Any]] = []
                for call, final_input in resolved_calls:
                    # 用 dataclasses.replace 构造带新 input 的 LLMToolCall,
                    # 不修改 LLM SDK 返回的原对象(避免后续轮次读到被改过的字段)
                    effective_call = dataclasses.replace(call, input=final_input)

                    tool_result = await dispatch_tool_call(effective_call, ctx=tool_ctx)

                    # POST_TOOL_USE hook(主要给 audit)
                    post_ctx = HookContext(
                        event=HookEvent.POST_TOOL_USE,
                        trace_id=thread_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        thread_id=thread_id,
                        message_id=user_message_id,
                        agent_id="orchestrator",
                        tool_name=call.name,
                        tool_input=final_input,
                        tool_output=tool_result.output,
                    )
                    await hook_manager.fire(HookEvent.POST_TOOL_USE, post_ctx)

                    tool_result_blocks.append(wrap_tool_result(tool_result))

                # 拼 tool_result 进 messages,继续下一轮 LLM
                messages.append({"role": "user", "content": tool_result_blocks})
                continue

            # ---- 步 6/7/8 暂跳过 ----
            # TODO[F-loop-checkpoint]: thread_service.save_checkpoint(thread_id, ...)
            # TODO[F-loop-token-write]: thread_repo.update_tokens(thread_id, delta)
            # TODO[F-loop-compact]: context_compactor.maybe_compact(messages)

        # loop 结束
        logger.info(
            "orchestrator %s done after %d round(s), tokens=%d/%d",
            thread_id,
            round_count,
            total_tokens_in,
            total_tokens_out,
        )

    # --------------------------------------------------------
    # 内部辅助
    # --------------------------------------------------------

    async def _wait_for_wake(self, wake_event: asyncio.Event) -> bool:
        """
        挂起等子 Thread 完成事件。
        返回 True 表示被唤醒,False 表示超时(主 loop 应退出)。
        被唤醒后立即 clear 准备下次等待。
        """
        try:
            await asyncio.wait_for(wake_event.wait(), timeout=_WAKE_TIMEOUT_SECONDS)
            wake_event.clear()
            return True
        except asyncio.TimeoutError:
            return False

    def _has_unfinished_children(
        self,
        session: Session,
        conversation_id: str,
        orchestrator_thread_id: str,
    ) -> bool:
        """
        判断该 conversation 下是否还有未完成的子 Thread(排除 orchestrator 自己)。
        未完成 = init / running / suspended。

        session 由 _agent_loop 注入 —— 不依赖 self.session(模块级单例 self.session=None)。

        关键:每次查询前 expire_all(),让 SQLAlchemy 抛弃 identity map 缓存重新读库。
        子 Thread 状态变更发生在后台 asyncio.Task 里(用别的 session 写),
        loop session 如果不主动 expire,可能拿到陈旧的 init/running 视图,
        导致主 loop 误判"还有 Thread 没完成"陷入死等到超时。
        """
        session.expire_all()
        ts = ThreadService(session)
        active = ts.repo.list_active_in_conversation(conversation_id)
        for t in active:
            if t.id == orchestrator_thread_id:
                continue
            if t.status in {
                ThreadStatus.INIT.value,
                ThreadStatus.RUNNING.value,
                ThreadStatus.SUSPENDED.value,
            }:
                return True
        return False


orchestrator_service = OrchestratorService()
