"""
AgentAdapter 抽象基类

定义所有 Adapter 必须遵守的统一接口,屏蔽底层 SDK 差异
(Anthropic Python SDK / Codex MCP 子进程 / OpenAI 兼容 HTTP / OpenCode CLI)。

主 Agent 与 stream_service 不关心 Adapter 的具体实现,
只通过本文件定义的 stream() 接口调用并消费 AgentEvent 流。

任何新 Adapter 都需要:
1. 继承 AgentAdapter
2. 实现 stream() —— 把底层 SDK 输出转换成 AgentEvent yield 出去
3. 实现 get_capabilities() —— 声明该 Adapter 是否支持 diff / 审批等特性

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-22
修改者:Musuyin
修改日期:2026-05-25
"""

from abc import ABC, abstractmethod
from asyncio import Event
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from backend.adapters.events import AgentEvent
from backend.domain.agent import AgentCapabilities
from backend.schemas.message import MessageInHistory
from backend.schemas.skill import SkillWithContent


# ============================================================
# stream() 入参
# ============================================================

@dataclass
class StreamInput:
    """
    Adapter.stream() 的入参。

    用 dataclass 而非 BaseModel:
    - 含 asyncio.Event 等运行时对象,Pydantic 序列化不友好
    - 调用方主要在 service 内部组装,不跨 HTTP 边界,无需序列化

    字段来源:
    - agent_id / thread_id / message_id —— 由主 Agent / thread_service 注入
    - prompt —— 主 Agent dispatch_to_agent 工具调用时传入
    - history —— 由 thread_service 从 messages 表查出并裁剪
    - system_prompt —— 由 prompt_service 按 agent_id 加载组装(主 Agent 自己的六层管道
                       由 orchestrator_service 单独组装,不走这个字段)
    - skills —— 由 skill_service 查 agent_skills 关联表后加载正文
    - cancel_event —— stream_service 维护的 abort 信号;用户点停止 / 排队下一轮中断时触发
    """

    agent_id: str
    thread_id: str
    message_id: str
    prompt: str
    agent_name: str = ""
    agent_avatar: Optional[str] = None
    history: list[MessageInHistory] = field(default_factory=list)
    system_prompt: Optional[str] = None
    skills: list[SkillWithContent] = field(default_factory=list)
    cancel_event: Optional[Event] = None
    user_id: Optional[str] = None


# ============================================================
# 抽象基类
# ============================================================

class AgentAdapter(ABC):
    """
    所有 Adapter 的统一接口。

    每个具体 Adapter(Claude / Codex / OpenCode / Custom)继承本类,
    实现 stream() 与 get_capabilities() 两个方法。

    实例化时机:
    - 系统启动时由 adapters.registry 按配置创建并缓存
    - 同一个 Adapter 实例可服务多个 Agent(通过 stream() 入参 agent_id 区分),
      所以 Adapter 内部不应保存"当前 agent"的状态,所有上下文走 StreamInput 传递。
    """

    @abstractmethod
    async def stream(self, inp: StreamInput) -> AsyncIterator[AgentEvent]:
        """
        启动一次流式生成,按时间顺序 yield AgentEvent。

        约定:
        1. 第一个事件应为 AgentStartEvent(message_id 来自 inp.message_id)
        2. 中间通过块级流式协议产出内容:
           BlockStartEvent(创建块) → BlockDeltaEvent(增量更新) → BlockStopEvent(块结束)
           可穿插多个不同 block_id 的块(thinking / tool_use / code / text / approval / ...)
        3. 正常结束 yield AgentDoneEvent;出错 yield AgentErrorEvent
        4. 所有事件的 agent_id / thread_id / message_id 必须填充自 inp 对应字段
        5. 周期性检查 inp.cancel_event,被 set 时优雅退出(可补一个 AgentErrorEvent
           或直接结束生成,由实现方决定但需保证不留资源)

        实现方应定义为 async generator(`async def` + `yield`),返回类型自动满足
        AsyncIterator[AgentEvent]。外层主 Agent 用 `async for event in adapter.stream(inp):` 消费。
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> AgentCapabilities:
        """
        声明 Adapter 自身的能力。

        前端据此决定渲染哪些 UI 控件(如 supports_diff=False 时不展示 Diff 应用按钮);
        主 Agent 据此判断派活时是否合理(避免把"需要审批的危险任务"派给不支持审批的 Adapter)。
        """
        ...
