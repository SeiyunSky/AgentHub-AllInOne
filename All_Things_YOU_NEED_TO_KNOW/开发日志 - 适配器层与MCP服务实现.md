# AgentHub 开发日志 — 适配器层实现（块级流式协议对齐 + Claude CLI 接入）

**最后更新：** 2026-05-26
**分支：** `master`
**涉及文件：** `adapters/claude.py`、`adapters/codex.py`、`adapters/custom.py`、`adapters/registry.py`、`adapters/base.py`、`adapters/events.py`

---

## 背景

2026-05-25 master 分支合并（Adam Zhang）对事件协议、base 接口、domain 模型进行了全面重构。本阶段完成两件事：

1. **接口对齐**：三个 Adapter 全面迁移至块级流式协议
2. **Claude 接入模式修改**：从 Anthropic SDK 直接调用改为 Claude Code CLI subprocess 模式
aaaaaaaaaaa
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
