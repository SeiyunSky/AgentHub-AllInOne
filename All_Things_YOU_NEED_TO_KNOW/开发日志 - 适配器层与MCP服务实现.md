# AgentHub 开发日志 — 适配器层 + MCP 服务 + Agent 模版

**日期：** 2026-05-22
**分支：** `dev/musuyin/codex`
**涉及文件：** 18 个文件修改 / 1 个新建，共新增约 1500 行代码

---

## 背景

AgentHub 是一个 FastAPI + Vue3 的 IM 式多 Agent 协作平台。本次开发前，项目的 ORM 层（`backend/models/`）和 `requirements.txt` 已就绪，其余所有后端文件均为单行 `# TODO` 注释占位符。

**本次任务：**
1. OpenAI / Codex SDK Adapter 对接
2. MCP 服务支持
3. Agent 模版文件编写（skills + prompts）

---

## 实现内容

### Phase 0 — 基础对象

在实现 Adapter 层之前，需要先补全其依赖的基础模块。

#### `backend/config.py`

使用 `pydantic-settings` 的 `BaseSettings` 读取 `.env` 文件，集中管理所有环境变量：

| 分组 | 关键字段 |
|------|---------|
| 运行时 | `env`, `host`, `port` |
| 数据库 | `db_url`, `db_pool_size` |
| 鉴权 | `jwt_secret`, `jwt_algorithm`, `jwt_expire_minutes` |
| Redis | `redis_url` |
| Anthropic | `anthropic_api_key`, `anthropic_model_id`, `anthropic_base_url` |
| OpenAI / Custom | `openai_api_key`, `openai_model_id`, `openai_base_url` |
| Codex CLI | `codex_bin_path`（默认 `"codex"`） |
| OpenCode CLI | `opencode_bin_path` |

#### `backend/domain/agent.py`

```python
@dataclass
class AgentCapabilities:
    supports_diff: bool = False
    supports_approval: bool = False

@dataclass
class AgentEntity:
    id: str; name: str; type: str
    capabilities: AgentCapabilities
    system_prompt: str | None; tags: list[str]
```

#### `backend/domain/skill.py` / `domain/message.py`

纯 dataclass，无框架依赖，供 Adapter 层的 `stream()` 签名使用。`SkillEntity.content` 字段为 `None` 时表示尚未从文件加载（惰性加载，由 `skill_service` 填充）。

#### `backend/core/exceptions.py`

定义了服务层的自定义异常体系：

```
AgentHubError（基类）
  ├─ AgentNotFoundError
  ├─ CircuitOpenError
  ├─ RateLimitError
  ├─ ApprovalRequiredError
  └─ PermissionDeniedError
```

---

### Phase 1 — `adapters/events.py`

定义前后端 SSE 协议的完整事件模型，使用 Pydantic Union + `Literal` 鉴别器字段 `type`。

**关键设计：** Python 侧使用 `snake_case`，序列化到 JSON 时通过 `alias_generator=to_camel` 自动转为 `camelCase`，与前端 TypeScript 约定对齐：

```python
AgentStartEvent(agent_id="a1")
# → {"type":"agent_start","agentId":"a1","agentName":"...","messageId":"..."}
```

**完整事件类型列表：**

| 事件类型 | 触发时机 |
|---------|---------|
| `agent_start` | Agent 开始响应，前端创建新消息气泡 |
| `token` | 流式 token，前端追加到气泡 |
| `artifact_html` | HTML 预览卡片 |
| `artifact_diff` | 代码 Diff 卡片（含 file/patch/additions/deletions） |
| `approval_request` | 工具调用需要用户确认，前端弹出审批卡片 |
| `sub_agent_spawn` | 派生子 Agent |
| `deploy_progress` | 部署进度（stage/percent） |
| `deploy_done` | 部署完成（url） |
| `agent_done` | Agent 正常结束 |
| `agent_error` | Agent 出错 |

---

### Phase 2 — `adapters/base.py`

```python
class AgentAdapter(ABC):
    @abstractmethod
    async def stream(
        self,
        prompt: str,
        history: list[MessageEntity],
        skills: list[SkillEntity],
    ) -> AsyncGenerator[AgentEvent, None]: ...

    @abstractmethod
    def get_capabilities(self) -> dict[str, bool]: ...
    # {"supports_diff": bool, "supports_approval": bool}

    async def close(self) -> None: ...  # 可选，Registry shutdown 时调用
```

所有 Adapter 均须先 yield `AgentStartEvent`，最后 yield `AgentDoneEvent` 或 `AgentErrorEvent`。

---

### Phase 3 — `adapters/mcp_client.py`（新建文件）

这是本次新增的核心模块，为 MCP（Model Context Protocol）提供生命周期管理的客户端。

#### MCPTool

```python
@dataclass
class MCPTool:
    name: str
    description: str | None
    input_schema: dict[str, Any]
    has_side_effects: bool = True  # 由 ToolAnnotations.readOnlyHint 推断
```

`has_side_effects=False` 的工具（只读工具）在 Adapter 内直接调用；`True` 的工具需先 yield `ApprovalRequestEvent`，等待用户通过 WebSocket 确认。

#### MCPClient

支持两种 transport：

| Transport | 适用场景 | 工厂方法 |
|-----------|---------|---------|
| **stdio** | 子进程 MCP 服务器（如 Codex CLI） | `MCPClient.connect_stdio(command, args)` |
| **SSE/HTTP** | 远程 MCP 服务器 | `MCPClient.connect_sse(url, headers)` |

**生命周期管理的关键实现：**

MCP SDK 的 `stdio_client` / `sse_client` 是 `asynccontextmanager`，必须在持续存活的 async 上下文中运行。通过 `asyncio.create_task` + `anyio.Event` 实现：连接保活任务在后台运行，`_stop_event.wait()` 阻塞持有连接，调用 `stop()` 时触发关闭。

```python
async def _run():
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            self._session = session
            self._ready_event.set()    # 通知工厂方法连接就绪
            await self._stop_event.wait()  # 保持连接直到 stop()

self._background_task = asyncio.create_task(_run())
await self._ready_event.wait()  # 工厂方法等待连接就绪后返回
```

#### MCPRegistry

模块级单例，管理所有 MCP 服务器连接。FastAPI `lifespan` 关闭时调用 `MCPRegistry.shutdown_all()` 优雅停止所有连接。

---

### Phase 4 — `adapters/claude.py`

使用 Anthropic Python SDK `AsyncAnthropic.messages.stream()` 实现流式对接。

**事件处理流程：**

| stream 事件类型 | yield 的 AgentEvent |
|---------------|-------------------|
| `"text"` | `TokenEvent` |
| `"content_block_start"` (tool_use) | 开始累积工具调用 |
| `"input_json_delta"` | 累积 JSON 参数字符串 |
| `"content_block_stop"` (tool_use，有副作用) | `ApprovalRequestEvent` |
| `"content_block_stop"` (tool_use，任意) | `call_tool()` → `TokenEvent`（工具结果） |
| `anthropic.APIError` | `AgentErrorEvent` |
| 流结束 | `AgentDoneEvent` |

**辅助函数：**
- `_build_anthropic_messages()` — 将 `history: list[MessageEntity]` + 当前 `prompt` 转换为 Anthropic API 的 `messages` 格式
- `_build_system_prompt()` — 拼接 `system_prompt` + 注入的 Skill 内容
- `_mcp_tool_to_anthropic()` — 将 `MCPTool` 转换为 Anthropic `ToolUnionParam` 格式

---

### Phase 5 — `adapters/custom.py`

使用 OpenAI Python SDK `AsyncOpenAI.chat.completions.create(stream=True)` 实现，支持任意 OpenAI 兼容端点。

**典型用途：**
- OpenAI 官方（`gpt-4o` 等）
- Ollama 本地模型（`base_url="http://localhost:11434/v1"`）
- vLLM、Together、Groq 等第三方服务
- 任何 `base_url` 可配的 OpenAI 兼容 API

工具格式转换：`MCPTool` → OpenAI `{"type":"function","function":{...}}` 格式。

---

### Phase 6 — `adapters/codex.py`

对接 [OpenAI Codex CLI](https://github.com/openai/codex)（命令行编码 Agent，非旧版 Completions API）。

**双模式实现：**

#### 主模式：MCP Server 模式
若 Codex CLI 支持 `--mcp-server` 启动，通过 `MCPRegistry` 建立 stdio 连接，调用 `codex(prompt)` MCP 工具，将返回的文本/diff 解析为对应事件。

#### 备用模式：Subprocess 流式

```python
proc = await asyncio.create_subprocess_exec(
    bin_path, "--no-interactive", prompt,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```

逐行读取 stdout，状态机解析：

| 行特征 | 处理逻辑 |
|-------|---------|
| `--- a/<file>` 开头 | 进入 diff 累积模式 |
| diff 块内容 | 继续累积 |
| diff 块结束（空行） | yield `ArtifactDiffEvent`（含 additions/deletions 统计） |
| `? running: <cmd>` | yield `ApprovalRequestEvent`，向 stdin 写入 `y/n` |
| 其余内容 | yield `TokenEvent` |

---

### Phase 7 — `adapters/registry.py`

```python
class AdapterRegistry:
    async def seed_from_db(self, db: AsyncSession) -> None: ...
    def get_or_raise(self, agent_id: str) -> AgentAdapter: ...
    def register(self, agent_id: str, adapter: AgentAdapter) -> None: ...
    async def shutdown(self) -> None: ...

registry = AdapterRegistry()  # 模块级单例
```

`_build_adapter(row)` 工厂函数根据 ORM 行的 `type` 字段路由：

| `type` 字段 | 创建的 Adapter |
|------------|--------------|
| `"claude"` | `ClaudeAdapter`（使用 `settings.anthropic_*`） |
| `"codex"` | `CodexAdapter`（使用 `settings.codex_bin_path` + MCPRegistry） |
| `"custom"` | `CustomAdapter`（`api_key`/`base_url` 优先读 `capabilities` JSON） |
| `"opencode"` | `CodexAdapter`（复用，使用 `settings.opencode_bin_path`） |

---

### Phase 8 — Agent 模版文件

#### Skills（注入系统提示的知识增强模块）

| 文件 | trigger_keywords | 内容要点 |
|------|-----------------|---------|
| `code_review.md` | review, 审查, 代码质量, PR | 5 维度方法论（正确性/安全/性能/可维护性/测试）+ SEVERITY 输出格式 + 汇总表 |
| `python_expert.md` | python, 异步, asyncio, FastAPI | async 模式、TaskGroup、FastAPI SSE、SQLAlchemy 2.x async、Pydantic v2 |
| `security_audit.md` | 安全, XSS, SQL注入, 鉴权, 漏洞 | OWASP A01-A08 逐项检查清单 + CWE 编号 + 安全记分卡 |

#### Prompts（服务层渲染后作为系统提示使用）

| 文件 | 变量 | 输出格式 |
|------|-----|---------|
| `orchestrator.md` | `{{user_message}}`, `{{conversation_history}}`, `{{available_agents}}` | 严格 JSON：`{intent, mode, tasks[], fallback_agent_id}` |
| `agent_builder.md` | `{{user_description}}`, `{{existing_agents}}` | 严格 JSON：`{name, description, type, system_prompt, tags, capabilities}` |
| `local_edit.md` | `{{file}}`, `{{start}}`, `{{end}}`, `{{selected_code}}`, `{{user_intent}}` | 完整替换代码块 + 变更说明 |
| `sub_agent_spawn.md` | `{{parent_task}}`, `{{sub_task}}`, `{{context}}` | 任务输出 + `[SUB-TASK COMPLETE/BLOCKED]` 结束标记 |

---

## MCP 全链路集成流程

```
FastAPI lifespan startup
  ├─ MCPRegistry.get_or_connect_stdio("codex", "codex", ["--mcp-server"])
  │     └─ 建立 stdio 连接，后台 task 保活
  └─ AdapterRegistry.seed_from_db(db)
        ├─ type=codex  → CodexAdapter(mcp_client=MCPRegistry.get("codex"))
        ├─ type=claude → ClaudeAdapter(mcp_client=None)
        └─ type=custom → CustomAdapter(mcp_client=None 或按配置)

Chat 请求到达
  └─ adapter.stream(prompt, history, skills)
        ├─ mcp_client.list_tools() → 工具列表注入 LLM
        ├─ LLM 决定调用工具
        │     ├─ has_side_effects=True  → yield ApprovalRequestEvent
        │     │     └─ Thread 挂起，等待 WebSocket 用户确认
        │     └─ has_side_effects=False → 直接 call_tool()，结果注入对话
        └─ 继续流式输出

FastAPI lifespan shutdown
  ├─ MCPRegistry.shutdown_all()  → 停止所有 MCP 子进程
  └─ AdapterRegistry.shutdown()  → 调用各 adapter.close()
```

---

## 验证结果

```
$ .venv/bin/python -c "..."
All imports OK
Settings model: claude-sonnet-4-6
Event JSON (camelCase): {"type":"agent_start","agentId":"a1","agentName":"Claude","messageId":"m1"}
All adapter imports OK
Claude capabilities: {'supports_diff': True, 'supports_approval': True}
Custom capabilities: {'supports_diff': True, 'supports_approval': False}
Codex capabilities:  {'supports_diff': True, 'supports_approval': True}
```

---

## 下一步

Adapter 层已自包含，可独立测试。后续开发可按以下顺序推进：

1. **`core/`** — `database.py`, `redis.py`, `circuit_breaker.py`, `lock.py`
2. **`repositories/`** — 各表的 CRUD 实现
3. **`services/`** — `chat_service`、`thread_service`、`stream_service` 等
4. **`api/v1/`** — SSE 端点、WebSocket 端点、Agent CRUD
