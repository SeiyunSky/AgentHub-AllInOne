"""
threads 相关 Pydantic DTO

对应数据结构设计文档第 8 节 threads 表 + 主 Agent 设计第十二节(主 Agent loop)。

涵盖五类 DTO:
1. 枚举 —— ThreadStatus
2. 嵌套结构 —— ThreadCheckpoint(主 Agent 短期记忆,checkpoint JSON 字段反序列化目标) /
              DispatchedThreadInfo / ReceivedResultInfo
3. 任务图 —— TaskPlanItem(主 Agent create_task_plan 工具单条任务) / TaskPlan(任务列表)
4. 内部 DTO —— ThreadCreate / ThreadUpdate(service 层创建 / 更新)
5. API DTO —— ThreadResponse(主 Agent read_thread_status / read_thread_result 工具返回)

关键约定:
- ThreadStatus 含 cancelled 状态,用于"用户中止当前轮"或"队列下一轮抢占"场景。
- ThreadCheckpoint 字段全强类型化,避免 dict[str, Any] 黑盒;字段含义见主 Agent 设计第十二节。
- TaskPlanItem.id 由调用方提前生成 UUID,blocked_by 引用其他 task 的 id。
- ThreadUpdate 所有字段 Optional 默认 None,partial update 模式。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.message import MessageInHistory


# ============================================================
# 枚举
# ============================================================

class ThreadStatus(str, Enum):
    """Thread 执行状态机"""
    INIT = "init"
    RUNNING = "running"
    SUSPENDED = "suspended"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"


# ============================================================
# Checkpoint 嵌套结构
# ============================================================

class DispatchedThreadInfo(BaseModel):
    """主 Agent 已派发的子 Thread 摘要(含状态)"""

    thread_id: str
    agent_id: str
    status: ThreadStatus


class ReceivedResultInfo(BaseModel):
    """主 Agent 已收到的子 Thread 结果摘要"""

    thread_id: str = Field(description="对应 DispatchedThreadInfo.thread_id")
    summary: str = Field(description="子 Thread 输出的摘要;完整正文按需调 read_thread_result(thread_id)")


class ThreadCheckpoint(BaseModel):
    """
    Thread 短期记忆的结构化形态。
    对应数据库 threads.checkpoint JSON 字段,主 Agent loop 每轮结束持久化一次。

    主 Agent 与子 Agent 通用同一结构;子 Agent 不会有 dispatched_threads / received_results
    字段(默认空列表)。
    """

    messages_history: list[MessageInHistory] = Field(
        default_factory=list,
        description="对话历史(LLM 上下文,含 tool_use / tool_result 序列)",
    )
    dispatched_threads: list[DispatchedThreadInfo] = Field(
        default_factory=list,
        description="主 Agent 派发的子 Thread 列表(主 Agent 专用)",
    )
    received_results: list[ReceivedResultInfo] = Field(
        default_factory=list,
        description="主 Agent 已收到的子 Thread 结果摘要(主 Agent 专用)",
    )
    current_step: Optional[str] = Field(
        default=None,
        description="当前步骤描述,如 'waiting_approval' / 'waiting_for_t_xxx'",
    )
    tokens_used: int = Field(
        default=0,
        description=(
            "当前活跃 context 的 token 数,用于压缩判定(超阈值触发摘要)。"
            "压缩后被重置为摘要后的 token 数;与 threads.tokens_total(累计消耗,只增不减)不同。"
        ),
    )


# ============================================================
# 任务图
# ============================================================

class TaskPlanItem(BaseModel):
    """
    主 Agent create_task_plan 工具单条任务。
    一个 TaskPlanItem 落地为一行 threads 表记录;blocked_by 引用其他 task 的 id。
    """

    id: str = Field(description="调用方提前生成的 task_id (UUID),用于 blocked_by 引用")
    agent_id: str = Field(description="派给哪个 Agent")
    prompt: str = Field(description="给该 Agent 的特化指令")
    role_hint: Optional[str] = Field(
        default=None,
        description="任务角色提示,如 '后端' / '前端' / 'QA',前端展示用",
    )
    blocked_by: list[str] = Field(
        default_factory=list,
        description="依赖的 task_id 数组;全部 done 后该 task 才解锁启动",
    )


class TaskPlan(BaseModel):
    """主 Agent 提交的完整任务计划"""

    tasks: list[TaskPlanItem]


# ============================================================
# 内部 DTO
# ============================================================

class ThreadCreate(BaseModel):
    """
    thread_service.create_thread 入参。
    id 可选,调用方可提前生成 UUID(用于 TaskPlanItem 的 blocked_by 引用),
    repo 层在 id 为空时自动生成。
    """

    id: Optional[str] = None
    conversation_id: str
    message_id: str = Field(description="触发本 Thread 的用户消息 ID")
    agent_id: str
    blocked_by: list[str] = Field(
        default_factory=list,
        description="依赖的 thread_id 数组",
    )


class ThreadUpdate(BaseModel):
    """
    thread_service 内部更新 Thread。
    所有字段 Optional 默认 None,service 用 model_dump(exclude_unset=True) 取被显式传的字段。
    """

    status: Optional[ThreadStatus] = None
    checkpoint: Optional[ThreadCheckpoint] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    tokens_total: Optional[int] = None


# ============================================================
# API / 工具返回 DTO
# ============================================================

class ThreadResponse(BaseModel):
    """
    主 Agent read_thread_status / read_thread_result 工具返回的形态。

    重要约定:
    - 调用方(主 Agent)默认应使用 result_summary 字段获取该 Thread 的简短摘要,
      只在确需详情时才解析 checkpoint(messages_history 可能数万 tokens,
      直接注入 context 会撑爆)。
    - orchestrator_service 在事件回注主 Agent 时,只把 result_summary 塞进
      messages_history,checkpoint 不进 context。
    - tokens_total 是累计消耗(只增不减),与 ThreadCheckpoint.tokens_used
      (当前活跃 context 的 token 数,可被压缩重置)分工不同。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    message_id: str
    agent_id: str
    status: ThreadStatus
    result_summary: Optional[str] = Field(
        default=None,
        description="该 Thread 的简短摘要(done 时由 orchestrator_service / Adapter 生成),主 Agent 默认读这个",
    )
    checkpoint: Optional[ThreadCheckpoint] = Field(
        default=None,
        description="完整 checkpoint;按需读取,通常只在需要详情时使用",
    )
    blocked_by: list[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    tokens_total: int = Field(
        default=0,
        description="累计 token 消耗(输入+输出),只增不减,用于审计和成本统计",
    )
    created_at: datetime
    updated_at: datetime
