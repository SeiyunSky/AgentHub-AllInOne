"""
SystemPromptBuilder —— 主 Agent System Prompt 六层管道

1. 核心指令      (静态)
2. 工具列表      (静态)
3. Skill 元数据  (静态,progressive disclosure)
4. CLAUDE.md 链  (静态)
   --- DYNAMIC_BOUNDARY ---
5. 长期记忆      (动态,按相关性筛选 top-K)
6. 动态上下文    (动态,会话历史 / 可用 Agent / 任务图)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from dataclasses import dataclass


DYNAMIC_BOUNDARY = "\n\n----- DYNAMIC -----\n\n"


@dataclass
class PromptContext:
    """构建 Prompt 时调用方传入的上下文。"""
    user_id: str
    conversation_id: str
    thread_id: str
    available_agent_ids: list[str]


class SystemPromptBuilder:
    """主 Agent System Prompt 六层管道组装器。"""

    async def build(self, ctx: PromptContext) -> str:
        """
        组装完整 System Prompt。
        TODO[F-prompt]: 实装六层组装,目前返回最小可跑核心指令。
        """
        # TODO[F-prompt-1]: 核心指令(从 prompts/orchestrator.md 加载)
        # TODO[F-prompt-2]: 工具列表(orchestrator_tools 19 个 + MCP 动态)
        # TODO[F-prompt-3]: Skill 元数据(主 Agent 自挂 Skill description 列表)
        # TODO[F-prompt-4]: CLAUDE.md 链(用户全局 + 项目 + 子目录)
        # TODO[F-prompt-5]: 长期记忆(memory_service.list_index → 按相关性挑 top-K)
        # TODO[F-prompt-6]: 动态上下文(会话历史 + 可用 Agent 列表 + 任务图状态)
        raise NotImplementedError(
            "[TODO/F-prompt] SystemPromptBuilder.build 未实装,"
            "需要按设计文档第八节实现六层组装"
        )


prompt_builder = SystemPromptBuilder()
