"""
orchestrator_tools —— 主 Agent 19 个内置工具的 Handler 注册

Input Schema 唯一真相源在 backend.schemas.orchestrator_tools(A 阶段定的契约),
本文件负责把每个 schema 挂上 @register_tool 装饰器并实装 handler。

模块 import 即触发注册(每个 handler 上挂 @register_tool 装饰器),
所以 orchestrator/service.py 启动 loop 前要先 import 本模块一次,
让 TOOL_HANDLERS / TOOL_SCHEMAS 填满。

19 个工具按文档第八节分 5 组:
- A. 任务调度 (4)   dispatch_to_agent / read_thread_status / read_thread_result / cancel_thread
- B. 任务链管理 (5) create_task_plan / update_task_status / read_task_plan /
                    add_task / remove_task
- C. 用户交互 (3)   respond_to_user / request_user_clarification /
                    present_task_plan_for_review
- D. 上下文检索 (3) read_conversation_history / list_available_agents /
                    get_agent_capabilities
- E. 文件 (4)       create_file / read_file / edit_file / list_directory

约定:
- 每个 handler 第一行 model_validate 把 LLM dict 校验成 Pydantic input
- 业务调 service / repo,不绕过
- 返回 dict(JSON 可序列化),tool_registry 会 json.dumps 成 tool_result.content
- 错误处理由外层 dispatch_tool_call 兜底,handler 内部不 try/except

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.adapters.events import (
    AgentDoneEvent,
    AgentStartEvent,
    BlockStartEvent,
    BlockStopEvent,
)
from backend.core.utils import gen_uuid
from backend.domain.message import TextBlock
from backend.hooks.base import HookContext, HookEvent
from backend.hooks.manager import hook_manager
from backend.schemas.orchestrator_tools import (
    AddTaskInput,
    CancelThreadInput,
    CreateFileInput,
    CreateTaskPlanInput,
    DispatchToAgentInput,
    EditFileInput,
    GetAgentCapabilitiesInput,
    ListAvailableAgentsInput,
    ListDirectoryInput,
    PresentTaskPlanForReviewInput,
    ReadConversationHistoryInput,
    ReadFileInput,
    ReadTaskPlanInput,
    ReadThreadResultInput,
    ReadThreadStatusInput,
    RemoveTaskInput,
    RequestUserClarificationInput,
    RespondToUserInput,
    UpdateTaskStatusInput,
)
from backend.services.agent_service import agent_service
from backend.services.conversation_service import conversation_service
from backend.services.memory_service import MEMORY_ROOT, ensure_memory_dir
from backend.services.message_service import message_service
from backend.services.orchestrator.tool_registry import (
    ToolContext,
    register_tool,
)
from backend.services.stream_service import stream_service


logger = logging.getLogger(__name__)


# 主 Agent 在 SSE 中的 agent_id 约定 —— 复用 Step 3 service.py 里的常量
_ORCHESTRATOR_AGENT_ID = "orchestrator"
_ORCHESTRATOR_AGENT_NAME = "主 Agent"


# ============================================================
# 公共辅助:文件沙箱路径解析
# ============================================================

def _resolve_sandbox_path(ctx: ToolContext, raw_path: str) -> Path:
    """
    把 LLM 传入的 path 解析为绝对路径,并校验落在
    `runtime/memory/{user_id}/{conversation_id}/` 沙箱内。

    任何尝试逃出沙箱的路径(`../foo`、绝对路径、symlink 跳出等)都抛 ValueError。

    沙箱根复用 memory_service 的目录约定 —— 文件工具和长期记忆共享同一目录,
    LLM 写入的文件能被记忆工具看到,反之亦然。
    """
    base = ensure_memory_dir(ctx.user_id, ctx.conversation_id).resolve()
    candidate = (base / raw_path).resolve()
    # 必须是 base 的后代(等于 base 自身也算合法,虽然语义上没意义)
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError(
            f"路径 {raw_path!r} 越出沙箱,只允许操作当前会话目录下的文件"
        )
    return candidate


def _relative_to_sandbox(ctx: ToolContext, abs_path: Path) -> str:
    """把绝对路径转回相对沙箱的字符串(给 LLM 看)。"""
    base = ensure_memory_dir(ctx.user_id, ctx.conversation_id).resolve()
    try:
        return str(abs_path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(abs_path)


# ============================================================
# A. 任务调度 (4 个)
# ============================================================

@register_tool(
    name="dispatch_to_agent",
    description="派任务给某个子 Agent,立即启动并异步执行,返回 thread_id。",
    input_model=DispatchToAgentInput,
)
async def dispatch_to_agent(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    异步派任务给指定 Agent,立即启动 Thread。

    返回 {thread_id, agent_id, blocked_by}——不带 status,
    因为 schedule_conversation 后状态可能瞬间变更,让 LLM 用 read_thread_status 拿权威值。

    [TODO/D7-blocker]: thread_service._run_thread 用本 handler 传入的 session,
    handler close 后后台 Task 访问会炸。根本修法在 thread_service 自起 SessionLocal。
    MVP 单线程串行下不触发,上线前必须修。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = DispatchToAgentInput.model_validate(tool_input)

    # ----- 占位符兜底:LLM 经常忘了把上游产出贴进 prompt,留 {{...}} 字面量给子 Agent。
    # 这里检测到任何 {{...}} 占位符就尝试用 blocked_by 列出的上游 Thread 产出自动替换。
    # 替换后还有 {{...}} 残留就直接报错让 LLM 重派,避免子 Agent 拿到无效 prompt。
    final_prompt, placeholder_error = _resolve_upstream_placeholders(
        parsed.prompt, parsed.blocked_by or []
    )
    if placeholder_error is not None:
        return {"error": placeholder_error}

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        thread = ts.create_thread(
            conversation_id=ctx.conversation_id,
            message_id=ctx.user_message_id,
            agent_id=parsed.agent_id,
            blocked_by=parsed.blocked_by,
            dispatch_prompt=final_prompt,
        )
        session.commit()
        await ts.schedule_conversation(ctx.conversation_id)
        return {
            "thread_id": thread.id,
            "agent_id": thread.agent_id,
            "blocked_by": list(thread.blocked_by or []),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _extract_text_from_thread_messages(messages: list) -> str:
    """从 Thread 的 messages 列表里抽出所有 text block,拼成一段文本。

    messages 元素是 ORM Message,content 是 ContentBlock dict 列表。
    """
    parts: list[str] = []
    for m in messages:
        for block in (m.content or []):
            if isinstance(block, dict) and block.get("type") == "text":
                txt = block.get("content")
                if txt:
                    parts.append(str(txt))
    return "\n\n".join(parts)


def _resolve_upstream_placeholders(
    prompt: str,
    blocked_by: list[str],
) -> tuple[str, Optional[str]]:
    """识别 prompt 里 {{...}} 占位符,用 blocked_by 上游 Thread 产出替换。

    返回 (替换后 prompt, error)。error 非 None 时 caller 应放弃 dispatch。

    替换策略(简单粗暴):
    - 没有 {{...}}:直接返回原 prompt
    - 有占位符但 blocked_by 为空:报错(LLM 没声明依赖却引用上游)
    - 有占位符且 blocked_by 非空:用第 1 个上游 Thread 的产出替换全部 {{...}}
      (MVP 阶段不区分 {{UPSTREAM_X}} / {{UPSTREAM_Y}} 这种细分,直接全替成同一份)
    - 替换后还有 {{...}} 残留:报错(替换没用,LLM 留了别的占位符)
    """
    import re

    placeholders = re.findall(r"\{\{[^{}]+\}\}", prompt)
    if not placeholders:
        return prompt, None

    if not blocked_by:
        return prompt, (
            f"prompt 含占位符 {placeholders} 但 blocked_by 为空。"
            "若需引用上游产出,请在 dispatch 时声明 blocked_by;"
            "否则请把占位符替换成实际内容再派活。"
        )

    # 拿第 1 个上游 Thread 的产出
    from backend.core.database import SessionLocal
    from backend.repositories.message_repo import MessageRepository
    from backend.repositories.thread_repo import ThreadRepository

    upstream_id = blocked_by[0]
    session = SessionLocal()
    try:
        session.expire_all()
        thread = ThreadRepository(session).get(upstream_id)
        if thread is None:
            return prompt, f"上游 Thread {upstream_id} 不存在,无法填充占位符。"
        if thread.status != "done":
            return prompt, (
                f"上游 Thread {upstream_id} 状态为 {thread.status},尚未 done,"
                "暂不能用于占位符替换。请等其完成后再 dispatch,或先调 read_thread_status 确认。"
            )
        messages = MessageRepository(session).list_by_thread(upstream_id)
    finally:
        session.close()

    upstream_text = _extract_text_from_thread_messages(messages)
    if not upstream_text.strip():
        return prompt, f"上游 Thread {upstream_id} 没有可用文本产出,无法填充占位符。"

    # 全部 {{...}} 都替换成上游产出
    replaced = re.sub(r"\{\{[^{}]+\}\}", upstream_text, prompt)

    # 替换后还有 {{...}}? 不应该,但 upstream_text 里可能本身就包含模板 → 不报错
    # 只检查没替换成功的情况(replaced 跟原 prompt 一样长且仍有占位符)
    if replaced == prompt and re.search(r"\{\{[^{}]+\}\}", replaced):
        return prompt, "占位符替换失败:请检查 prompt 格式或手动替换占位符后再派活。"

    return replaced, None


@register_tool(
    name="read_thread_status",
    description="查 Thread 当前状态(init/running/suspended/done/error/cancelled)。",
    input_model=ReadThreadStatusInput,
)
async def read_thread_status(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """读取某 Thread 的实时状态。返回 {thread_id, agent_id, status, blocked_by, error_message}。"""
    from backend.core.database import SessionLocal
    from backend.repositories.thread_repo import ThreadRepository

    parsed = ReadThreadStatusInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        # 关键:expire_all 强制重读,避免 identity map 缓存住后台 Task 写的状态变化
        session.expire_all()
        thread = ThreadRepository(session).get(parsed.thread_id)
        if thread is None:
            return {"error": f"Thread {parsed.thread_id} 不存在"}
        return {
            "thread_id": thread.id,
            "agent_id": thread.agent_id,
            "status": thread.status,
            "blocked_by": list(thread.blocked_by or []),
            "error_message": thread.error_message,
            "started_at": thread.started_at.isoformat() if thread.started_at else None,
            "finished_at": thread.finished_at.isoformat() if thread.finished_at else None,
        }
    finally:
        session.close()


@register_tool(
    name="read_thread_result",
    description="读子 Thread 的完整产出(状态 + 子 Agent 的回复消息列表)。",
    input_model=ReadThreadResultInput,
)
async def read_thread_result(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    读取 Thread 完整结果。返回:
    - status / agent_id / 时间戳 / token / 错误
    - messages: 该 Thread 产出的所有 assistant 消息列表(序列化的 ContentBlock 数组)
    """
    from backend.core.database import SessionLocal
    from backend.repositories.message_repo import MessageRepository
    from backend.repositories.thread_repo import ThreadRepository

    parsed = ReadThreadResultInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        session.expire_all()
        thread = ThreadRepository(session).get(parsed.thread_id)
        if thread is None:
            return {"error": f"Thread {parsed.thread_id} 不存在"}
        messages = MessageRepository(session).list_by_thread(parsed.thread_id)
        return {
            "thread_id": thread.id,
            "agent_id": thread.agent_id,
            "status": thread.status,
            "tokens_total": thread.tokens_total or 0,
            "started_at": thread.started_at.isoformat() if thread.started_at else None,
            "finished_at": thread.finished_at.isoformat() if thread.finished_at else None,
            "error_message": thread.error_message,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
    finally:
        session.close()


@register_tool(
    name="cancel_thread",
    description="中止某个子 Thread。",
    input_model=CancelThreadInput,
)
async def cancel_thread(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    取消指定 Thread 并连带传播取消其所有下游(blocked_by 引用它的 Thread)。
    返回 {cancelled_self, cancelled_downstream_ids}。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = CancelThreadInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        cancelled_self = await ts.cancel_thread(parsed.thread_id)
        downstream = await ts.cancel_dependents(parsed.thread_id)
        session.commit()
        return {
            "cancelled_self": cancelled_self.id if cancelled_self else None,
            "cancelled_downstream_ids": [t.id for t in downstream],
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ============================================================
# B. 任务链管理 (5 个)
# ============================================================

@register_tool(
    name="create_task_plan",
    description="一次性创建多个任务(含依赖图),由调度器按 blocked_by 决定启动顺序。",
    input_model=CreateTaskPlanInput,
)
async def create_task_plan(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    把 TaskPlan 落地为 N 个 Thread + 触发调度。
    返回 {thread_ids: [...]} 给 LLM 后续用。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = CreateTaskPlanInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        threads = ts.create_task_plan(
            parsed.plan,
            conversation_id=ctx.conversation_id,
            message_id=ctx.user_message_id,
        )
        session.commit()
        await ts.schedule_conversation(ctx.conversation_id)
        return {"thread_ids": [t.id for t in threads]}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@register_tool(
    name="update_task_status",
    description="标记任务为 cancelled(主动放弃)。其他状态由系统自动管理。",
    input_model=UpdateTaskStatusInput,
)
async def update_task_status(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    Schema 限定 status=Literal["cancelled"],等价于 cancel_thread(不传播下游)。
    需要传播下游用 cancel_thread。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = UpdateTaskStatusInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        cancelled = await ts.cancel_thread(parsed.task_id)
        session.commit()
        if cancelled is None:
            return {"error": f"Thread {parsed.task_id} 不存在或已结束"}
        return {"task_id": cancelled.id, "status": cancelled.status}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@register_tool(
    name="read_task_plan",
    description="读取本轮所有任务的状态(任务图全貌)。",
    input_model=ReadTaskPlanInput,
)
async def read_task_plan(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    返回当前 round 所有 Thread 的轻量结构(不含完整产出)。
    用于主 Agent 总览"我派了哪些活、各自跑成啥样了"。
    """
    from backend.core.database import SessionLocal
    from backend.repositories.thread_repo import ThreadRepository

    ReadTaskPlanInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        session.expire_all()
        threads = ThreadRepository(session).list_by_message(ctx.user_message_id)
        return {
            "tasks": [
                {
                    "thread_id": t.id,
                    "agent_id": t.agent_id,
                    "status": t.status,
                    "blocked_by": list(t.blocked_by or []),
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                }
                for t in threads
            ]
        }
    finally:
        session.close()


@register_tool(
    name="add_task",
    description="追加一个待启动的任务节点(等 blocked_by 满足后调度器再启动)。",
    input_model=AddTaskInput,
)
async def add_task(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    追加任务节点。和 dispatch_to_agent 共享 thread_service.create_thread,
    区别仅在于:本工具假定 blocked_by 非空(等依赖),dispatch_to_agent 通常 blocked_by=[]。
    实际调度逻辑相同——schedule_conversation 内部判 blocked_by 是否就绪。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = AddTaskInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        thread = ts.add_task(
            conversation_id=ctx.conversation_id,
            message_id=ctx.user_message_id,
            agent_id=parsed.agent_id,
            blocked_by=parsed.blocked_by,
            dispatch_prompt=parsed.prompt,
        )
        session.commit()
        await ts.schedule_conversation(ctx.conversation_id)
        return {
            "thread_id": thread.id,
            "agent_id": thread.agent_id,
            "blocked_by": list(thread.blocked_by or []),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@register_tool(
    name="remove_task",
    description="移除尚未启动的任务(已启动的请用 cancel_thread)。",
    input_model=RemoveTaskInput,
)
async def remove_task(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """硬删除尚未启动的 Thread。返回 {removed: bool}。"""
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = RemoveTaskInput.model_validate(tool_input)

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        ok = ts.remove_task(parsed.task_id)
        session.commit()
        return {"task_id": parsed.task_id, "removed": ok}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ============================================================
# C. 用户交互 (3 个)
# ============================================================

@register_tool(
    name="respond_to_user",
    description="给用户回话(本轮用户能看到的输出走这里)。",
    input_model=RespondToUserInput,
)
async def respond_to_user(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    主 Agent 直接回话给用户。

    实现:
    1. message_service.create_assistant_message 落 messages 表(role=assistant, agent_id="orchestrator")
    2. 推 SSE 一组事件给前端:AgentStart → BlockStart(TextBlock) → BlockStop → AgentDone
       (BlockStart 直接带完整 content,不流式拆分;打字机效果归前端)
    3. 返回 {message_id} 给 LLM
    """
    parsed = RespondToUserInput.model_validate(tool_input)
    text = parsed.message

    # 1. 落库
    msg = await message_service.create_assistant_message(
        conversation_id=ctx.conversation_id,
        agent_id=_ORCHESTRATOR_AGENT_ID,
        content_blocks=[TextBlock(block_id=gen_uuid(), content=text)],
        sender=_ORCHESTRATOR_AGENT_NAME,
    )

    # 2. 推 SSE
    base = {
        "agent_id": _ORCHESTRATOR_AGENT_ID,
        "thread_id": ctx.thread_id,
        "message_id": msg.id,
    }
    block_id = gen_uuid()
    await stream_service.push_event(
        ctx.conversation_id,
        AgentStartEvent(**base, agent_name=_ORCHESTRATOR_AGENT_NAME),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStartEvent(
            **base,
            block=TextBlock(block_id=block_id, content=text),
        ),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStopEvent(**base, block_id=block_id),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        AgentDoneEvent(**base),
    )

    return {"message_id": msg.id}


@register_tool(
    name="request_user_clarification",
    description="向用户提问澄清,本轮挂起等待回复。",
    input_model=RequestUserClarificationInput,
)
async def request_user_clarification(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    向用户提澄清问题。

    顺序:落库 + mark_suspended **先于** SSE 推送。
    若反过来:用户已经看到消息,但 mark_suspended commit 失败 → 主 loop 没挂起,
    下一轮会再次决策可能造成重复消息。先把 DB 状态钉死,SSE 失败最坏只是用户没收到通知
    (前端可重连补)。

    注:本工具调完后主 Agent 应该 end_turn,因为没有可继续推进的子 Thread。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = RequestUserClarificationInput.model_validate(tool_input)
    question = parsed.question

    # 1. 落消息 + mark_suspended(同一个 session 里,要么都成,要么都不成)
    msg = await message_service.create_assistant_message(
        conversation_id=ctx.conversation_id,
        agent_id=_ORCHESTRATOR_AGENT_ID,
        content_blocks=[TextBlock(block_id=gen_uuid(), content=question)],
        sender=_ORCHESTRATOR_AGENT_NAME,
    )

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        await ts.mark_suspended(ctx.thread_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # 2. DB 状态确定后再推 SSE。SSE 推送失败不影响 DB 状态正确性
    base = {
        "agent_id": _ORCHESTRATOR_AGENT_ID,
        "thread_id": ctx.thread_id,
        "message_id": msg.id,
    }
    block_id = gen_uuid()
    await stream_service.push_event(
        ctx.conversation_id,
        AgentStartEvent(**base, agent_name=_ORCHESTRATOR_AGENT_NAME),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStartEvent(
            **base,
            block=TextBlock(block_id=block_id, content=question),
        ),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStopEvent(**base, block_id=block_id),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        AgentDoneEvent(**base),
    )

    return {"message_id": msg.id, "suspended": True}


@register_tool(
    name="present_task_plan_for_review",
    description="把任务计划发给用户审批,本轮挂起等用户确认后再实际派活。",
    input_model=PresentTaskPlanForReviewInput,
)
async def present_task_plan_for_review(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    向用户展示任务计划等审批。

    顺序:落库 + fire APPROVAL_REQUESTED hook + mark_suspended **先于** SSE 推送。
    若反过来:用户已看到计划,但 mark_suspended commit 失败 → 主 loop 没挂起,
    下一轮可能再次决策造成重复。先把 DB / hook 状态钉死,SSE 失败前端可重连补。

    实际"用户审批通过 / 拒绝"的回流路径走 WS(schemas/ws.py 的 ApprovalDecisionRequest),
    本工具只负责发送审批请求,不等待结果。
    """
    from backend.core.database import SessionLocal
    from backend.services.thread_service import ThreadService

    parsed = PresentTaskPlanForReviewInput.model_validate(tool_input)

    # 1. 把计划序列化成可读文本
    plan_text_lines = ["## 拟执行的任务计划\n"]
    if parsed.summary:
        plan_text_lines.append(f"{parsed.summary}\n")
    for i, task in enumerate(parsed.plan.tasks, 1):
        deps = f" (依赖: {', '.join(task.blocked_by)})" if task.blocked_by else ""
        plan_text_lines.append(f"{i}. **{task.agent_id}**{deps}\n   {task.prompt}")
    plan_text = "\n".join(plan_text_lines)

    # 2. 落消息
    msg = await message_service.create_assistant_message(
        conversation_id=ctx.conversation_id,
        agent_id=_ORCHESTRATOR_AGENT_ID,
        content_blocks=[TextBlock(block_id=gen_uuid(), content=plan_text)],
        sender=_ORCHESTRATOR_AGENT_NAME,
    )

    # 3. fire APPROVAL_REQUESTED hook + mark_suspended(DB 状态钉死)
    await hook_manager.fire(
        HookEvent.APPROVAL_REQUESTED,
        HookContext(
            event=HookEvent.APPROVAL_REQUESTED,
            trace_id=ctx.thread_id,
            user_id=ctx.user_id,
            conversation_id=ctx.conversation_id,
            thread_id=ctx.thread_id,
            message_id=msg.id,
            agent_id=_ORCHESTRATOR_AGENT_ID,
            extra={"plan": parsed.plan.model_dump(mode="json")},
        ),
    )

    session = SessionLocal()
    try:
        ts = ThreadService(session)
        await ts.mark_suspended(ctx.thread_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    # 4. DB / hook 都确定后再推 SSE
    base = {
        "agent_id": _ORCHESTRATOR_AGENT_ID,
        "thread_id": ctx.thread_id,
        "message_id": msg.id,
    }
    block_id = gen_uuid()
    await stream_service.push_event(
        ctx.conversation_id,
        AgentStartEvent(**base, agent_name=_ORCHESTRATOR_AGENT_NAME),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStartEvent(
            **base,
            block=TextBlock(block_id=block_id, content=plan_text),
        ),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        BlockStopEvent(**base, block_id=block_id),
    )
    await stream_service.push_event(
        ctx.conversation_id,
        AgentDoneEvent(**base),
    )

    return {"message_id": msg.id, "suspended": True}


# ============================================================
# D. 上下文检索 (3 个)
# ============================================================

@register_tool(
    name="read_conversation_history",
    description="拉本会话最近的消息(默认 20 条)。",
    input_model=ReadConversationHistoryInput,
)
async def read_conversation_history(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    读取会话最近 N 条消息。

    repo 返回倒序(最新在前),本工具反转为正序(早→晚)给 LLM ——
    LLM 按时间线推理需要早到晚的顺序。
    """
    parsed = ReadConversationHistoryInput.model_validate(tool_input)

    messages = await message_service.list_recent(
        ctx.conversation_id,
        limit=parsed.limit,
    )
    # repo 返回倒序,反转成正序
    messages = list(reversed(messages))

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "user_id": m.user_id,
                "agent_id": m.agent_id,
                "sender": m.sender,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    }


@register_tool(
    name="list_available_agents",
    description="列出本会话所有子 Agent 的概要(派活前用)。",
    input_model=ListAvailableAgentsInput,
)
async def list_available_agents(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """列出当前会话挂载的所有 Agent。"""
    ListAvailableAgentsInput.model_validate(tool_input)

    agents = await conversation_service.get_active_agents(ctx.conversation_id)
    return {
        "agents": [
            {
                "agent_id": a.id,
                "name": a.name,
                "description": a.description,
                "type": a.type,
                "capabilities": a.capabilities or {},
                "tags": a.tags or [],
            }
            for a in agents
        ]
    }


@register_tool(
    name="get_agent_capabilities",
    description="查某个 Agent 的详细能力(list_available_agents 不够细时用)。",
    input_model=GetAgentCapabilitiesInput,
)
async def get_agent_capabilities(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    查某 Agent 详细信息。
    [TODO/F-skill]: skill_service 实装后,这里要补返回 skills 字段。
    """
    parsed = GetAgentCapabilitiesInput.model_validate(tool_input)

    agent = await agent_service.get(parsed.agent_id)
    if agent is None:
        return {"error": f"Agent {parsed.agent_id} 不存在"}

    # system_prompt 可能很长,只给前 500 字摘要,完整内容不暴露给主 Agent
    system_prompt_preview = (agent.system_prompt or "")[:500]
    if agent.system_prompt and len(agent.system_prompt) > 500:
        system_prompt_preview += "..."

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "type": agent.type,
        "capabilities": agent.capabilities or {},
        "tags": agent.tags or [],
        "system_prompt_preview": system_prompt_preview,
        # "skills": [TODO/F-skill] skill_service.list_by_agent(agent.id),
    }


# ============================================================
# E. 文件 (4 个)
# ============================================================
# 沙箱:所有 path 必须落在 runtime/memory/{user_id}/{conversation_id}/ 下,
# 沙箱校验在 _resolve_sandbox_path 内统一做。
# 路径越界(../foo / 绝对路径 / symlink 跳出)→ ValueError → 外层 dispatch 包成 is_error。

@register_tool(
    name="create_file",
    description="新建文件(已存在会报错,要更新用 edit_file)。",
    input_model=CreateFileInput,
)
async def create_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """创建新文件,utf-8 + LF。已存在抛错。"""
    parsed = CreateFileInput.model_validate(tool_input)
    abs_path = _resolve_sandbox_path(ctx, parsed.path)

    if abs_path.exists():
        return {"error": f"文件 {parsed.path} 已存在,使用 edit_file 修改"}

    abs_path.parent.mkdir(parents=True, exist_ok=True)
    # newline='' + content 不带 CR 保证 LF 行尾,避免 Windows 上写出 CRLF
    abs_path.write_text(parsed.content, encoding="utf-8", newline="")

    return {
        "path": _relative_to_sandbox(ctx, abs_path),
        "size": len(parsed.content.encode("utf-8")),
        "old_content": "",
        "new_content": parsed.content,
    }


@register_tool(
    name="read_file",
    description="读文件内容(可选 limit 截断行数)。",
    input_model=ReadFileInput,
)
async def read_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """读取文件,limit 给定时按行切片(从头开始 N 行)。"""
    parsed = ReadFileInput.model_validate(tool_input)
    abs_path = _resolve_sandbox_path(ctx, parsed.path)

    if not abs_path.exists():
        return {"error": f"文件 {parsed.path} 不存在"}
    if not abs_path.is_file():
        return {"error": f"{parsed.path} 不是文件"}

    content = abs_path.read_text(encoding="utf-8")
    truncated = False
    if parsed.limit is not None:
        lines = content.splitlines(keepends=True)
        if len(lines) > parsed.limit:
            content = "".join(lines[: parsed.limit])
            truncated = True

    return {
        "path": _relative_to_sandbox(ctx, abs_path),
        "content": content,
        "truncated": truncated,
    }


@register_tool(
    name="edit_file",
    description="精确替换文件中的一段文字(old_text 必须在文件中唯一出现)。",
    input_model=EditFileInput,
)
async def edit_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """
    精确替换 old_text → new_text。
    - old_text 在文件中不存在 → 报错
    - old_text 出现多次 → 报错(LLM 应该补齐上下文让 old_text 唯一)
    - 替换后写回文件
    """
    parsed = EditFileInput.model_validate(tool_input)
    abs_path = _resolve_sandbox_path(ctx, parsed.path)

    if not abs_path.exists() or not abs_path.is_file():
        return {"error": f"文件 {parsed.path} 不存在"}

    content = abs_path.read_text(encoding="utf-8")
    occurrences = content.count(parsed.old_text)
    if occurrences == 0:
        return {"error": "old_text 在文件中未找到,无法替换"}
    if occurrences > 1:
        return {
            "error": (
                f"old_text 在文件中出现 {occurrences} 次,"
                "请补充周围上下文让 old_text 在文件中唯一"
            )
        }

    new_content = content.replace(parsed.old_text, parsed.new_text, 1)
    abs_path.write_text(new_content, encoding="utf-8", newline="")

    return {
        "path": _relative_to_sandbox(ctx, abs_path),
        "replaced": True,
        "old_content": content,
        "new_content": new_content,
    }


@register_tool(
    name="list_directory",
    description="列出目录下的文件和子目录。",
    input_model=ListDirectoryInput,
)
async def list_directory(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """列目录条目,不递归。"""
    parsed = ListDirectoryInput.model_validate(tool_input)
    abs_path = _resolve_sandbox_path(ctx, parsed.path)

    if not abs_path.exists():
        return {"error": f"目录 {parsed.path} 不存在"}
    if not abs_path.is_dir():
        return {"error": f"{parsed.path} 不是目录"}

    entries: list[dict[str, Any]] = []
    for child in sorted(abs_path.iterdir()):
        try:
            if child.is_dir():
                entries.append({
                    "name": child.name,
                    "type": "dir",
                })
            else:
                entries.append({
                    "name": child.name,
                    "type": "file",
                    "size": child.stat().st_size,
                })
        except OSError:
            # 某个 entry stat 失败时跳过,不让整次列目录失败
            continue

    return {
        "path": _relative_to_sandbox(ctx, abs_path),
        "entries": entries,
    }
