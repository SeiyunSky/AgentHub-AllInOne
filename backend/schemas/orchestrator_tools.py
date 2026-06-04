"""
主 Agent (Orchestrator) 19 个内置工具的 input schema

对应主 Agent 设计第五节的工具列表。每个工具一个 Pydantic class,定义 LLM 调用工具时
input 字段的形态。Python tool handler 用对应类反序列化并校验入参。

按组分:
A. 任务调度(4)        DispatchToAgent / ReadThreadStatus / ReadThreadResult / CancelThread
B. 任务链管理(5)      CreateTaskPlan / UpdateTaskStatus / ReadTaskPlan / AddTask / RemoveTask
C. 用户交互(3)        RespondToUser / RequestUserClarification / PresentTaskPlanForReview
D. 上下文检索(3)      ReadConversationHistory / ListAvailableAgents / GetAgentCapabilities
E. 文件(4)            CreateFile / ReadFile / EditFile / ListDirectory

约定:
- 每个工具的入参类命名为 {ToolName}Input(驼峰),即使是无参数的工具也定义空类,
  让 LLM 看到的 schema 一致。
- 路径 / 内容的"沙箱校验"由 tool handler 实现,DTO 层只做基础非空与格式校验。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.thread import TaskPlan


# ============================================================
# A. 任务调度
# ============================================================

class DispatchToAgentInput(BaseModel):
    """
    异步派任务给某个 Agent,**立即启动**该 Thread,返回 thread_id。

    与 AddTaskInput 区别:
    - dispatch_to_agent —— 即时派发启动,适合单点派活、临时补救场景。
    - add_task —— 往当前任务图追加节点(不立即启动,blocked_by 满足后才启动),
                  适合扩展已存在的 TaskPlan。
    """

    agent_id: str = Field(description="目标 Agent ID")
    prompt: str = Field(description="给该 Agent 的特化指令")
    role_hint: Optional[str] = Field(
        default=None,
        description="任务角色提示,如 '后端' / '前端' / 'QA'",
    )
    blocked_by: list[str] = Field(
        default_factory=list,
        description="依赖的 thread_id 数组,全部 done 后才解锁启动",
    )


class ReadThreadStatusInput(BaseModel):
    """查 Thread 当前状态(init/running/suspended/done/error/cancelled)"""

    thread_id: str


class ReadThreadResultInput(BaseModel):
    """读取 Thread 完整结果(含中间产物)"""

    thread_id: str


class CancelThreadInput(BaseModel):
    """主动中止某个子 Thread"""

    thread_id: str


# ============================================================
# B. 任务链管理
# ============================================================

class CreateTaskPlanInput(BaseModel):
    """
    创建结构化任务计划(含依赖图)落地到 threads 表。
    每个 TaskPlanItem 形成一行 Thread 记录。
    """

    plan: TaskPlan


class UpdateTaskStatusInput(BaseModel):
    """
    更新任务状态。

    主 Agent 只允许把任务标记为 cancelled(主动放弃执行);
    其他状态(init/running/suspended/done/error)由 thread_service / Adapter 自动管理,
    主 Agent 不应直接操作。
    """

    task_id: str = Field(description="对应 thread_id")
    status: Literal["cancelled"] = Field(
        description="目标状态,主 Agent 仅可设为 cancelled",
    )


class ReadTaskPlanInput(BaseModel):
    """读取当前轮次的完整任务图(无入参)"""
    pass


class AddTaskInput(BaseModel):
    """
    往当前任务图**追加**任务节点。

    与 DispatchToAgentInput 区别:
    - add_task —— 加入任务图等待调度(blocked_by 满足后由调度器统一启动)
    - dispatch_to_agent —— 立即启动 Thread

    适用场景:运行中发现需要补一个新任务,且该任务依赖某些已存在的 task_id。
    """

    agent_id: str
    prompt: str
    role_hint: Optional[str] = None
    blocked_by: list[str] = Field(default_factory=list)


class RemoveTaskInput(BaseModel):
    """运行中移除尚未启动的任务"""

    task_id: str = Field(description="对应 thread_id;仅支持 status=init 的任务")


# ============================================================
# C. 用户交互
# ============================================================

class RespondToUserInput(BaseModel):
    """直接给用户回话(不走子 Agent)"""

    message: str = Field(description="给用户的最终回复内容")


class RequestUserClarificationInput(BaseModel):
    """主动问用户澄清问题(暂停整轮等待用户回复)"""

    question: str = Field(description="向用户提出的澄清问题")


class PresentTaskPlanForReviewInput(BaseModel):
    """向用户展示拟执行的任务计划,等用户批准"""

    plan: TaskPlan
    summary: Optional[str] = Field(
        default=None,
        description="计划的简短说明,放在任务列表前展示给用户",
    )


# ============================================================
# D. 上下文检索
# ============================================================

class ReadConversationHistoryInput(BaseModel):
    """读取当前会话最近 N 条消息"""

    limit: int = Field(
        default=20,
        ge=1,
        le=200,
        description="最多返回的消息条数,默认 20",
    )


class ListAvailableAgentsInput(BaseModel):
    """列出当前会话挂载的所有 Agent + 能力(无入参)"""
    pass


class GetAgentCapabilitiesInput(BaseModel):
    """查某个 Agent 的详细能力"""

    agent_id: str


# ============================================================
# E. 文件
# ============================================================

class CreateFileInput(BaseModel):
    """创建新文件(任务说明 / 阶段总结 / 计划文档 / 新记忆)"""

    path: str = Field(description="目标文件路径(沙箱校验在 handler 中执行)")
    content: str = Field(description="文件完整内容")


class ReadFileInput(BaseModel):
    """读取文件"""

    path: str = Field(description="目标文件路径")
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        description="最多返回的行数;不传表示读完整文件",
    )


class EditFileInput(BaseModel):
    """精确替换文件中一段文字(原子操作,old_text 不存在则报错不写)"""

    path: str = Field(description="目标文件路径")
    old_text: str = Field(description="要被替换的原始文本(精确匹配)")
    new_text: str = Field(description="替换后的文本")


class ListDirectoryInput(BaseModel):
    """列目录(探索记忆目录 / 浏览子 Agent 产出)"""

    path: str = Field(description="目录路径")


# ============================================================
# F. 部署
# ============================================================

class DeployAppInput(BaseModel):
    """部署沙箱里的 Python 应用到 AgentHub 内置 Docker 容器,返回可访问 URL"""

    entry_point: str = Field(
        default="app.py",
        description="入口文件名(沙箱根目录下相对路径),默认 app.py。容器内会跑 "
                    "uvicorn {entry_module}:app --host 0.0.0.0 --port 8000",
    )
