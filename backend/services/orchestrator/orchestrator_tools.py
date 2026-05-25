"""
orchestrator_tools —— 主 Agent 19 个内置工具的 Handler 注册

Input Schema 唯一真相源在 backend.schemas.orchestrator_tools(A 阶段定的契约),
本文件只负责把每个 schema 挂上 @register_tool 装饰器,并提供 stub handler。
真实装在 C 阶段补完。

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

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from __future__ import annotations

from typing import Any

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
from backend.services.orchestrator.tool_registry import (
    ToolContext,
    register_tool,
)


# ============================================================
# A. 任务调度 (4 个)
# ============================================================

@register_tool(
    name="dispatch_to_agent",
    description=(
        "异步派任务给某个 Agent,可声明依赖。立即启动该 Thread,返回 thread_id;"
        "Thread 完成时通过事件回注主 Agent context。与 add_task 区别:"
        "dispatch_to_agent 立即启动,add_task 仅加入任务图等待调度。"
    ),
    input_model=DispatchToAgentInput,
)
async def dispatch_to_agent(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-1] thread_service.create_thread + schedule_conversation,返回 thread_id。"""
    raise NotImplementedError("[TODO/C-tool-1] dispatch_to_agent 未实装")


@register_tool(
    name="read_thread_status",
    description="查 Thread 当前状态(init/running/suspended/done/error/cancelled)。",
    input_model=ReadThreadStatusInput,
)
async def read_thread_status(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-2] thread_repo.get(thread_id) → 返回 status / agent_id / blocked_by。"""
    raise NotImplementedError("[TODO/C-tool-2] read_thread_status 未实装")


@register_tool(
    name="read_thread_result",
    description="读取 Thread 完整结果(含中间产物)。",
    input_model=ReadThreadResultInput,
)
async def read_thread_result(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-3] thread_repo.get + load_checkpoint,返回 ThreadResponse 形态。"""
    raise NotImplementedError("[TODO/C-tool-3] read_thread_result 未实装")


@register_tool(
    name="cancel_thread",
    description="主动中止某个子 Thread(配合 cancel_dependents 传播取消)。",
    input_model=CancelThreadInput,
)
async def cancel_thread(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-4] thread_service.cancel_thread + cancel_dependents。"""
    raise NotImplementedError("[TODO/C-tool-4] cancel_thread 未实装")


# ============================================================
# B. 任务链管理 (5 个)
# ============================================================

@register_tool(
    name="create_task_plan",
    description="创建结构化任务计划(含依赖图)落地到 threads 表。",
    input_model=CreateTaskPlanInput,
)
async def create_task_plan(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-5] thread_service.create_task_plan,触发 schedule_conversation。"""
    raise NotImplementedError("[TODO/C-tool-5] create_task_plan 未实装")


@register_tool(
    name="update_task_status",
    description=(
        "更新任务状态。主 Agent 仅可把任务标为 cancelled(主动放弃执行);"
        "其他状态由 thread_service / Adapter 自动管理。"
    ),
    input_model=UpdateTaskStatusInput,
)
async def update_task_status(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-6] thread_service.cancel_thread(主 Agent 只能改成 cancelled)。"""
    raise NotImplementedError("[TODO/C-tool-6] update_task_status 未实装")


@register_tool(
    name="read_task_plan",
    description="读取当前轮次的完整任务图(threads 表里同 message_id 的所有行)。",
    input_model=ReadTaskPlanInput,
)
async def read_task_plan(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-7] thread_repo.list_by_message(ctx.user_message_id)。"""
    raise NotImplementedError("[TODO/C-tool-7] read_task_plan 未实装")


@register_tool(
    name="add_task",
    description=(
        "往当前任务图追加任务节点(blocked_by 满足后由调度器统一启动)。"
        "与 dispatch_to_agent 区别见 schema 注释。"
    ),
    input_model=AddTaskInput,
)
async def add_task(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-8] thread_service.add_task,触发 schedule_conversation。"""
    raise NotImplementedError("[TODO/C-tool-8] add_task 未实装")


@register_tool(
    name="remove_task",
    description="运行中移除尚未启动的任务(仅支持 status=init)。",
    input_model=RemoveTaskInput,
)
async def remove_task(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-9] thread_service.remove_task,返回是否成功。"""
    raise NotImplementedError("[TODO/C-tool-9] remove_task 未实装")


# ============================================================
# C. 用户交互 (3 个)
# ============================================================

@register_tool(
    name="respond_to_user",
    description="直接给用户回话(不走子 Agent)。整轮可多次调用,最终触发 round_done。",
    input_model=RespondToUserInput,
)
async def respond_to_user(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-10] message_service.create_assistant_message + stream_service.push_event。"""
    raise NotImplementedError("[TODO/C-tool-10] respond_to_user 未实装")


@register_tool(
    name="request_user_clarification",
    description="主动问用户澄清问题(暂停整轮等待用户回复)。",
    input_model=RequestUserClarificationInput,
)
async def request_user_clarification(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-11] mark_suspended + push 'awaiting_user' SSE event,主 Agent loop 暂停。"""
    raise NotImplementedError("[TODO/C-tool-11] request_user_clarification 未实装")


@register_tool(
    name="present_task_plan_for_review",
    description="向用户展示拟执行的任务计划,等用户批准后再 dispatch。",
    input_model=PresentTaskPlanForReviewInput,
)
async def present_task_plan_for_review(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-12] mark_suspended + push 'awaiting_approval',hook_manager 触发审批 hook。"""
    raise NotImplementedError("[TODO/C-tool-12] present_task_plan_for_review 未实装")


# ============================================================
# D. 上下文检索 (3 个)
# ============================================================

@register_tool(
    name="read_conversation_history",
    description="读取当前会话最近 N 条消息(避开重复加载完整历史撑爆 context)。",
    input_model=ReadConversationHistoryInput,
)
async def read_conversation_history(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-13] message_service.list_recent(conversation_id, limit)。"""
    raise NotImplementedError("[TODO/C-tool-13] read_conversation_history 未实装")


@register_tool(
    name="list_available_agents",
    description="列出当前会话挂载的所有 Agent + 能力概要。",
    input_model=ListAvailableAgentsInput,
)
async def list_available_agents(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-14] conversation_service.get + agent_service.list_by_ids。"""
    raise NotImplementedError("[TODO/C-tool-14] list_available_agents 未实装")


@register_tool(
    name="get_agent_capabilities",
    description="查某个 Agent 的详细能力(capabilities / tags / skills)。",
    input_model=GetAgentCapabilitiesInput,
)
async def get_agent_capabilities(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-15] agent_service.get(agent_id) + skill_service.list_by_agent。"""
    raise NotImplementedError("[TODO/C-tool-15] get_agent_capabilities 未实装")


# ============================================================
# E. 文件 (4 个)
# ============================================================
# 工作目录约束:所有路径必须落在 runtime/memory/{user_id}/{conversation_id}/ 下,
# path_traversal 防护在 file_service 层做(core/utils.safe_join + 校验)。

@register_tool(
    name="create_file",
    description="创建新文件(任务说明 / 阶段总结 / 计划文档 / 新记忆)。已存在则报错。",
    input_model=CreateFileInput,
)
async def create_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-16] file_service.create(safe_join + utf-8 + LF)。"""
    raise NotImplementedError("[TODO/C-tool-16] create_file 未实装")


@register_tool(
    name="read_file",
    description="读取文件(子 Agent 产出 / 记忆文件)。limit 可选,大文件按行截断。",
    input_model=ReadFileInput,
)
async def read_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-17] file_service.read,limit 给定时按行切片。"""
    raise NotImplementedError("[TODO/C-tool-17] read_file 未实装")


@register_tool(
    name="edit_file",
    description="精确替换文件中一段文字(编辑 MEMORY.md / 记忆文件)。old_text 不唯一时报错。",
    input_model=EditFileInput,
)
async def edit_file(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-18] file_service.edit,old_text 不唯一 / 找不到都返错。"""
    raise NotImplementedError("[TODO/C-tool-18] edit_file 未实装")


@register_tool(
    name="list_directory",
    description="列目录(探索记忆目录 / 浏览子 Agent 产出)。返回文件 / 子目录列表。",
    input_model=ListDirectoryInput,
)
async def list_directory(tool_input: dict[str, Any], *, ctx: ToolContext) -> dict[str, Any]:
    """[TODO/C-tool-19] file_service.list_dir,返回 [{name, type, size}, ...]。"""
    raise NotImplementedError("[TODO/C-tool-19] list_directory 未实装")
