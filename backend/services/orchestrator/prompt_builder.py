"""
SystemPromptBuilder —— 主 Agent System Prompt 六层管道

1. 核心指令      (静态)  —— prompts/orchestrator.md
2. 工具列表      (静态)  —— anthropic SDK 通过 tools= 参数传,prompt 不重复
3. Skill 元数据  (静态,progressive disclosure)
4. CLAUDE.md 链  (静态)
   --- DYNAMIC_BOUNDARY ---
5. 长期记忆      (动态,按相关性筛选 top-K)
6. 动态上下文    (动态,会话历史 / 可用 Agent / 任务图)

MVP 阶段只实装第 1 层。
- 第 2 层不在 prompt 里重复——LLM 看 tools schema 已经能拿到 name/description/input_schema,
  在 prompt 里再说一遍是浪费 token,且容易和 schema 不一致
- 第 3-6 层各依赖一个还没接通的 service,留 stub 返回空字符串。每层等对应依赖落地后回来补,
  本文件接口签名稳定,后续实装不影响调用方

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from backend.services.memory_service import list_index


logger = logging.getLogger(__name__)


DYNAMIC_BOUNDARY = "\n\n----- DYNAMIC -----\n\n"

# 第 1 层 prompt 文件位置 —— backend/prompts/orchestrator.md
# 路径相对本文件:services/orchestrator/prompt_builder.py → 上三级 → backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_ORCHESTRATOR_PROMPT_PATH = _BACKEND_ROOT / "prompts" / "orchestrator.md"

# 第 4 层 AGENTHUB.md 加载链:项目根 + 部署 cwd
# - 项目根 AGENTHUB.md:跟代码 git 版本化,团队共享
# - 部署 cwd AGENTHUB.md:运维覆盖用,不入 git
# 跨平台用 Path 即可,Windows / macOS / Linux 都正确
_PROJECT_ROOT = _BACKEND_ROOT.parent
_AGENTHUB_MD_FILENAME = "AGENTHUB.md"

# 第 6 层(动态上下文)滑动窗口与摘要参数
# - 会话历史最近 N 条作为入口,更早的让 LLM 调 read_conversation_history 工具按需拉
# - N 与工具默认 limit 对齐,LLM 看到的"默认窗口"前后一致
# - 单条消息按字符截断,只为给 LLM 看出意图;详情让它调工具
_HISTORY_RECENT_LIMIT = 20
_HISTORY_TEXT_PER_MSG_CHARS = 300


@dataclass
class PromptContext:
    """构建 Prompt 时调用方传入的上下文。"""
    user_id: str
    conversation_id: str
    thread_id: str
    user_message_id: str
    available_agent_ids: list[str]


class SystemPromptBuilder:
    """主 Agent System Prompt 六层管道组装器。"""

    def __init__(self, prompt_path: Path | None = None) -> None:
        # 默认用模块级常量,允许测试 / 多版本 prompt 场景注入自定义路径
        self._prompt_path = prompt_path or _ORCHESTRATOR_PROMPT_PATH
        # TODO[F-prompt-cache]: _core_instructions_cache 是实例属性,但 prompt_builder
        # 是模块级单例(本文件底部),所有请求共享同一份缓存。
        # MVP 阶段不影响——orchestrator.md 内容不会运行期变;但如果未来:
        # - 测试注入不同 prompt_path
        # - 多租户需要不同 prompt
        # 单例会导致第一次缓存后所有请求都用同一份。届时改成"按 prompt_path 做 key 的字典"
        # 或干脆每次 build 重读(orchestrator.md 不大,IO 开销可接受)。
        self._core_instructions_cache: str | None = None

    async def build(self, ctx: PromptContext) -> str:
        """
        组装完整 System Prompt(便捷入口)。

        长循环场景(主 Agent loop)推荐分别调 build_static / build_dynamic,
        把 build_static 的结果缓存到 loop 局部变量,每轮只重新算 build_dynamic。
        本方法每次都全量构建,适合一次性场景。
        """
        static_part = await self.build_static(ctx)
        dynamic_part = await self.build_dynamic(ctx)

        if static_part and dynamic_part:
            return static_part + DYNAMIC_BOUNDARY + dynamic_part
        return static_part or dynamic_part

    async def build_static(self, ctx: PromptContext) -> str:
        """
        构建静态层(1-4)。loop 跑期间不变,调用方应缓存结果。

        注:文件 IO(orchestrator.md / AGENTHUB.md)在这里发生。
        每次调用都重读;调用方在长循环里需要自己缓存避免重复 IO。
        """
        layers = [
            await self._layer_1_core_instructions(),
            await self._layer_2_tools_summary(),
            await self._layer_3_skill_metadata(ctx),
            await self._layer_4_agenthub_md_chain(ctx),
        ]
        return "\n\n".join(s for s in layers if s)

    async def build_dynamic(self, ctx: PromptContext) -> str:
        """
        构建动态层(5-6)。loop 每轮重新调用——长期记忆 / 任务图状态可能变。
        """
        layers = [
            await self._layer_5_long_term_memory(ctx),
            await self._layer_6_dynamic_context(ctx),
        ]
        return "\n\n".join(s for s in layers if s)

    # --------------------------------------------------------
    # 静态层
    # --------------------------------------------------------

    async def _layer_1_core_instructions(self) -> str:
        """
        第 1 层:核心指令——prompts/orchestrator.md 完整内容。

        读一次缓存住——文件只在进程启动时变化,运行期不会改,缓存可以省 IO。
        """
        if self._core_instructions_cache is None:
            try:
                self._core_instructions_cache = self._prompt_path.read_text(
                    encoding="utf-8"
                )
            except FileNotFoundError:
                logger.error(
                    "orchestrator.md 不存在: %s——主 Agent loop 将无核心指令",
                    self._prompt_path,
                )
                self._core_instructions_cache = ""
        return self._core_instructions_cache

    async def _layer_2_tools_summary(self) -> str:
        """
        第 2 层:工具列表。

        **设计决策:本层返回空字符串,工具信息走 anthropic SDK 的 tools= 参数下发**。
        理由:
        - LLM 调 tools schema 已经能拿到 name/description/input_schema
        - 在 prompt 里再列一遍是重复,占 ~3K token
        - 重复更新易和 schema 不一致(改了 schema 忘了改 prompt)
        """
        return ""

    async def _layer_3_skill_metadata(self, ctx: PromptContext) -> str:
        """
        第 3 层:Skill 元数据(progressive disclosure)。

        现状:返回空字符串,等 skill_service 实装后接通。

        TODO[F-prompt-3]: 实装时返回 markdown 列表:
            ## 可用 Skill 列表
            - **{name}**: {description}
            - ...
            (主 Agent 看完描述后,需要用某个 Skill 调 read_file/load_skill 拿完整正文)

        待定的设计点(动手前必须先和团队对齐):

        1. **数据源**:DB 为权威 + 本地文件为缓存
           - 用户创建的 Skill 写入 skills 表(元数据)+ skills/{name}.md(正文)
           - 用户删本地 .md 文件不丢数据,可从 DB 重新生成本地副本
           - skill_service 应提供 list_for_orchestrator() 屏蔽来源细节

        2. **主 Agent 挂载机制**:复用 agent_skills 多对多表
           - 约定主 Agent 用 agent_id='orchestrator' 注册到 agents 表(seed 阶段)
           - skill_service.list_for_orchestrator() 等价于
             list_by_agent_id('orchestrator'),按 active+is_public/作者过滤
           - 不引入"orchestrator 专属目录"的隐式约定,避免文件系统 / DB 双标识不一致

        3. **用户创建路径**:
           - is_public=1 + author=GUGA 视为系统内置,所有主 Agent 默认可见
           - is_public=0 仅 author 自己可见;主 Agent 在 ctx.user_id 视角下加载
           - 实装 list_for_orchestrator(user_id) 时要带 user_id 做可见性过滤

        依赖:
        - skill_service 实装(services/skill_service.py 当前是 # TODO stub)
        - skill_repo 实装(repositories/skill_repo.py 当前是 # TODO stub)
        - agents 表 seed 主 Agent 行(agent_id='orchestrator')
        """
        return ""

    async def _layer_4_agenthub_md_chain(self, ctx: PromptContext) -> str:
        """
        第 4 层:AGENTHUB.md 链 —— 部署级全局指令。

        加载顺序(后者覆盖前者优先级,在 prompt 里"后写优先"——LLM 通常更看后段):
        1. 项目根 {project_root}/AGENTHUB.md       —— git 版本化,团队共享
        2. 部署 cwd {cwd}/AGENTHUB.md              —— 运维覆盖,不入 git

        多租户 IM 场景下用户个人偏好走第 5 层长期记忆,不在本层。
        """
        paths = [
            _PROJECT_ROOT / _AGENTHUB_MD_FILENAME,    # 项目根
            Path.cwd() / _AGENTHUB_MD_FILENAME,       # 部署 cwd
        ]
        # 用 resolve() 去重——cwd 跟项目根重合时不重复加载
        # 检查存在 / 读文件也用 resolved,统一处理符号链接(避免读到符号链接前的"假"文件)
        seen: set[Path] = set()
        parts: list[str] = []
        for p in paths:
            try:
                resolved = p.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if not resolved.exists():
                continue
            try:
                parts.append(resolved.read_text(encoding="utf-8"))
            except OSError as exc:
                logger.warning("AGENTHUB.md 读取失败 %s: %s", resolved, exc)
        return "\n\n---\n\n".join(parts) if parts else ""

    # --------------------------------------------------------
    # 动态层
    # --------------------------------------------------------

    async def _layer_5_long_term_memory(self, ctx: PromptContext) -> str:
        """
        第 5 层:长期记忆索引 —— Progressive disclosure 模式。

        - 只把 MEMORY.md 索引(name + description)塞进 prompt,正文不进
        - 主 Agent 读完索引后,需要哪条记忆就调 read_file 工具按需加载
        - 索引为空(目录不存在 / 没记 / 索引文件没内容)→ 返回空字符串,不在 prompt 里
          出现"## 你的长期记忆索引(空)"这种废话

        作用对象:用户 + 会话双隔离的记忆,跨 Thread 复用。

        TODO[F-prompt-async-io]: list_index 是同步函数(读 MEMORY.md 文件 IO),在 async def
        里直接调用,高并发场景会阻塞 event loop。MVP 阶段单用户问题不大,后续上量时改成
        `await asyncio.to_thread(list_index, ...)` 或让 memory_service 提供 async 版本。
        同样问题在 _layer_1 / _layer_4 也存在(都是同步文件 IO)。
        """
        # list_index 内部已经处理了"目录不存在"和"索引文件不存在"两种情况,
        # 都返回空列表——这里不需要 try/except FileNotFoundError
        index_lines = list_index(ctx.user_id, ctx.conversation_id)
        if not index_lines:
            return ""

        body = "\n".join(
            f"- [{ln.name}]({ln.name}.md) — {ln.description}"
            for ln in index_lines
        )
        return (
            "## 你的长期记忆索引\n\n"
            "以下是当前会话累积的长期记忆(项目核心进展 / 用户偏好 / 跨会话事实等)。\n"
            "如需查看某条记忆的完整内容,调用 read_file 工具,"
            "path 参数填记忆文件名(如 `feedback_no_emoji.md`)。\n"
            "**先按需要读,不要每条都读——索引足够你判断哪些相关。**\n\n"
            f"{body}"
        )

    async def _layer_6_dynamic_context(self, ctx: PromptContext) -> str:
        """
        第 6 层:动态上下文。三块拼接:
        1. 当前会话最近 N 条消息(滑动窗口入口,详情让 LLM 调 read_conversation_history)
        2. 当前会话挂载的可用 Agent 列表(精简,详情让 LLM 调 get_agent_capabilities)
        3. 当前轮次的任务图状态(轻量,本身就是 read_task_plan 的全量返回)

        每块独立 try/except 兜底:单块查询失败不阻塞整层,失败块输出空字符串。
        三块全空时整层返回 ""(避免硬塞"## 动态上下文(空)"白占 token)。
        """
        history = await self._dyn_history_block(ctx)
        agents = await self._dyn_agents_block(ctx)
        task_plan = await self._dyn_task_plan_block(ctx)

        parts = [p for p in (history, agents, task_plan) if p]
        return "\n\n".join(parts)

    async def _dyn_history_block(self, ctx: PromptContext) -> str:
        """会话最近 N 条消息摘要。"""
        # lazy import 避免 prompt_builder import 时 message_service 还在初始化链路上
        from backend.services.message_service import message_service

        try:
            messages = await message_service.list_recent(
                ctx.conversation_id,
                limit=_HISTORY_RECENT_LIMIT,
            )
        except Exception:
            logger.exception("layer_6 list_recent 失败 conversation=%s", ctx.conversation_id)
            return ""
        if not messages:
            return ""

        # repo 返回倒序(最新在前),反转为正序便于阅读时间线
        messages = list(reversed(messages))

        lines: list[str] = []
        for m in messages:
            sender = (m.sender or m.agent_id or m.user_id or "?")[:30]
            text = self._extract_message_text(m.content)
            if len(text) > _HISTORY_TEXT_PER_MSG_CHARS:
                text = text[:_HISTORY_TEXT_PER_MSG_CHARS] + "...(truncated)"
            lines.append(f"- [{m.role}/{sender}] {text}")

        return (
            f"## 当前会话最近 {len(messages)} 条历史\n\n"
            "更早的消息或单条详情请调 `read_conversation_history` 工具拉取。\n\n"
            + "\n".join(lines)
        )

    async def _dyn_agents_block(self, ctx: PromptContext) -> str:
        """会话挂载的可用 Agent 列表(精简)。"""
        from backend.services.conversation_service import conversation_service

        try:
            agents = await conversation_service.get_active_agents(ctx.conversation_id)
        except Exception:
            logger.exception(
                "layer_6 get_active_agents 失败 conversation=%s", ctx.conversation_id
            )
            return ""
        if not agents:
            return ""

        lines = [
            f"- `{a.id}` **{a.name}** — {a.description or '(无描述)'}"
            for a in agents
        ]
        return (
            "## 本会话可用 Agent\n\n"
            "派活前可调 `get_agent_capabilities(agent_id)` 拿到完整能力 / system_prompt。\n\n"
            + "\n".join(lines)
        )

    async def _dyn_task_plan_block(self, ctx: PromptContext) -> str:
        """当前轮次任务图状态(同 user_message_id 的所有 Thread,含主 Agent 自己)。"""
        from backend.core.database import SessionLocal
        from backend.repositories.thread_repo import ThreadRepository

        # 在 session 生命周期内把 ORM 对象的字段抽成纯 Python 元组,
        # 避免 session.close() 后访问 ORM 属性触发 DetachedInstanceError
        rows: list[tuple[str, str, str, list[str]]] = []
        session = SessionLocal()
        try:
            # 子 Thread 状态在后台 task 用别的 session 写,本 session 必须 expire
            # 才能拿到最新状态(否则可能命中 identity map 缓存读到陈旧值)
            session.expire_all()
            try:
                threads = ThreadRepository(session).list_by_message(ctx.user_message_id)
            except Exception:
                logger.exception(
                    "layer_6 list_by_message 失败 message=%s", ctx.user_message_id
                )
                return ""
            rows = [
                (t.id, t.agent_id, t.status, list(t.blocked_by or []))
                for t in threads
            ]
        finally:
            session.close()

        if not rows:
            return ""

        lines: list[str] = []
        for tid, agent_id, status, blockers in rows:
            blocker_str = f" blocked_by={blockers}" if blockers else ""
            lines.append(
                f"- `{tid}` agent=`{agent_id}` status={status}{blocker_str}"
            )

        return (
            "## 当前轮次任务图\n\n"
            "完整产出请调 `read_thread_result(thread_id)` 拉取。\n\n"
            + "\n".join(lines)
        )

    @staticmethod
    def _extract_message_text(content: object) -> str:
        """
        从 messages.content (JSON 列存储的 ContentBlock 数组) 提取展示文本。

        ContentBlock 协议见 domain/message.py:
        - TextBlock     content
        - ThinkingBlock content
        - ToolUseBlock  tool_name + input(摘要展示)
        - CodeBlock     language + code(摘要展示)
        - ApprovalBlock action + status
        - 其他          type 占位

        失败兜底返回 repr(content)[:200],不让单条解析错误拖死整层。
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return repr(content)[:200]

        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block)[:80])
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("content") or "")
            elif btype == "thinking":
                parts.append(f"<thinking> {block.get('content', '')}")
            elif btype == "tool_use":
                parts.append(f"<tool_use {block.get('tool_name', '?')}>")
            elif btype == "code":
                parts.append(
                    f"<code {block.get('language', '')}> "
                    + (block.get("code") or "")[:80]
                )
            elif btype == "approval":
                parts.append(
                    f"<approval {block.get('action', '?')} status="
                    f"{block.get('status', '?')}>"
                )
            else:
                parts.append(f"<{btype}>")
        return " ".join(p for p in parts if p)


prompt_builder = SystemPromptBuilder()
