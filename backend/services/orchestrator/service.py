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

from backend.hooks.base import HookBlockedException, HookContext, HookEvent
from backend.hooks.manager import hook_manager
from backend.schemas.thread import ThreadStatus
from backend.services.orchestrator.context_compactor import context_compactor
from backend.services.orchestrator.error_recovery import (
    classify_api_error,
    error_recovery,
)
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

        【session 策略】不持有跨 await 的长 session。
        所有需要写库的地方(mark_running / mark_done / update_tokens)都用
        `with db_session()` 短事务,用一次开一次 close 一次。
        adapter / LLM 调用期间 MySQL 端没有挂着的事务,杜绝长事务泄漏。
        """
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

        loop_error: Optional[Exception] = None
        # _agent_loop 跑完会返回累计 token,即使中途异常也尽量返回已累计的部分
        # (异常时返回 (0, 0) 兜底,避免拿到 None)
        total_tokens_in = 0
        total_tokens_out = 0
        try:
            # 主 Agent thread 从 init 推进到 running,写 started_at(便于监控 loop 起跑时间)
            # 短 session:用完立刻关,不持有跨 await 的长 session
            from backend.core.database import db_session
            with db_session() as s:
                await ThreadService(s).mark_running(thread_id)
                s.commit()

            # 立刻推 SSE agent_start,让前端 UI 立即出现"主 Agent 正在思考"的气泡。
            # 否则前端要等到主 Agent 最后调 respond_to_user 才看到反馈,期间几十秒内
            # 用户以为卡死。orchestrator 没有专属 messageId(自己不直接落消息),
            # 用 thread_id 作 message_id 占位,前端 streaming 气泡按 agent_id 索引,
            # 真有消息落库时会再触发新的 agent_start(message_id 不同)。
            from backend.adapters.events import AgentStartEvent
            from backend.services.stream_service import stream_service
            # 从 DB 拿 orchestrator 头像(seed 配的 /static/avatars/avatar-1.jpg)
            from backend.core.database import db_session
            from backend.repositories.agent_repo import AgentRepository
            orchestrator_avatar: Optional[str] = None
            try:
                with db_session() as _s:
                    _row = AgentRepository(_s).get("orchestrator")
                    orchestrator_avatar = _row.avatar if _row else None
            except Exception:
                pass
            try:
                await stream_service.push_event(
                    conversation_id,
                    AgentStartEvent(
                        agent_id="orchestrator",
                        thread_id=thread_id,
                        message_id=thread_id,  # 占位,respond_to_user 会推真的 message_id
                        agent_name="Orchestrator",
                        agent_avatar=orchestrator_avatar,
                    ),
                )
            except Exception:
                logger.exception("failed to push orchestrator agent_start (non-fatal)")

            total_tokens_in, total_tokens_out = await self._agent_loop(
                thread_id=thread_id,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                user_id=user_id,
                wake_event=wake_event,
            )
        except asyncio.CancelledError as exc:
            loop_error = exc
            logger.warning("orchestrator loop %s cancelled", thread_id)
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
            # 同时累加 token 到 threads.tokens_total —— 主 Agent 自己的 LLM 调用消耗
            # (含 chat_completion + context_compactor.global_summarize)。
            # 子 Agent 的 token 写库不在这里,见 thread_service._run_thread 收 AgentDoneEvent 后单独写。
            #
            # 短 session:每次开 / commit / close,绝不长持
            # 重试逻辑:stop 流程里 cancel_all_in_conversation 可能与本 finally 并发写同一行,
            # 触发 MySQL 1205 lock wait timeout 或 1213 deadlock;最多重试 3 次,指数退避。
            from backend.core.database import db_session as _db_session
            from sqlalchemy.exc import OperationalError as _OperationalError
            _MAX_RETRIES = 3
            for _attempt in range(_MAX_RETRIES):
                try:
                    with _db_session() as s:
                        ts = ThreadService(s)
                        if total_tokens_in or total_tokens_out:
                            ts.repo.update_tokens(
                                thread_id,
                                total_tokens_in + total_tokens_out,
                            )
                        if loop_error is None:
                            await ts.mark_done(thread_id, "(orchestrator round complete)")
                        else:
                            await ts.mark_error(thread_id, str(loop_error))
                        s.commit()
                    break  # 成功,跳出重试循环
                except _OperationalError as _oe:
                    _err_code = getattr(_oe.orig, "args", (None,))[0] if _oe.orig else None
                    if _err_code in (1205, 1213) and _attempt < _MAX_RETRIES - 1:
                        logger.warning(
                            "orchestrator %s mark final status hit lock error (code=%s), "
                            "retry %d/%d",
                            thread_id, _err_code, _attempt + 1, _MAX_RETRIES,
                        )
                        await asyncio.sleep(0.5 * (2 ** _attempt))
                    else:
                        logger.exception(
                            "orchestrator %s mark final status failed (attempt %d)",
                            thread_id, _attempt + 1,
                        )
                        break
                except Exception:
                    logger.exception(
                        "orchestrator %s mark final status failed",
                        thread_id,
                    )
                    break

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
    ) -> tuple[int, int]:
        """
        八步循环主体。

        返回 (total_tokens_in, total_tokens_out) —— 本轮主 Agent 自己 LLM 调用的累计 token,
        包括 chat_completion + context_compactor.global_summarize。

        正常 break 路径返回真实累计值;异常路径(LLM 致命错误 / 其他 bug)直接抛出,
        start_loop 兜底但拿不到累计值——这部分 token 在数据库里会丢失记账。

        messages 是主 Agent 的内部 messages_history,只在本函数生命周期内有效。
        MVP 阶段不持久化到 thread.checkpoint(单进程内 conversation 锁保证不会被打断)。

        【session 策略】本函数不持有 session。需要查库时由具体子方法
        (_has_unfinished_children 等)自起短 session,用完立刻关。
        """
        messages: list[dict[str, Any]] = []
        total_tokens_in = 0
        total_tokens_out = 0
        round_count = 0

        # 第一轮必须有一条 user 消息作为 messages[0],否则 Anthropic API 报
        # 400 "messages array cannot be empty"。把当前轮触发的用户消息原文取出注入。
        # 历史更早的对话由 prompt_builder 第 6 层塞进 system,这里只放本轮用户原话。
        from backend.services.message_service import message_service as _msg_svc
        try:
            _user_msg = await _msg_svc.get(user_message_id)
        except Exception:
            _user_msg = None
        if _user_msg is not None and _user_msg.content:
            _user_text_parts = [
                str(b.get("content", ""))
                for b in (_user_msg.content or [])
                if isinstance(b, dict) and b.get("type") == "text" and b.get("content")
            ]
            _user_text = "\n\n".join(_user_text_parts).strip()
            if _user_text:
                # 如果 orchestrator thread 有 dispatch_prompt（如 @ 隐式调度时注入的 mention hint），
                # 把它前置到用户消息文本，让 orchestrator 一开始就知道该 dispatch 给谁
                _dispatch_hint = ""
                try:
                    from backend.core.database import db_session as _dbs
                    from backend.repositories.thread_repo import ThreadRepository as _TR
                    with _dbs() as _s:
                        _t = _TR(_s).get(thread_id)
                        _dispatch_hint = (_t.dispatch_prompt or "") if _t else ""
                except Exception:
                    pass
                _full_text = (_dispatch_hint + _user_text) if _dispatch_hint else _user_text
                messages.append({"role": "user", "content": _full_text})

        # 三路恢复 attempt 计数器(每路独立维护,某路重试成功后**不**重置:
        # 同一 loop 内累计触发次数,达到上限 → give up)
        attempt_max_tokens = 0
        attempt_prompt_too_long = 0
        attempt_api_error = 0

        # 准备 prompt context(每轮重新 build_dynamic,但 thread_id 等不变,只在这里组装一次基础)
        prompt_ctx = PromptContext(
            user_id=user_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            user_message_id=user_message_id,
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

            # ---- 步 0:中止检查 ----
            # 用户点 stop 或上游 cancel 后,stream_service.abort() 会被调用。
            # 这里在每轮开头主动检查,直接抛 CancelledError 退出 loop,
            # 比依赖 task.cancel() 注入更可靠(避免 except Exception 误吞 + LLM 调用
            # 中途的 retry 路径无法及时响应 cancel)。
            from backend.services.stream_service import stream_service as _ss
            if _ss.is_aborted(conversation_id):
                logger.info("orchestrator %s aborted by user, exit loop", thread_id)
                raise asyncio.CancelledError()

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

            # ---- 步 3:调 LLM(含异常恢复 prompt_too_long / api_error) ----
            try:
                response = await llm_client.chat_completion(
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )
            except asyncio.CancelledError:
                # cancel 信号最高优先级,直接外抛让 start_loop finally 走 cancel 路径,
                # 不要进 error_recovery 的 retry 死循环
                raise
            except Exception as exc:
                category = classify_api_error(exc)
                if category == "fatal":
                    # 致命错误(认证 / 422 / 非法请求 / 非 anthropic 异常)→ 直接抛
                    raise
                if category == "prompt_too_long":
                    decision = await error_recovery.on_prompt_too_long(
                        attempt_prompt_too_long
                    )
                    attempt_prompt_too_long += 1
                else:  # "api_error"
                    decision = await error_recovery.on_api_error(
                        exc, attempt_api_error
                    )
                    attempt_api_error += 1

                if not decision.should_retry:
                    logger.warning(
                        "orchestrator %s give up (%s): %s",
                        thread_id,
                        category,
                        decision.give_up_reason,
                    )
                    raise

                if decision.delay_seconds > 0:
                    await asyncio.sleep(decision.delay_seconds)

                if decision.truncate_history:
                    # prompt_too_long 路径:让 compactor 摘要历史
                    messages = await context_compactor.global_summarize(messages)
                    logger.info(
                        "orchestrator %s history summarized due to prompt_too_long",
                        thread_id,
                    )

                if decision.inject_user_message:
                    messages.append({
                        "role": "user",
                        "content": decision.inject_user_message,
                    })

                # 回步 1 重试本轮 LLM 调用。
                # 注意:回步 1 后会重新消费 pending_events——如果在恢复处理期间
                # (尤其 truncate_history 调 global_summarize 是 async 的)有子 Thread
                # 完成事件进队列,这次"重试"会消费这些新事件。这是有意为之:
                # - 重试本来是为了让 LLM 在更干净的 context 下做决策
                # - 新事件本来就应该在下一轮 LLM 看到,提前消费不会破坏语义
                # - 不重新 pop 反而要维护"哪些事件已消费"的状态,得不偿失
                continue

            total_tokens_in += response.tokens_input
            total_tokens_out += response.tokens_output
            tool_ctx.tokens_input = total_tokens_in
            tool_ctx.tokens_output = total_tokens_out

            logger.debug(
                "orchestrator %s round=%d stop_reason=%s tokens=%d/%d",
                thread_id,
                round_count,
                response.stop_reason,
                response.tokens_input,
                response.tokens_output,
            )

            # ---- 步 3.5:max_tokens 处理(stop_reason 走这条路,不走 except) ----
            if response.stop_reason == "max_tokens":
                decision = await error_recovery.on_max_tokens(attempt_max_tokens)
                attempt_max_tokens += 1
                if not decision.should_retry:
                    logger.warning(
                        "orchestrator %s give up (max_tokens): %s",
                        thread_id,
                        decision.give_up_reason,
                    )
                    # 把已截断的 assistant 输出也保留(让用户/审计能看到主 Agent 在崩前
                    # 的最后想法),然后退出 loop
                    if response.content_text:
                        messages.append({
                            "role": "assistant",
                            "content": response.content_text,
                        })
                    raise RuntimeError(
                        f"orchestrator {thread_id}: {decision.give_up_reason}"
                    )

                # 把 LLM 已输出的 text 部分拼回 messages,丢弃可能不完整的 tool_use
                # (截断的 tool_use 不该执行——LLM 都没说完它要干什么)
                if response.content_text:
                    messages.append({
                        "role": "assistant",
                        "content": response.content_text,
                    })
                messages.append({
                    "role": "user",
                    "content": decision.inject_user_message,
                })
                # continue 后会重新消费 pending_events,见步 3 except 块的注释说明
                continue

            # ---- 步 4:end_turn 收敛判断 ----
            if is_terminal_stop_reason(response):
                if self._has_unfinished_children(conversation_id, thread_id):
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
                if response.content_text and response.content_text.strip():
                    await self._emit_assistant_text(
                        conversation_id=conversation_id,
                        thread_id=thread_id,
                        text=response.content_text,
                        tokens_input=total_tokens_in,
                        tokens_output=total_tokens_out,
                    )
                break

            # ---- 步 5:tool_use 派发 ----
            if has_tool_calls(response):
                # ---- 步 5-pre：多文件写入批量审批 ----
                # 本轮有 ≥2 个 create_file / edit_file 时合并为一个 ApprovalBlock，
                # 避免用户一个个点审批框。单个文件写工具仍走原来的逐一 ApprovalHook。
                _FILE_WRITE_TOOLS = {"create_file", "edit_file"}
                file_write_calls = [c for c in response.tool_calls if c.name in _FILE_WRITE_TOOLS]
                if len(file_write_calls) >= 2:
                    from backend.hooks.approval import batch_request_file_approval
                    batch_decision = await batch_request_file_approval(
                        conversation_id=conversation_id,
                        thread_id=thread_id,
                        user_id=user_id,
                        agent_id="orchestrator",
                        calls=file_write_calls,
                    )
                    if batch_decision == "reject":
                        # 批量拒绝：把所有文件写工具标为 blocked，其他工具正常走
                        batch_blocked_ids = {c.id for c in file_write_calls}
                    else:
                        batch_blocked_ids: set[str] = set()
                else:
                    batch_blocked_ids: set[str] = set()

                # 关键时序:先全部 fire PRE_TOOL_USE 拿到最终 input,**再**写 assistant_blocks
                # 否则:assistant_blocks 用改前 input,实际执行用改后 input,
                # messages 历史里 tool_use 块和 tool_result 的入参对不上 → LLM 看到错位易产生幻觉
                resolved_calls: list[tuple[Any, dict[str, Any]]] = []
                # 被 PRE_TOOL_USE block 掉的 call(reject / 黑名单 / 路径越界 / 审批超时),
                # 不真正执行,直接合成 error tool_result 返回给 LLM
                blocked_calls: dict[str, str] = {}  # call_id → block_reason
                for call in response.tool_calls:
                    # 批量审批已拒绝的文件写工具直接 block，跳过 ApprovalHook
                    if call.id in batch_blocked_ids:
                        blocked_calls[call.id] = "批量审批：用户拒绝执行该文件写入操作"
                        resolved_calls.append((call, call.input))
                        continue
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
                        # 批量审批已通过的文件写工具：告知 ApprovalHook 跳过逐一审批
                        extra={"batch_approved": True} if (
                            call.name in _FILE_WRITE_TOOLS and len(file_write_calls) >= 2
                            and call.id not in batch_blocked_ids
                        ) else {},
                    )
                    # hook_manager.fire 在任一 sync hook 返回 block 时会抛 HookBlockedException,
                    # 不会以 HookResult(decision="block") 返回。这里捕获后转成 blocked_calls,
                    # 让 LLM 拿到 is_error tool_result 自己决定下一步,而不是让整个 orchestrator
                    # loop 因为审批超时 / 拒绝就崩掉(原行为:HookBlockedException 一路冒到
                    # start_loop,thread mark_error,前端永远等不到 round_done)。
                    try:
                        pre_result = await hook_manager.fire(HookEvent.PRE_TOOL_USE, pre_ctx)
                    except HookBlockedException as exc:
                        blocked_calls[call.id] = str(exc.reason or exc) or "操作被拒绝"
                        # 仍要进 resolved_calls,assistant_blocks 里 tool_use 块和
                        # tool_result 块必须成对出现(Anthropic API 强制要求)
                        resolved_calls.append((call, call.input))
                        continue
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
                # 推 tool_use 块的 SSE 事件需要的依赖,模块顶部 lazy import 防循环
                from backend.adapters.events import (
                    BlockStartEvent as _BlockStartEvent,
                    BlockStopEvent as _BlockStopEvent,
                )
                from backend.domain.message import ToolUseBlock as _ToolUseBlock
                from backend.services.stream_service import (
                    stream_service as _stream_service,
                )
                for call, final_input in resolved_calls:
                    # 被 PRE_TOOL_USE block 的 call:不真正执行,合成 error tool_result
                    # 让 LLM 知道该工具被拒了,自己决定下一步(重试 / 换思路 / 收手)
                    if call.id in blocked_calls:
                        block_reason = blocked_calls[call.id]
                        tool_result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": call.id,
                            "content": block_reason,
                            "is_error": True,
                        })
                        continue

                    # 用 dataclasses.replace 构造带新 input 的 LLMToolCall,
                    # 不修改 LLM SDK 返回的原对象(避免后续轮次读到被改过的字段)
                    effective_call = dataclasses.replace(call, input=final_input)

                    # 推 BlockStart(ToolUseBlock):前端 workflow 据此显示工具调用详情
                    # (旧版主 Agent loop 完全不推 tool_use SSE,workflow 看不到主 Agent
                    # 自己调了哪些工具,审批 / dispatch 等关键链路无可视化)。
                    # call.id 直接当 block_id 用:同次 tool 调用从 LLM 那儿拿到的就这一个 id,
                    # 跟 tool_result 的 tool_use_id 一致,前端拼接也方便。
                    base_kwargs = {
                        "agent_id": "orchestrator",
                        "thread_id": thread_id,
                        "message_id": user_message_id,
                    }
                    tool_block = _ToolUseBlock(
                        block_id=call.id,
                        tool_name=call.name,
                        input=final_input,
                        status="running",
                    )
                    try:
                        await _stream_service.push_event(
                            conversation_id,
                            _BlockStartEvent(**base_kwargs, block=tool_block),
                        )
                    except Exception:
                        logger.exception(
                            "orchestrator %s push tool_use block_start failed (non-fatal)",
                            thread_id,
                        )

                    logger.info(
                        "orchestrator %s executing tool=%s call_id=%s",
                        thread_id, effective_call.name, effective_call.id,
                    )
                    tool_result = await dispatch_tool_call(effective_call, ctx=tool_ctx)

                    # 推 BlockStop:把 status / output 落到前端 workflow,转圈停下来
                    final_status = "error" if tool_result.is_error else "completed"
                    output_text: Optional[str] = None
                    try:
                        if tool_result.output is not None:
                            import json as _json2
                            output_text = _json2.dumps(
                                tool_result.output, ensure_ascii=False, default=str
                            )
                    except Exception:
                        output_text = str(tool_result.output)
                    try:
                        await _stream_service.push_event(
                            conversation_id,
                            _BlockStopEvent(
                                **base_kwargs,
                                block_id=call.id,
                                final_fields={
                                    "tool_name": call.name,
                                    "status": final_status,
                                    "output": output_text,
                                },
                            ),
                        )
                    except Exception:
                        logger.exception(
                            "orchestrator %s push tool_use block_stop failed (non-fatal)",
                            thread_id,
                        )

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

                # ---- 步 6:压缩 messages_history(只在 tool_use 分支后做,
                # end_turn / max_tokens 路径在 break/continue 之前 messages 已确定,
                # 没必要再压)
                # context_compactor.maybe_compact 内部判 token 阈值,未超阈值时直接返回原列表
                messages = await context_compactor.maybe_compact(messages)
                continue

            # ---- 步 7/8 暂跳过 ----
            # TODO[F-loop-checkpoint]: thread_service.save_checkpoint(thread_id, ...)
            # TODO[F-loop-token-write/inner]: 主 Agent 内部 token 写库已经在 start_loop finally
            # 块统一处理(用本函数返回值);adapter 层子 Thread token 由 [TODO-18] 无履生 单独做。

        # loop 结束
        logger.info(
            "orchestrator %s done after %d round(s), tokens=%d/%d",
            thread_id,
            round_count,
            total_tokens_in,
            total_tokens_out,
        )
        return total_tokens_in, total_tokens_out

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

    async def _emit_assistant_text(
        self,
        *,
        conversation_id: str,
        thread_id: str,
        text: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        """
        主 Agent end_turn 时直接说话(没调 respond_to_user)的兜底:
        把 LLM 输出的纯文本作为一条 assistant 消息落库 + 推 SSE,
        与 respond_to_user 工具产生的效果完全一致。
        否则前端永远收不到 agent_start / block_start,看不到主 Agent 的回复。
        """
        from backend.adapters.events import (
            AgentDoneEvent,
            AgentStartEvent,
            BlockStartEvent,
            BlockStopEvent,
        )
        from backend.domain.message import TextBlock
        from backend.services.message_service import message_service
        from backend.services.stream_service import stream_service
        from backend.core.utils import gen_uuid

        _ORCHESTRATOR_AGENT_ID = "orchestrator"
        _ORCHESTRATOR_AGENT_NAME = "Orchestrator"

        block_id = gen_uuid()
        msg = await message_service.create_assistant_message(
            conversation_id=conversation_id,
            agent_id=_ORCHESTRATOR_AGENT_ID,
            content_blocks=[TextBlock(block_id=block_id, content=text)],
            sender=_ORCHESTRATOR_AGENT_NAME,
            thread_id=thread_id,
        )

        base = {
            "agent_id": _ORCHESTRATOR_AGENT_ID,
            "thread_id": thread_id,
            "message_id": msg.id,
        }
        await stream_service.push_event(
            conversation_id,
            AgentStartEvent(**base, agent_name=_ORCHESTRATOR_AGENT_NAME),
        )
        await stream_service.push_event(
            conversation_id,
            BlockStartEvent(
                **base,
                block=TextBlock(block_id=block_id, content=text),
            ),
        )
        await stream_service.push_event(
            conversation_id,
            BlockStopEvent(**base, block_id=block_id),
        )
        await stream_service.push_event(
            conversation_id,
            AgentDoneEvent(**base, tokens_input=tokens_input, tokens_output=tokens_output),
        )

    def _has_unfinished_children(
        self,
        conversation_id: str,
        orchestrator_thread_id: str,
    ) -> bool:
        """
        判断该 conversation 下是否还有未完成的子 Thread(排除 orchestrator 自己)。
        未完成 = init / running / suspended。

        【session 策略】自起短 session,用完立刻关,绝不持有跨 await 的长 session。
        每次调用都是新 session,天然无 identity map 陈旧问题(原代码 expire_all 是
        因为长 session 才需要,改短 session 后不需要了)。
        """
        from backend.core.database import db_session
        with db_session() as s:
            ts = ThreadService(s)
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
