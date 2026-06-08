# openai-agents-python
## 1. 项目基本信息

- **项目名**：OpenAI Agents SDK（openai/openai-agents-python）
- **GitHub**：https://github.com/openai/openai-agents-python
- **Star 数 / 主要语言**：26.5k / Python
- **简介**（≤200 字）：

OpenAI 官方推出的轻量级多 Agent 工作流框架，作为 Python SDK 提供。核心概念为 Agent（带指令、工具、护栏、handoff 的 LLM 配置）、Tools（函数/MCP/托管工具）、Handoffs（Agent 之间的任务移交）、Sessions（自动管理对话历史）、Tracing（内置全链路追踪）、Guardrails（输入输出安全检查）、Sandbox Agents（在受控容器环境中跨长时间执行）、Realtime Agents（语音 Agent）。Provider-agnostic，支持 OpenAI Responses、Chat Completions API 及 100+ 其他 LLM。

- **核心创新（一句话）**：把 Agent Loop 抽象成 Runner，把 Agent 之间协作抽象成 Handoff，所有协作过程自动产生 Trace。

## 2. 项目架构概览

### 技术栈

- **语言**：Python 3.10+
- **核心依赖**：Pydantic（数据校验）、MCP Python SDK（MCP 协议支持）、Griffe（文档）
- **可选依赖**：websockets、SQLAlchemy（Session 持久化）、any-llm / LiteLLM（多 LLM 提供商）、Redis（Session 存储）
- **工具链**：uv（包管理）、ruff（lint）、mypy / pyright（类型）、pytest（测试）、MkDocs（文档）

### 目录结构

```
openai-agents-python/
├── src/agents/                        ← 核心包（49 个文件 + 11 个子目录）
│   ├── agent.py             (43 KB)   ← Agent 基础类，定义 Agent 配置
│   ├── run.py               (93 KB)   ← Runner 主循环（Agent Loop 实现）
│   ├── run_state.py        (129 KB)   ← 运行时状态管理（最大文件，核心）
│   ├── tool.py              (73 KB)   ← Tool 抽象与函数式工具支持
│   ├── result.py            (40 KB)   ← Run 结果数据模型
│   ├── items.py             (33 KB)   ← 消息项、tool_use、tool_result 等数据结构
│   ├── apply_diff.py        (10 KB)   ← Diff 应用（沙箱场景的代码修改）
│   ├── function_schema.py   (16 KB)   ← Python 函数自动生成 JSON Schema
│   ├── guardrail.py         (10 KB)   ← 输入输出安全护栏
│   ├── retry.py             (12 KB)   ← 错误重试策略
│   ├── lifecycle.py          (6 KB)   ← Agent 生命周期钩子
│   │
│   ├── handoffs/                      ← Agent 之间任务移交机制
│   ├── tracing/                       ← 全链路追踪（Trace UI 数据生成）
│   ├── memory/                        ← Session 记忆持久化
│   ├── models/                        ← 多 LLM 提供商适配
│   ├── mcp/                           ← MCP 协议集成
│   ├── realtime/                      ← Realtime Agent（语音）
│   ├── sandbox/                       ← Sandbox Agent（容器化执行）
│   ├── voice/                         ← 语音相关
│   ├── extensions/                    ← 扩展点
│   ├── run_internal/                  ← 运行时内部实现细节
│   └── util/                          ← 工具函数
│
├── examples/                          ← 大量示例（多 Agent 编排、handoff、sandbox 等）
├── docs/                              ← MkDocs 文档源
└── tests/
```

### 核心机制

**一句话**：所有功能围绕 `Runner.run_sync(agent, input)` 这个调用展开——Runner 跑 Agent Loop，Agent 之间通过 Handoff 切换主控权，所有过程自动写入 Trace。

整套 SDK 围绕 **Runner.run_sync(agent, input)** 这一调用构建。Runner 进入 Agent Loop：将 input 喂给 Agent，Agent 调用 LLM，LLM 输出可能含 tool_use 或 handoff；tool_use 由 SDK 内部执行后回写消息流；handoff 切换到目标 Agent 继续 Loop；最终拿到 final_output。Sessions 模块负责跨 run 的对话历史持久化，Tracing 模块自动埋点每次 LLM 调用、每次 tool_use、每次 handoff，输出标准化 trace。Guardrails 在 input/output 阶段插入校验。Sandbox 子系统额外把 Agent 装进受控的本地或远程容器，让 Agent 拥有真实文件系统、可执行命令、可跨长时间任务保留 workspace。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Handoff 机制**：用同步、显式、状态化的"移交"代替消息总线作为多 Agent 协作模式。Agent A 可以在自己的工具里声明 `handoff_to=B`，Runner 看到后保留对话历史、切换主控 Agent 到 B，继续同一个 Run。
2. **Tracing 自动埋点**：每次 LLM 调用、每次 tool_use、每次 handoff 都被自动记录为 trace 节点，输出可消费的 Span/Event 数据，支持 Trace UI 可视化。
3. **Function Tool + 自动 Schema**：用 Python 函数加装饰器即可注册为 Agent 工具，`function_schema.py` 自动从函数签名+类型注解+docstring 生成 LLM 可用的 JSON Schema，无需手写工具描述。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `agent.py` | Agent 怎么定义 | 不可变配置对象：指令 + 工具 + handoffs + guardrails |
| `run.py` + `run_state.py` | Agent Loop 怎么跑 | Runner 状态机驱动 + RunState 持久化 |
| `handoffs/` | Agent 之间怎么传任务 | 同步移交，保留历史，切换主控 Agent |
| `tracing/` | 怎么追溯 Agent 决策 | 自动埋点 LLM 调用 / tool_use / handoff，输出 Span 树 |
| `tool.py` + `function_schema.py` | 工具怎么注册 | 装饰器 + 自动生成 JSON Schema |
| `guardrail.py` | 输入输出怎么校验 | 在 Run 前后插入校验函数，违规直接中断 |
| `sessions/` + `memory/` | 跨 Run 对话怎么保留 | Session 抽象，可持久化到 SQLite/Redis |
| `retry.py` | API 失败怎么恢复 | 指数退避 + 错误类型分类的重试策略 |
| `apply_diff.py` | 代码改动怎么应用 | Sandbox Agent 改 workspace 时的统一 diff 协议 |
| `sandbox/` | Agent 怎么跨长任务保留状态 | 受控容器 + Manifest 描述 workspace 内容 |

### 详细说明

- **`agent.py` Agent 抽象**：Agent 是不可变的配置对象，包含 `instructions`、`tools`、`handoffs`、`guardrails`、`model`、`model_settings`。同一个 Agent 可以被多次复用，状态通过 RunState 在外部维护。这种"行为定义与状态分离"的设计让 Agent 易测试、可序列化、可热替换。

- **`handoffs/` 移交机制**：Handoff 是声明式的——Agent A 在工具里声明 `Handoff(target=B)`，Runner 在 Loop 里检测到 handoff 类型的 tool_use 后切换到 B 继续。整个 Run 共享同一个对话历史和 Trace，对外仍然是"一次任务"。比"A 给 B 发消息"模式更轻量，避免了消息总线的协议设计。

- **`tracing/` Trace 数据模型**：Trace 是层级化的 Span 树。一次 Run 是根 Span，每次 LLM 调用、每次 tool_use、每次 handoff 是子 Span，每个 Span 有 attributes（输入/输出/耗时/错误）。Span 数据可以推送到 OpenAI Tracing UI 或自定义后端。这套数据模型可以直接用作通用 Agent 系统的可观测性基础。

- **`tool.py` 多种工具来源**：支持三类工具——Function Tool（Python 函数）、MCP Tool（外部 MCP 服务器）、Hosted Tool（OpenAI 托管）。三种工具用同一个 ToolDefinition 抽象表达，Agent 调用时不感知差异。这种设计让 Agent 工具集可以混合本地实现和远程服务。

- **`sandbox/` 长任务执行环境**：SandboxAgent 装进容器（本地 UnixLocalSandboxClient 或远程 sandbox 服务），可读写真实文件系统、跑命令、维护跨任务 workspace。Manifest 声明初始环境（如 GitRepo），Sandbox 启动后 Agent 用类似真实开发者的方式工作。这是"持久化工作环境"的现成方案。

- **`function_schema.py` 自动 Schema**：Python 函数加 `@function_tool` 装饰器后，SDK 解析函数签名（参数名/类型/默认值）+ docstring（描述），生成 OpenAI Function Calling 标准的 JSON Schema。开发者不用手写 schema，类型注解即文档。

## 4. 关键细节

- **`run_state.py` 是最大的文件（129 KB）**：状态机的复杂度都在这里。如果要深读 SDK，从这里开始。
- **`tool.py` 73 KB**：三种工具来源的统一抽象。Function Tool 与 MCP Tool 在调用接口上完全一致，仅在执行路径上分流。
- **`apply_diff.py`**：Sandbox 场景下 Agent 改代码的统一 diff 协议。包含完整的 diff 解析、应用、冲突检测逻辑。
- **`examples/` 目录**：包含多 Agent 编排（research bot、customer service triage 等）、handoff 模式、sandbox 工作流的可运行示例。
- **MCP 集成**：`mcp/` 子目录原生支持 MCP 协议。Agent 可以直接调用 MCP server 提供的工具，把外部能力（数据库、第三方 API）接入工作流。
- **Provider-agnostic**：通过 any-llm / LiteLLM 支持 100+ LLM。Agent 配置时指定 model 字符串（如 `"gpt-4"`、`"claude-3-opus"`），底层自动路由到对应提供商。
- **Sessions 双后端**：默认内存 Session（进程内），可选 SQLAlchemy（任意 SQL 数据库）或 Redis。Session 抽象统一，切换后端不改业务代码。
- **Pyright + mypy 双类型检查**：项目配置了两套类型检查器，对类型严谨度要求高。这反映了"Agent 系统的状态机复杂度需要静态类型保护"的工程经验。
