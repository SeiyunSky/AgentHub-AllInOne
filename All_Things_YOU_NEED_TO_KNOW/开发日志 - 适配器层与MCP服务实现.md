# AgentHub 开发日志 — 适配器层实现（块级流式协议对齐 + Claude CLI 接入）

**最后更新：** 2026-05-29
**分支：** `master`
**涉及文件：** `adapters/claude.py`、`adapters/codex.py`、`adapters/custom.py`、`adapters/registry.py`、`adapters/base.py`、`adapters/events.py`

---

## 背景

2026-05-25 master 分支合并（Adam Zhang）对事件协议、base 接口、domain 模型进行了全面重构。本阶段完成两件事：

1. **接口对齐**：三个 Adapter 全面迁移至块级流式协议
2. **Claude 接入模式修改**：从 Anthropic SDK 直接调用改为 Claude Code CLI subprocess 模式

### 接口变化速查

| 模块 | 旧接口 | 新接口 |
|------|--------|--------|
| `adapters/events.py` | `TokenEvent`、`ArtifactDiffEvent`、`ApprovalRequestEvent` 等 10 类扁平事件 | **块级流式协议**：`AgentStartEvent` / `BlockStartEvent` / `BlockDeltaEvent` / `BlockStopEvent` / `AgentDoneEvent` / `AgentErrorEvent` |
| `adapters/base.py` | `stream(prompt, history, skills)` → `AsyncGenerator` | `stream(inp: StreamInput)` → `AsyncIterator`；`get_capabilities()` 返回 `AgentCapabilities` dataclass |
| `domain/message.py` | `MessageEntity` dataclass（role/content 字符串） | `ContentBlock` 联合类型（TextBlock / ThinkingBlock / ToolUseBlock / CodeBlock / ApprovalBlock 等 8 种） |
| `schemas/message.py` | 不存在 | `MessageInHistory`（Adapter 喂历史用）/ `MessageCreate` / `MessageResponse` 等 |
| `schemas/skill.py` | `SkillEntity` dataclass | `SkillWithContent`（Pydantic，含 `content` 正文） |
| `config.py` | 含 `anthropic_api_key`、`openai_model_id` 等 API 配置字段 | 精简为 `DB_URL` + `MEMORY_ROOT`，API 配置通过环境变量直接读取 |

---

## 块级流式协议（`adapters/events.py`）

新协议核心：**一条消息 = 多个有序块，每块生命周期三步**。

```
BlockStartEvent  → 创建块（携带 block_id + 初始字段）
BlockDeltaEvent  → 增量更新（{"content": "新片段"} 累加，{"status": "completed"} 覆盖）
BlockStopEvent   → 块结束（可附 final_fields）
```

**所有事件新增 `thread_id` 字段**，必须三字段齐全：`agent_id`、`thread_id`、`message_id`。

**RoundDoneEvent / QueueDrainedEvent** 独立于 `AgentEvent` union，由 `stream_service` 单独产生。

---

## `adapters/base.py`（新 StreamInput）

```python
@dataclass
class StreamInput:
    agent_id: str
    thread_id: str          # 新增，所有事件必须填
    message_id: str         # 由 Orchestrator 注入，Adapter 不自行生成
    prompt: str
    history: list[MessageInHistory]
    system_prompt: Optional[str] = None
    skills: list[SkillWithContent] = field(default_factory=list)
    cancel_event: Optional[asyncio.Event] = None   # abort 信号
```

`get_capabilities()` 返回类型从 `dict[str, bool]` 改为 `AgentCapabilities`：

```python
def get_capabilities(self) -> AgentCapabilities:
    return AgentCapabilities(supports_code=True, supports_diff=True, supports_approval=True)
```

---

## `adapters/claude.py` — CLI subprocess 模式

### 接入方式变更

| | 旧实现 | 新实现 |
|-|--------|--------|
| 接入方式 | Anthropic SDK（`anthropic.AsyncAnthropic`）直接调 API | Claude Code CLI subprocess（`claude -p <prompt> --output-format stream-json --verbose`） |
| 认证 | `ANTHROPIC_API_KEY` 环境变量 | `claude login` OAuth session，无需 API Key |
| 依赖 | `anthropic` Python SDK | 本地安装的 `claude` CLI |
| 构造参数 | `model`、`api_key`、`base_url`、`mcp_client` | 仅 `bin_path`（默认 `"claude"`） |

### 工作原理

```
claude -p "<history + prompt>" --output-format stream-json --verbose
  │
  ├─ {"type": "assistant", "message": {"content": [{"type": "text", "text": "..."}]}}
  │     → BlockStartEvent(TextBlock) + BlockDeltaEvent({"content": text})
  │
  └─ {"type": "result", "subtype": "success"}
        → BlockStopEvent + AgentDoneEvent
```

### 历史序列化 `_build_prompt()`

将 `MessageInHistory.blocks` 拼成纯文本追加到 prompt 前：

| 块类型 | 序列化结果 |
|-------|----------|
| `TextBlock` | 直接取 `.content` |
| `ThinkingBlock` | 省略（不喂给 LLM） |
| `ToolUseBlock` | `"[Tool: {tool_name} -> {output or 'pending'}]"` |
| `CodeBlock` | `"[Code: {filename} +{additions}/-{deletions}]"` |
| `ApprovalBlock` | `"[Approval: {action} ({status})]"` |

`system_prompt` 通过 `--append-system-prompt` 参数注入。

### 支持的能力

```python
AgentCapabilities(supports_code=True, supports_diff=True, supports_approval=False)
```

注：当前 CLI 模式不支持 ApprovalBlock（CLI 自动处理工具调用，无法中断等待审批）。

---

## `adapters/custom.py` — OpenAI 兼容 API

与旧实现接口对齐，关键差异：

- 文本输出：首个文本 chunk 触发 `BlockStart`，后续 `BlockDelta`，`finish_reason="stop"` 触发 `BlockStop`
- 工具调用：`finish_reason="tool_calls"` 时批量处理所有累积的 `pending_tool_calls`，每个工具独立产出 `ToolUseBlock` + 可选的 `ApprovalBlock`
- 流异常截断时自动关闭开放中的文本块

---

## `adapters/codex.py` — Codex CLI

### Diff 输出 → CodeBlock

```python
# 旧
yield ArtifactDiffEvent(file_path=..., patch=...)

# 新
yield BlockStartEvent(..., block=CodeBlock(block_id=bid, language="diff", code="", filename=file_path))
yield BlockDeltaEvent(..., block_id=bid, delta={"code": patch_text})
yield BlockStopEvent(..., block_id=bid, final_fields={"additions": N, "deletions": M})
```

### 审批请求 → ApprovalBlock

```python
# 旧
yield ApprovalRequestEvent(action="run_command", detail=command)

# 新
yield BlockStartEvent(..., block=ApprovalBlock(action="run_command", detail=command, status="pending"))
yield BlockStopEvent(..., final_fields={"status": "approved"})
```

### cancel_event 支持

subprocess 模式每次 readline 后检查，触发时调 `proc.terminate()`，关闭开放文本块后 yield error。

---

## `adapters/registry.py` — 工厂函数 + Session 修复

### 工厂函数对齐

`_build_adapter()` 不再向构造函数传 `agent_id`、`agent_name`、`system_prompt`，不再从 `settings` 读 API 配置：

```python
# 旧
ClaudeAdapter(agent_id=row.id, agent_name=row.name, system_prompt=row.system_prompt, ...)

# 新
ClaudeAdapter()              # type=claude，使用 claude CLI
CodexAdapter(mcp_client=...) # type=codex
CustomAdapter(model=..., api_key=..., base_url=...)  # type=custom，从 capabilities JSON 读
```

### seed_from_db Session 修复（D7-blocker 配套）

```python
# 旧（错误）：async def + AsyncSession
async def seed_from_db(self, db: AsyncSession) -> None:
    result = await db.execute(...)

# 新（正确）：同步 def + Session，与其他服务层统一
def seed_from_db(self, db: Session) -> None:
    rows = db.execute(select(AgentModel).where(...)).scalars().all()
```

`shutdown()` 简化为直接 `_registry.clear()`（新 Adapter 无 `close()` 方法）。

---

## 测试更新

所有单元测试对齐新接口：

| 文件 | 主要变更 |
|------|---------|
| `tests/conftest.py` | `MessageEntity` + `SkillEntity` → `MessageInHistory` + `SkillWithContent` |
| `tests/unit/test_events.py` | 旧 10 类扁平事件 → 块级事件协议（BlockStart/Delta/Stop 序列化、union 鉴别器） |
| `tests/unit/test_claude_adapter.py` | `stream(prompt, history, skills)` → `stream(StreamInput)`；mock subprocess stdout；验证 BlockStart/Delta/Stop 事件序列 |
| `tests/unit/test_custom_adapter.py` | `get_capabilities()` 断言改为 `AgentCapabilities` 字段；工具调用块级事件测试 |
| `tests/unit/test_codex_adapter.py` | `ArtifactDiffEvent` → `BlockStartEvent(CodeBlock)`；diff 测试改为检查 `CodeBlock` 块 |
| `tests/unit/test_registry.py` | `seed_from_db` 测试改为同步（`MagicMock` 替代 `AsyncMock`）；`test_shutdown_clears_registry` |

---

## 全链路流程

```
FastAPI lifespan startup
  ├─ MCPRegistry.get_or_connect_stdio("codex", ...)
  └─ AdapterRegistry.seed_from_db(db)          # 同步 Session
        ├─ type=codex  → CodexAdapter(mcp_client=MCPRegistry.get("codex"))
        ├─ type=claude → ClaudeAdapter()        # claude CLI，无需 API Key
        └─ type=custom → CustomAdapter(model=..., api_key=..., base_url=...)

Chat 请求到达
  └─ adapter.stream(StreamInput(agent_id, thread_id, message_id, prompt, history, ...))
        ├─ yield AgentStartEvent
        ├─ 块级流式（TextBlock / ToolUseBlock / CodeBlock / ApprovalBlock）
        │     BlockStartEvent → BlockDeltaEvent(s) → BlockStopEvent
        └─ yield AgentDoneEvent 或 AgentErrorEvent

FastAPI lifespan shutdown
  ├─ MCPRegistry.shutdown_all()
  └─ AdapterRegistry.shutdown()   → _registry.clear()
```

---

## 验证结果

```
$ PYTHONPATH=. DB_URL=sqlite:///./test.db .venv/bin/python -c "
from backend.adapters.claude import ClaudeAdapter
from backend.adapters.custom import CustomAdapter
from backend.adapters.codex import CodexAdapter
from backend.domain.agent import AgentCapabilities
a = ClaudeAdapter()
assert isinstance(a.get_capabilities(), AgentCapabilities)
print('imports OK')
"
imports OK

$ PYTHONPATH=. DB_URL=sqlite:///./test.db .venv/bin/pytest backend/tests/unit/ -v
======================== 70 passed, 1 warning ========================
```

集成测试（`pytest -m integration`）需要本地安装并登录 `claude` CLI，在 CI 环境中自动 skip。

---

## 当前状态与遗留 TODO

适配器层已完全实现并通过单元测试。遗留项均在服务层：

| 优先级 | 位置 | 内容 |
|--------|------|------|
| 中 | `main.py` TODO[main-1] | lifespan 中 `seed_from_db` 接入同步 `SessionLocal()` |
| 中 | `orchestrator_tools.py` [F-skill] | `get_agent_capabilities` 接入 `skill_service` |
| 低 | `orchestrator/service.py` | `save_checkpoint` 持久化未实现 |
| 低 | `prompt_builder.py` Layer 3-6 | memory / skill 动态上下文注入为 stub |
| 低 | `api/v1/agents.py` | Agent CRUD 端点未实现 |
| 低 | `api/v1/ws.py` | WebSocket（approval / diff / status）未实现 |

---

## 补充：端到端跑通后的完整实现细节（2026-05-27/28）

> 本节记录主链路跑通后对 ClaudeAdapter 及其调用链的完整实现状态，可作为最新参考。

### ClaudeAdapter 完整工作流

```
thread_service._run_thread(thread)
  ├─ 从 DB 加载上下文（MySQL 查询）
  │     ├─ AgentRepository.get(agent_id) → agent.system_prompt
  │     ├─ MessageRepository.list_recent(conversation_id, limit=20) → history（倒序，翻转为正序）
  │     └─ SkillService.list_with_content_for_agent(agent_id) → agent_skills（查 agent_skills 关联表 + 读文件）
  │
  ├─ 构造 StreamInput
  │     agent_id, thread_id, message_id, prompt=thread.dispatch_prompt,
  │     history=history, skills=agent_skills, system_prompt=agent.system_prompt,
  │     cancel_event=stream_service.get_abort_event(conversation_id)
  │
  ├─ ClaudeAdapter.stream(StreamInput)
  │     ├─ _build_prompt(inp) → 把 history + prompt 拼成单字符串，调 _flatten_for_cli 压换行
  │     ├─ subprocess: claude -p "<flat_prompt>" --output-format stream-json --verbose
  │     │               [--append-system-prompt "<flat_system_prompt>"]
  │     └─ 解析 stdout stream-json → yield BlockStart / BlockDelta / BlockStop / AgentDone
  │
  ├─ 消费事件流
  │     ├─ stream_service.push_event(conversation_id, event) → SSE 广播给前端
  │     ├─ block_states 累积（BlockStart 初始化 / BlockDelta 合并 / BlockStop final_fields 覆盖）
  │     └─ AgentDoneEvent 收到后：
  │           ├─ update_tokens(thread.id, delta) → threads.tokens_total 累加
  │           └─ _persist_assistant_message() → messages 表写入完整产出
  │
  └─ mark_done → _on_thread_terminal → pending_events 写摘要 + wake_event 唤醒主 Agent loop
```

### System Prompt 注入机制

两个独立来源，通过不同 CLI 参数传入：

| 来源 | 内容 | CLI 参数 |
|------|------|---------|
| `agents.system_prompt` | Agent 人格定义（从 DB 读取，每个 Agent 配置一次） | `--append-system-prompt` |
| Skill 正文 | 在 `_build_system_prompt()` 里拼接到 system_prompt 后（用 `---` 分隔） | （合并后一起传 `--append-system-prompt`） |

> **已知遗留**：`_build_system_prompt()` 函数已实现（合并 base + skills），但 `stream()` 当前只直接用 `inp.system_prompt`，未调用该函数将 skills 合并进去。skills 字段有值但尚未被 ClaudeAdapter 消费——需后续修复。

### Prompt 构建：`_build_prompt()` + `_flatten_for_cli()`

```python
def _build_prompt(inp: StreamInput) -> str:
    # 有历史时，将历史拼在 prompt 前面
    # 格式：
    # "User: <消息内容>  Assistant: <Agent名>: <消息内容>  User: <当前 prompt>"
    parts = []
    for msg in inp.history:
        role = "User" if msg.role == "user" else (msg.sender or "Assistant")
        text = _blocks_to_text(msg.blocks)  # ContentBlock → 可读文本
        if text:
            parts.append(f"{role}: {text}")
    parts.append(f"User: {inp.prompt}")
    return _flatten_for_cli("\n\n".join(parts))

def _flatten_for_cli(text: str) -> str:
    # \r\n / \r → \n → 空格，再折叠连续空格
    # Windows claude.CMD 不接受 -p / --append-system-prompt 参数中的真换行符
    flat = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ")
    return " ".join(flat.split())
```

ContentBlock 序列化规则（`_blocks_to_text`）：

| 块类型 | 序列化结果 |
|--------|----------|
| `TextBlock` | 直接取 `.content` 文本 |
| `ThinkingBlock` | **省略**（思考过程不喂回 LLM） |
| `ToolUseBlock` | `[Tool: {tool_name} -> {output or 'pending'}]` |
| `CodeBlock` | `[Code: {filename} +{additions}/-{deletions}]` |
| `ApprovalBlock` | `[Approval: {action} ({status})]` |

### History 存储与读取

**存储**：`messages` 表，`content` 字段为 JSON，存 `ContentBlock` 数组。子 Agent 流式完成后，`_persist_assistant_message` 将累积的 `block_states` 反序列化成 `ContentBlock` 列表写入一条 `role=assistant` 记录。

**读取**（每次子 Thread 启动）：

```python
raw_history = msg_repo.list_recent(conversation_id, limit=20)  # 倒序（最新在前）
history = list(reversed(raw_history))                           # 翻转为正序（早→晚）
```

只取最近 20 条，排除软删除（`is_deleted=1`）。分页游标用 `(created_at, id)` 复合比较，防同毫秒消息丢失。

### Skill 注入机制

**扫描入库**（`main.py` lifespan 启动时）：

```python
SkillService(db).scan_builtin()
# 扫 backend/skills/*.md
# 解析 frontmatter（name/description/category）存 skills 表
# 文件正文不入库，只记 file_path
# 幂等：已存在跳过
```

**运行时注入**（每次子 Thread 启动）：

```python
agent_skills = SkillService(own_session).list_with_content_for_agent(agent_id)
# 1. 查 agent_skills 关联表，找该 agent 挂载了哪些 skill
# 2. 按 skill.file_path 读取文件正文
# 3. 返回 list[SkillWithContent]（含 content 字段）
```

Skill 正文通过 `_build_system_prompt` 追加到 system_prompt（每个 Skill 用 `\n---\n` 分隔），再通过 `--append-system-prompt` 传给 CLI。

### 子 Thread 产出落库：`_persist_assistant_message`

```
AgentDoneEvent 收到
  ├─ TypeAdapter(ContentBlock).validate_python(state) 反序列化每个 block_states
  ├─ message_service.create_assistant_message(
  │     conversation_id, agent_id, thread_id,
  │     content_blocks=blocks,
  │     sender=agent.name,    # agent 名字快照，改名后历史消息仍显示当时的名字
  │  )
  └─ message_service.update_tokens(msg.id, tokens_input, tokens_output)
```

失败兜底：落库异常只记日志，不抛出，不影响 Thread 进入 done 状态。

### MySQL 连接层

```python
# core/database.py
engine = create_engine(
    settings.DB_URL,
    pool_pre_ping=True,     # 连接前 ping，防连接池拿到已断开的连接
    pool_recycle=3600,      # 每小时回收连接，防 MySQL 8h 空闲断开
    connect_args={"init_command": "SET time_zone='+00:00'"},  # 强制 UTC，防时区错位
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
```

**Session 隔离**：`_run_thread` 是 asyncio Task，自起独立 `own_session = SessionLocal()`，不共享调用方 session。这是 D7-blocker 的核心修复——多个并发 Task 各自持有独立 session，互不干扰。

### 已知遗留问题

| # | 问题 | 影响 | 优先级 |
|---|------|------|--------|
| 1 | `_build_system_prompt` 未在 `stream()` 中调用，skills 有值但未注入 CLI | Skill 功能对 ClaudeAdapter 无效 | P1 |
| 2 | ClaudeAdapter CLI 模式不报 token usage，`AgentDoneEvent.tokens_*` 默认 0 | threads/messages token 字段全为 0 | P2 |
| 3 | `-p` 参数传 prompt 有长度上限，超长 dispatch_prompt 可能被截断 | 长任务描述丢失 | P2 |
| 4 | `_persist_assistant_message` 只在 TextBlock 场景验证，多 block / ToolUseBlock 未实测 | 边角场景可能 silently 跳过 | P2 |
