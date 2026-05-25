# AgentHub 开发日志 — 适配器层接口对齐（master 合并）

**日期：** 2026-05-25
**分支：** `dev/musuyin/codex`
**涉及文件：** 8 个文件修改，全面对齐 master 分支引入的块级流式协议

---

## 背景

2026-05-25 master 分支合并带来了重大接口重写（Adam Zhang），对 `events.py`、`base.py`、`domain/message.py`、`schemas/message.py`、`schemas/skill.py` 进行了全面重构。本次开发将三个 Adapter 实现及相关测试对齐至新接口。

### 接口变化速查

| 模块 | 旧接口 | 新接口（master 合并后） |
|------|--------|----------------------|
| `adapters/events.py` | `TokenEvent`、`ArtifactDiffEvent`、`ApprovalRequestEvent` 等 10 类扁平事件 | **块级流式协议**：`AgentStartEvent` / `BlockStartEvent` / `BlockDeltaEvent` / `BlockStopEvent` / `AgentDoneEvent` / `AgentErrorEvent` |
| `adapters/base.py` | `stream(prompt, history, skills)` → `AsyncGenerator` | `stream(inp: StreamInput)` → `AsyncIterator`；`get_capabilities()` 返回 `AgentCapabilities`（dataclass，不是 dict） |
| `domain/message.py` | `MessageEntity` dataclass（role/content 字符串） | `ContentBlock` 联合类型（TextBlock / ThinkingBlock / ToolUseBlock / CodeBlock / ApprovalBlock 等 8 种） |
| `schemas/message.py` | 不存在 | `MessageInHistory`（Adapter 喂历史用）/ `MessageCreate` / `MessageResponse` 等 |
| `schemas/skill.py` | `SkillEntity` dataclass | `SkillWithContent`（Pydantic，含 `content` 正文） |
| `config.py` | 含 `anthropic_api_key`、`openai_model_id` 等 API 配置字段 | 精简为 `DB_URL` + `MEMORY_ROOT`，API 配置通过环境变量直接读取 |

---

## 实现内容

### Phase 1 — 块级流式协议（`adapters/events.py`）

master 完全重写了 `events.py`。新协议核心：**一条消息 = 多个有序块，每块生命周期三步**。

```
BlockStartEvent  → 创建块（携带 block_id + 初始字段）
BlockDeltaEvent  → 增量更新（{"content": "新片段"} 累加，{"status": "completed"} 覆盖）
BlockStopEvent   → 块结束（可附 final_fields）
```

**所有事件新增 `thread_id` 字段**，与旧协议的单一 `agent_id` + `message_id` 相比，现在必须三字段齐全。

```python
BlockStartEvent(
    agent_id="a1", thread_id="t1", message_id="m1",
    block=TextBlock(block_id="...", content=""),
)
```

**RoundDoneEvent / QueueDrainedEvent** 独立于 `AgentEvent` union，由 `stream_service` 单独产生（SSE 连接在 `round_done` 后保持打开，等待排队消息；`queue_drained` 后关闭）。

---

### Phase 2 — `adapters/base.py`（新 StreamInput）

```python
@dataclass
class StreamInput:
    agent_id: str
    thread_id: str          # 新增，所有事件必须填
    message_id: str         # 由 Orchestrator 注入，Adapter 不自行生成
    prompt: str
    history: list[MessageInHistory]    # 旧: list[MessageEntity]
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

### Phase 3 — `adapters/claude.py` 全面重写

#### 构造函数简化

移除 `agent_id`、`agent_name`、`system_prompt`（这些信息现在走 `StreamInput` 传，不存在实例上）：

```python
def __init__(self, model=None, api_key=None, base_url=None, mcp_client=None)
```

API key 和模型 ID 从环境变量读取（`ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL_ID`），不再依赖 `config.settings`。

#### 块级事件映射

| Anthropic SDK 事件 | 新协议 |
|-------------------|-------|
| `content_block_start` (type=thinking) | `BlockStart` → `ThinkingBlock` |
| `content_block_start` (type=text) | `BlockStart` → `TextBlock` |
| `content_block_start` (type=tool_use) | `BlockStart` → `ToolUseBlock(status="running")` |
| `content_block_delta` (thinking_delta) | `BlockDelta({"content": delta})` |
| `content_block_delta` (text_delta) | `BlockDelta({"content": delta})` |
| `content_block_delta` (input_json_delta) | 累积到 `current_tool_input_str` |
| `content_block_stop` (tool_use，有副作用) | 先 `BlockStart` → `ApprovalBlock(status="pending")`，再 `BlockStop(final_fields={"status":"approved"})` |
| `content_block_stop` (tool_use) | `call_tool()` → `BlockStop(final_fields={"input":..., "output":..., "status":"completed"})` |
| `content_block_stop` (非 tool_use) | `BlockStop` |

#### 历史序列化 `_blocks_to_text()`

`MessageInHistory.blocks` 是 `list[ContentBlock]`，Adapter 喂 LLM 前需转为自然语言：

| 块类型 | 序列化结果 |
|-------|----------|
| `TextBlock` | 直接取 `.content` |
| `ThinkingBlock` | 省略（不喂给 LLM） |
| `ToolUseBlock` | `"[Tool: {tool_name} -> {output or 'pending'}]"` |
| `CodeBlock` | `"[Code: {filename} +{additions}/-{deletions}]"` |
| `ApprovalBlock` | `"[Approval: {action} ({status})]"` |

`role=assistant` 且 `msg.sender` 非空时，内容前拼入 `"[{sender}]: "` 前缀，让 LLM 区分多 Agent 群聊场景。

#### cancel_event 支持

每次主循环迭代检查 `inp.cancel_event.is_set()`，触发时 yield `AgentErrorEvent(error="cancelled")` 并 return。

---

### Phase 4 — `adapters/custom.py` 全面重写

与 `claude.py` 策略一致，关键差异：

- 文本输出：OpenAI 流是"按 chunk 来"而非"content_block"，首个文本 chunk 触发 `BlockStart`，后续 `BlockDelta`，`finish_reason="stop"` 触发 `BlockStop`
- 工具调用：在 `finish_reason="tool_calls"` 时批量处理所有累积的 `pending_tool_calls`，每个工具调用独立产出一个 `ToolUseBlock` + 可选的 `ApprovalBlock`
- 若流结束但未收到 `finish_reason="stop"`（异常截断），也会自动关闭开放中的文本块

---

### Phase 5 — `adapters/codex.py` 全面重写

#### Diff 输出 → CodeBlock

```
旧：_parse_diff_to_events() → list[ArtifactDiffEvent]
新：_emit_diff_blocks() → AsyncIterator[AgentEvent]（BlockStart/Delta/Stop with CodeBlock）
```

```python
yield BlockStartEvent(..., block=CodeBlock(block_id=bid, language="diff", code="", filename=file_path))
yield BlockDeltaEvent(..., block_id=bid, delta={"code": patch_text})
yield BlockStopEvent(..., block_id=bid, final_fields={"additions": N, "deletions": M})
```

#### 审批请求 → ApprovalBlock

```
旧：yield ApprovalRequestEvent(action="run_command", detail=command)
新：yield BlockStartEvent(..., block=ApprovalBlock(action="run_command", detail=command, status="pending"))
    yield BlockStopEvent(..., final_fields={"status": "approved"})
```

#### cancel_event 支持

subprocess 模式每次 readline 后检查，若触发则 `proc.terminate()`，关闭开放文本块后 yield error。

---

### Phase 6 — `adapters/registry.py` 工厂函数对齐

`_build_adapter()` 不再向构造函数传 `agent_id`、`agent_name`、`system_prompt`，不再从 `settings` 读 API 配置（直接由 Adapter 构造函数读 env var）：

```python
# 旧
ClaudeAdapter(agent_id=row.id, agent_name=row.name, system_prompt=row.system_prompt,
              api_key=settings.anthropic_api_key, ...)

# 新
ClaudeAdapter()  # 所有配置从环境变量取，agent 信息从 StreamInput 取
```

`shutdown()` 简化：不再调用 `adapter.close()`（新 Adapter 无此方法），直接 `_registry.clear()`。

---

### Phase 7 — 测试更新

所有单元测试对齐新接口：

| 文件 | 主要变更 |
|------|---------|
| `tests/conftest.py` | `MessageEntity` + `SkillEntity` → `MessageInHistory` + `SkillWithContent` |
| `tests/unit/test_events.py` | 旧 10 类扁平事件测试 → 块级事件协议测试（BlockStart/Delta/Stop 序列化、union 鉴别器） |
| `tests/unit/test_claude_adapter.py` | `stream(prompt, history, skills)` → `stream(StreamInput)`；`TokenEvent` → `BlockStartEvent(TextBlock)`；`ApprovalRequestEvent` → `BlockStartEvent(ApprovalBlock)`；新增 `_blocks_to_text()` 测试 |
| `tests/unit/test_custom_adapter.py` | 同上；`get_capabilities()` 返回值断言改为 `AgentCapabilities` 字段 |
| `tests/unit/test_codex_adapter.py` | `ArtifactDiffEvent` → `BlockStartEvent(CodeBlock)`；`_parse_diff_to_events()` 已不存在，diff 测试改为检查 `CodeBlock` 块 |
| `tests/unit/test_registry.py` | `test_shutdown_calls_close_on_all_adapters` → `test_shutdown_clears_registry` |

---

## 全链路集成流程（更新后）

```
FastAPI lifespan startup
  ├─ MCPRegistry.get_or_connect_stdio("codex", ...)
  └─ AdapterRegistry.seed_from_db(db)
        ├─ type=codex  → CodexAdapter(mcp_client=MCPRegistry.get("codex"))
        ├─ type=claude → ClaudeAdapter()         # API key 从 env var 取
        └─ type=custom → CustomAdapter(model=..., api_key=..., base_url=...)
                         # 优先读 capabilities JSON，fallback 到 env var

Chat 请求到达（Orchestrator 生成 message_id 注入 StreamInput）
  └─ adapter.stream(StreamInput(agent_id, thread_id, message_id, prompt, history, ...))
        ├─ yield AgentStartEvent(agent_id, thread_id, message_id, agent_name=agent_id)
        ├─ 块级流式输出（TextBlock / ThinkingBlock / ToolUseBlock / ApprovalBlock ...）
        │     BlockStartEvent → BlockDeltaEvent(s) → BlockStopEvent
        └─ yield AgentDoneEvent 或 AgentErrorEvent

FastAPI lifespan shutdown
  ├─ MCPRegistry.shutdown_all()  → 停止所有 MCP 子进程
  └─ AdapterRegistry.shutdown()  → 清空注册表
```

---

## 验证结果

```
$ DB_URL=sqlite+aiosqlite:///./test.db .venv/bin/python -c "
from backend.adapters.claude import ClaudeAdapter
from backend.adapters.custom import CustomAdapter
from backend.adapters.codex import CodexAdapter
from backend.domain.agent import AgentCapabilities
a = ClaudeAdapter()
assert isinstance(a.get_capabilities(), AgentCapabilities)
print('All imports OK, capabilities return AgentCapabilities instances')
"
All imports OK, capabilities return AgentCapabilities instances

$ DB_URL=sqlite+aiosqlite:///./test.db PYTHONPATH=. .venv/bin/pytest backend/tests/unit/ -v
======================== 70 passed, 1 warning in 0.99s =========================
```

---

## 下一步

适配器层与 master schema 已完全对齐，可进入服务层开发：

1. **`repositories/`** — `message_repo`、`thread_repo`、`agent_repo` CRUD 实现
2. **`services/stream_service.py`** — 消费 `AgentEvent` 流，写库 + 推 SSE（含 `RoundDoneEvent` / `QueueDrainedEvent` 信号）
3. **`services/thread_service.py`** — `resume_or_create()`，支持 `blocked_by` DAG 依赖校验
4. **`api/v1/`** — SSE 端点、审批 WebSocket 端点