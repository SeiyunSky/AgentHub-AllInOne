# AgentHub 架构现状报告
> 生成日期：2026-06-08  
>
> 2026.8.3
>
> 鉴于王晨晖（Uzemiu）在本次项目中，只是在很前期照搬了一个10k行代码的已知项目作为前端，并且在后续的合作过程中敷衍、消极和态度不认真。
> 
> 在近期明确了解到此人在项目进行过程中，故意不认真，故意不沟通，故意不配合，敷衍项目，并在身后诽谤团队成员的情况后，现留此告示。
>
> 项目主体核心贡献人是  SeiyunSky 及 Musuyin，次要贡献人为liu pan 和 fengyuxuan。
> 
> 王晨晖（Uzemiu）的全部贡献为 ：
> 
> 照搬前端代码并不进行格式修改，现在的前端全部是经由SeiyunSky重新设计优化的。
> 
> 直接复制需求用ai生成的代码并且不进行审阅。30分钟生成一堆垃圾，导致我和musuyin要花成倍的时间去修改修正。
> 
> 仅有的MCP部分，也是在“你再不做，你真的相当于什么都没做了”，用ai生成的。
> 
> 在ai开发上的贡献度为0，在核心代码的贡献度为0，在设计框架的贡献度为0，望周知。
> 

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [本地开发配置](All_Things_YOU_NEED_TO_KNOW/本地开发配置.md) | **新成员从这里开始** — 软件安装、环境变量、启动命令、踩坑记录 |
| [开发日志 1 — 架构选型](All_Things_YOU_NEED_TO_KNOW/开发日志%201%20—%20架构选型.md) | 技术选型背景与决策 |
| [开发日志 2 — 前端架构设计](All_Things_YOU_NEED_TO_KNOW/开发日志%202%20-%20前端架构设计.md) | 前端模块设计 |
| [开发日志 3 — 后端架构设计](All_Things_YOU_NEED_TO_KNOW/开发日志%203%20-%20后端架构设计.md) | 后端模块设计 |
| [开发日志 — Agent 管理与 Skill 子系统](All_Things_YOU_NEED_TO_KNOW/开发日志%20-%20Agent管理与Skill子系统实现.md) | Agent/Skill CRUD 实现过程 |
| [开发日志 — 适配器层与 MCP 服务实现](All_Things_YOU_NEED_TO_KNOW/开发日志%20-%20适配器层与MCP服务实现.md) | Adapter 层块级协议对齐 |
| [开发日志 — 消息显示 Bug 修复与 UI 优化](All_Things_YOU_NEED_TO_KNOW/开发日志%20-%20消息显示Bug修复与UI优化.md) | SSE 竞态 Bug 修复、表情包、UI 更新（2026-06-08） |
| [需求汇总 6.2](All_Things_YOU_NEED_TO_KNOW/AgentHub%206.2%20需求汇总.md) | 待实现功能清单 |

---

## 一、项目定位

AgentHub 是一个以 **IM 为交互界面的多 Agent 协作平台**，目标是让用户像发消息一样驱动 AI Agent 完成复杂任务。

**核心设计思路**：不同于单 Agent 对话产品，AgentHub 的模型是一个**分层 Agent 网络**：

- **Orchestrator 主 Agent**：接收用户意图，负责任务理解、拆解与调度。它本身不执行具体工作，而是通过 22 个内置工具驱动下层 Agent 并行运作，管理依赖关系（blocked_by 图）、等待结果、汇总回复。
- **专属子 Agent**：执行具体任务（写代码、查资料、审查代码等），每个 Agent 有独立的 Thread、独立的 Adapter（Claude CLI / Codex / OpenAI 兼容接口），互相隔离。
- **多种对话模式并存**：单聊（直连子 Agent）、群聊（Orchestrator 主导）、broadcast（多 Agent 自由对话，概率自决是否回复）、@个体（复用历史 Thread）、local_edit（代码文件编辑），覆盖不同场景。

**关键工程约束**：
- 所有 Agent 输出通过 **SSE 块级流式协议**实时推送到前端（block_start / block_delta / block_stop），用户能实时看到每个 Agent 的思考过程和工具调用。
- 高风险操作（文件写入、代码部署）走 **ApprovalHook 审批闭环**，在 asyncio 层面阻塞等待用户授权，不打断流式输出。
- 代码执行和应用部署运行在**会话级 Docker 容器沙箱**内，每个会话隔离，结果可通过反向代理直接在前端 iframe 预览。
- 当前运行在 Windows 开发环境，对 Claude CLI subprocess 调用、Docker Desktop 网络、进程间通信均做了专项适配。

---

## 二、技术栈

### 前端

| 库 / 框架 | 用途 |
|---|---|
| Vue 3 + TypeScript | 主框架，Composition API |
| Pinia | 状态管理：chat / workflow / conversations / deployments / sandboxFiles 等多个 store |
| Vue Router | 路由管理，侧边栏驱动布局 |
| Element Plus | 基础 UI 组件库 |
| Tailwind CSS v4 | 原子化样式 |
| Shiki | 代码高亮（支持 100+ 语言，SSR 友好） |
| Monaco Editor | Diff 编辑器（Artifact Apply / Edit 模式） |
| markdown-it | 消息 Markdown 渲染 |

### 后端

| 库 / 框架 | 用途 |
|---|---|
| Python 3.13 + FastAPI | 主框架，async 原生支持，SSE / WebSocket 端点 |
| SQLAlchemy 2.x + Alembic | ORM + 迁移，11 张表 |
| MySQL | 主数据库（支持 MariaDB） |
| Redis | 可选，用于 Auth token 缓存 |
| structlog | 结构化日志，console / JSON 双格式，trace_id contextvars 注入 |
| Docker SDK | DockerRuntimeService，会话级容器生命周期管理 |

### LLM 接入层

| SDK | 对应 Adapter |
|---|---|
| Anthropic SDK | 主 Orchestrator LLM 调用 |
| Claude Code CLI（subprocess） | ClaudeAdapter — 子 Agent 执行，stdin 传 prompt 绕 Windows 8191 字符限制 |
| OpenAI SDK | CustomAdapter — 兼容 Deepseek / Qwen / Ollama 等 |
| MCP SDK | CodexAdapter — MCP 协议接入 Codex |
| opencode CLI（subprocess） | OpencodeAdapter |

### 测试

| 工具 | 用途 |
|---|---|
| pytest + pytest-asyncio | 后端集成测试 + 单元测试 |
| vitest | 前端单元测试 |

---

## 三、整体架构概览

### 3.1 请求入口与三条通信通道

```
用户浏览器
  ├── GET  /api/v1/chat/stream    # SSE — 先建连，接收所有 Agent 事件流
  ├── POST /api/v1/chat           # HTTP — 发消息（SSE 必须先于此建立）
  └── WS   /api/v1/ws            # WebSocket — 审批决策信令
```

**SSE 先连后发**是一个关键约束：群聊路径下，后端在 POST 返回前就开始向 SSE 推事件，前端必须先建立 SSE 连接才能收到第一个 `agent_start` 事件，`useChat.sendMessage()` 严格保证这个顺序。

### 3.2 ChatService 五路分流

```
ChatService.handle_message()
  ├── local_edit    → DiffApplyService（直接修改沙箱文件，不经 LLM）
  ├── 单聊          → ThreadService.create_thread → AdapterRegistry → 对应 Adapter
  ├── @个体         → ThreadService.resume_or_create（复用历史 Thread 上下文）
  ├── broadcast     → 遍历会话所有 Agent，各自起独立 Thread
  │                   每个 Agent 70% 概率回复 / 30% 仅发已读回执
  │                   互聊深度 ≤ 1，防止无限自对话
  └── 群聊          → OrchestratorService.start_loop（主 Agent 接管）
```

每条消息进入 ChatService 前，会先获取 **conversation 级别锁**，并发消息进入 pending 队列串行处理。

### 3.3 Orchestrator 八步 Agent Loop

群聊模式的核心，每轮循环：

```
① abort 检查          — 检测 stop 信号，立即退出
② pending_events 消费  — 处理子 Thread 完成通知（wake_event）
③ 六层 Prompt 构建     — 静态系统 prompt + 动态上下文（会话历史 / 可用 Agent / 任务状态等）
④ Anthropic API 调用   — 携带 22 个工具 schema，流式接收 ContentBlock
⑤ 错误恢复            — max_tokens → 续写；prompt_too_long → global_summarize；api_error → 指数退避
⑥ end_turn 判断       — 无工具调用则输出最终回复，退出循环
⑦ 工具派发            — PRE_TOOL_USE hooks → 执行工具 → POST_TOOL_USE hooks
⑧ 上下文压缩          — token 超阈值时 maybe_compact，避免上下文窗口溢出
```

子 Agent 执行时，主 Agent 挂起等待 `wake_event`（asyncio.Event），子 Thread 完成后触发唤醒，主 Agent 继续下一轮循环消费结果。

### 3.4 22 个 Orchestrator 工具分组

| 组 | 工具 | 作用 |
|---|---|---|
| A. 任务调度 | `dispatch_to_agent` / `read_thread_status` / `get_thread_result` / `cancel_thread` | 派发子 Agent、轮询 / 等待结果 |
| B. 任务链 | `create_task_plan` / `add_task` / `update_task` / `get_task_plan` / `present_task_plan_for_review` | 结构化多步任务编排 |
| C. 用户交互 | `respond_to_user` / `request_approval` / `ask_user` | 回复 / 审批阻塞 / 提问 |
| D. 上下文 | `read_conversation_history` / `list_available_agents` / `get_conversation_context` | 读取上下文信息 |
| E. 文件沙箱 | `create_file` / `edit_file` / `read_file` / `list_directory` | 沙箱路径校验，16KB 结果截断 |
| F. 部署 | `deploy_app` / `stop_app` / `read_app_logs` | Docker 容器全生命周期 |
| G. 网络 | `fetch_url` | HTTP 抓取 |

### 3.5 Hook 执行链

每次工具调用前后，经过两条 Hook 链：

```
PRE_TOOL_USE（同步串行）:
  PreExecutionHook → 黑名单检查 + 路径穿越防护
  ApprovalHook    → 高风险工具（create_file / edit_file / deploy_app）阻塞等待用户审批
                    asyncio.Event 挂起主 Agent，WS 推审批气泡给前端
                    用户 Approve / Reject → DB 落库 → set Event → 主 Agent 继续

POST_TOOL_USE（异步）:
  PostExecutionHook → 审计日志落库 + CodeBlock SSE 推送（文件创建/修改可视化）
```

### 3.6 SSE 事件协议

前端 `useSSE` 处理 10 种事件，驱动两个独立状态机：

```
事件                     → chat store（消息气泡）     → workflow store（侧边工作流视图）
─────────────────────────────────────────────────────────────────────────
agent_start             → 新建 AgentStreamingState   → onAgentStart（thread 初始化）
block_start/delta/stop  → 追加 / 更新 / 完成 block   → onBlockStart/Delta/Stop
agent_done              → commitAgentStreaming        → onAgentDone（token 统计）
agent_error             → failStreamingAgent         → onAgentError
round_done              → clearRound                 → persistCurrent（快照落库）
message_appended        → appendPersistedMessage     → （审批 / diff 消息非 streaming 路径）
read_receipt            → addReadReceipt             → （broadcast 已读回执）
queue_drained           → disconnect SSE             → —
```

**多 Agent 并发 streaming**：`chat store` 的 `streamingMap` 以 `convId → agentId → AgentStreamingState` 三级嵌套索引，群聊中主 Agent 和多个子 Agent 可同时维护各自的气泡，互不干扰（Teams 风格并发气泡）。

### 3.7 Docker 沙箱与预览

```
deploy_app 工具调用
  → DockerRuntimeService.start_container()
    → docker run -p 0:8000（host 随机端口）
    → 记录 host_port（Windows Docker Desktop 不走 bridge IP，必须用 localhost:host_port）
  → /preview/{conv_id}/ 反向代理 → localhost:host_port
    → 前端 PreviewCard iframe 内嵌预览

闲置 30 分钟自动回收；每次前端访问 touch 刷新计时器；关闭时清理全部容器
```

---

## 四、核心已完成模块

### 4.1 后端

| 模块 | 位置 | 完成状态 | 说明 |
|---|---|---|---|
| **FastAPI 应用入口 & 生命周期** | `backend/main.py` | ✅ 完整 | 自动建库/迁移、seed、hook 注册、Docker 运行时初始化、stale thread 收尸 |
| **ChatService 路由分发** | `backend/services/chat_service.py` | ✅ 完整 | 单聊/群聊/broadcast/@个体/local_edit 五路分流；conversation 锁 + pending 队列；handle_stop 紧急中止 |
| **OrchestratorService 主 Agent Loop** | `backend/services/orchestrator/service.py` | ✅ 完整 | 八步循环；wake_event 子 Thread 唤醒机制；token 累计；max_tokens/prompt_too_long/api_error 三路恢复；stop 中止检查 |
| **Orchestrator 22 个工具** | `backend/services/orchestrator/orchestrator_tools.py` | ✅ 完整 | 任务调度(4) + 任务链(5) + 用户交互(3) + 上下文检索(3) + 文件沙箱(4) + 部署(3) + 网络(1) |
| **ToolRegistry & 工具注册装饰器** | `backend/services/orchestrator/tool_registry.py` | ✅ 完整 | Pydantic→JSON Schema 转换（$ref inline 展开）；16KB tool_result 截断；dispatch/wrap 抽象 |
| **Adapter 抽象层 + Registry** | `backend/adapters/base.py` `registry.py` | ✅ 完整 | StreamInput 统一入参；AgentAdapter 抽象基类；startup seed_from_db |
| **ClaudeAdapter（Claude Code CLI）** | `backend/adapters/claude.py` | ✅ 完整 | stdin 喂 prompt（绕 Windows 8191 字符限制）；stream-json 解析；token 上报 |
| **CodexAdapter（MCP 子进程）** | `backend/adapters/codex.py` | ✅ 完整 | MCP 协议；事件转换到 AgentEvent 协议 |
| **CustomAdapter（OpenAI 兼容 HTTP）** | `backend/adapters/custom.py` | ✅ 完整 | OpenAI SDK 流式；支持 Deepseek/Qwen/Ollama 等自定义端点 |
| **OpencodeAdapter（opencode CLI）** | `backend/adapters/opencode.py` | ✅ 完整 | CLI 子进程流式；stream-json 协议 |
| **SSE StreamService** | `backend/services/stream_service.py` | ✅ 完整 | 内存事件队列；abort 标志；push_round_done/push_queue_drained |
| **Hook 系统** | `backend/hooks/` | ✅ 完整 | PRE_TOOL_USE / POST_TOOL_USE / PRE_ORCHESTRATE / POST_ORCHESTRATE；HookManager；ApprovalHook（含超时 10 分钟）；PreExecutionHook（黑名单 + 路径校验）；PostExecutionHook（审计 + CodeBlock SSE 推送） |
| **ApprovalHook 审批闭环** | `backend/hooks/approval.py` | ✅ 完整 | asyncio.Event 阻塞等待用户决策；MessageAppendedEvent 推送（绕过 streaming 路径）；DB 持久化决策结果 |
| **DockerRuntimeService** | `backend/services/docker_runtime.py` | ✅ 完整 | 镜像 build/pull；会话级容器 start/stop/exec；host 端口映射（跨 Windows/Linux）；闲置回收（30 min）；关闭时清理 |
| **ThreadService + 调度器** | `backend/services/thread_service.py` | ✅ 完整 | create/resume_or_create/create_task_plan；blocked_by 依赖图调度；mark_running/done/error/suspended/cancelled；schedule_conversation_staggered（broadcast 错峰起 Thread）|
| **broadcast 广播群聊** | `backend/services/chat_service.py` | ✅ 完整 | 70%/30% 概率自决回复；sentinel __READ_RECEIPT__ 已读不回；互聊 depth ≤ 1 控制；表情包支持 |
| **MessageService** | `backend/services/message_service.py` | ✅ 完整 | create_user/assistant_message；update_approval_block；list_recent；reap_stale_approval_blocks |
| **DB 模型 + Alembic 迁移** | `backend/models/` `backend/migrations/` | ✅ 完整 | 6 张表：users / agents / skills / agent_skills / conversations / conversation_agents / messages / threads / read_receipts / audit_log / workflows；5 次迁移版本 |
| **Skill 系统（DB inline 存储）** | `backend/services/skill_service.py` `backend/models/skill.py` | ✅ 完整 | scan_builtin 扫 .md/.json 文件写库；inline content 列（已废弃 file_path）|
| **Agent Builder Service** | `backend/services/agent_builder_service.py` | ✅ 完整 | 对话式构建 Agent；LLM 生成 prompt/description/tags |
| **ContextCompactor** | `backend/services/orchestrator/context_compactor.py` | ✅ 完整 | maybe_compact（token 阈值判定）；global_summarize（prompt_too_long 路径）|
| **DiffApply Service** | `backend/services/diff_apply_service.py` | ✅ 完整 | 沙箱路径校验 + 文件 diff 应用 |
| **PreviewService + 反向代理** | `backend/services/preview_service.py` `backend/api/v1/preview.py` | ✅ 完整 | /preview/{conv_id}/ → 容器 host_port 反向代理转发；流量 touch 刷新闲置计时 |
| **WorkflowService（快照持久化）** | `backend/services/workflow_service.py` | ✅ 完整 | 每轮 workflow 快照落库；历史回看查询 |
| **Auth 模块（JWT）** | `backend/services/auth_service.py` `backend/api/v1/auth.py` | ✅ 完整 | 注册/登录/JWT token；bcrypt 密码哈希；Redis 可选 |
| **ResponseEnvelope + TraceId Middleware** | `backend/api/middleware/` | ✅ 完整 | 统一 `{code, data, message}` 包装；trace_id contextvars 注入 |
| **Squad 预设小组** | `backend/api/v1/squads.py` | ✅ 完整 | dev_squad / data_squad / chat_squad JSON 配置；一键创建群聊 |
| **Seed 系统（岁家 Agents）** | `backend/seeds/agents.py` `backend/prompts/agents/` | ✅ 完整 | Orchestrator + Coder/Reviewer/Research 模板 + 岁年/岁晚/岁熙/岁汪四个角色 Agent |

### 4.2 前端

| 模块 | 位置 | 完成状态 | 说明 |
|---|---|---|---|
| **useSSE（SSE 事件路由）** | `frontend/src/composables/useSSE.ts` | ✅ 完整 | 处理全部 8 种 SSE 事件（agent_start/block_start/block_delta/block_stop/agent_done/agent_error/round_done/message_appended/read_receipt/queue_drained）|
| **useChatStore（多 Agent 并行流式）** | `frontend/src/stores/chat.ts` | ✅ 完整 | 按 agentId 索引的 AgentStreamingState（解决群聊多气泡同时 streaming 的老问题）；thread 调度卡片本地虚拟；审批状态管理；broadcast 已读回执；打字流动画标记 |
| **useChat composable** | `frontend/src/composables/useChat.ts` | ✅ 完整 | sendMessage（先 SSE 再 POST 顺序保证）；stopGeneration 乐观 UI + 取消 |
| **WorkflowStore + 历史回看** | `frontend/src/stores/workflow.ts` | ✅ 完整 | SSE 事件驱动 WorkflowThread 状态机；persistCurrent 每轮快照落库；historyMap 历史回看；skipNextPersist stop 路径跳过 |
| **ChatContainer / MessageList / MessageGroup / AgentBubble** | `frontend/src/components/chat/` | ✅ 完整 | 群聊多 Agent 气泡同时显示（Teams 风格）；streaming cursor；超高内容折叠 |
| **ApprovalOverlay / ApprovalBlock** | `frontend/src/components/chat/ApprovalOverlay.vue` `blocks/ApprovalBlock.vue` | ✅ 完整 | 结构化展示 tool_input；Approve/Reject 按钮；审批结果持久化回显 |
| **DiffCard + useDiff** | `frontend/src/components/chat/artifacts/DiffCard.vue` `composables/useDiff.ts` | ✅ 完整 | Monaco Diff 编辑器；Apply 按钮调后端沙箱 diff apply |
| **WorkflowView** | `frontend/src/components/layout/WorkflowView.vue` | ✅ 完整 | Agent thread 卡片；工具调用详情；历史轮次回看 |
| **DeployCard + DeploymentsView** | `frontend/src/components/chat/artifacts/DeployCard.vue` | ✅ 完整 | deploy_app 结果展示；URL 跳转；运行/失败状态 |
| **PreviewCard** | `frontend/src/components/chat/artifacts/PreviewCard.vue` | ✅ 完整 | 内嵌 iframe 预览已部署应用 |
| **MarkdownRenderer + CodeBlock** | `frontend/src/components/common/MarkdownRenderer.vue` | ✅ 完整 | markdown-it + Shiki 语法高亮；复制代码；最大高度折叠 |
| **AgentForm + AgentBuilderDialog** | `frontend/src/components/agents/` | ✅ 基本完整 | Agent 创建/编辑；只读 UI（非创建者）；Builder 对话式构建（mock 未对接 API，见 TODO）|
| **SkillForm + SkillsPanel** | `frontend/src/components/layout/SkillsPanel.vue` | ✅ 完整 | Skill CRUD；Markdown 编辑 |
| **ChatInput** | `frontend/src/components/chat/ChatInput.vue` | ✅ 完整 | @mention 选择器；文件上传；code range 选择（local_edit）；draft 保存 |
| **MentionPicker** | `frontend/src/components/chat/MentionPicker.vue` | ✅ 完整 | @ 触发；实时过滤 Agent 列表 |
| **ConversationSettingsDrawer** | `frontend/src/components/chat/ConversationSettingsDrawer.vue` | ✅ 完整 | 会话参与 Agent 管理；头像显示 |
| **NewChatDialog** | `frontend/src/components/chat/NewChatDialog.vue` | ✅ 完整 | 单聊/群聊/broadcast 模式选择；小组快速创建 |
| **主题系统 + SettingsDialog** | `frontend/src/stores/theme.ts` | ✅ 完整 | 多 Accent 配色；深色/浅色；Settings 对话框 |
| **布局系统（SplitPanes + NavRail）** | `frontend/src/components/layout/` | ✅ 完整 | 可拖拽三栏布局（Left/Chat/Right Panel）；NavRail 导航 |
| **LoginView / RegisterView** | `frontend/src/views/` | ✅ 完整 | 重新设计风格；对齐真实 Agent 支持 |
| **SandboxFilesView** | `frontend/src/components/layout/SandboxFilesView.vue` | ✅ 完整 | 沙箱文件浏览；block_start code 触发 debounce 刷新 |

### 4.3 测试

| 测试模块 | 位置 | 内容 |
|---|---|---|
| **Orchestrator Loop 集成测试** | `backend/tests/integration/test_orchestrator_loop.py` | 10 个测试：end_turn 收敛、tool_use 派发、PRE_TOOL_USE hook、max_tokens 恢复/放弃、prompt_too_long 触发 summarize、API 错误退避、wake_event 唤醒、多 tool_call 串行 |
| **Group Chat / Mention 集成测试** | `test_group_chat.py` `test_group_mention.py` | 群聊路由、@个体路由 |
| **Single Chat 集成测试** | `test_single_chat.py` | 单聊全链路 |
| **Claude / Codex / Custom / OpenCode Adapter 单元测试** | `tests/unit/` | Adapter 事件序列；cancel_event；token 上报 |
| **Auth API 集成测试** | `test_auth_api.py` | 注册/登录/token |
| **Agents / Skills / Messages API 集成测试** | `test_agents_api.py` `test_skills_api.py` `test_messages_api.py` | CRUD |
| **Diff Apply 集成测试** | `test_diff_apply.py` | 沙箱路径校验；文件 diff 应用 |
| **Response Envelope / TraceId Middleware 集成测试** | `test_response_envelope.py` `test_trace_id_middleware.py` | 中间件 |
| **WS Approval 集成测试** | `test_ws_approval.py` | 审批 WS 流程 |
| **Agent Builder 集成测试** | `test_agent_builder.py` | 对话式 Agent 构建 |
| **Context Compactor 集成测试** | `test_context_compactor.py` | maybe_compact / global_summarize |
| **Workflows API 集成测试** | `test_workflows_api.py` | 快照 CRUD |
| **Registry 单元测试** | `tests/unit/test_registry.py` | Adapter 注册/覆盖/未知类型 |

---

## 五、贡献者分析

### 5.1 提交量统计

> 注：「涉及文件数」含大量无效文件，不具参考价值，改用**有效净增代码行数**（已排除噪音文件）。贡献度占比为基于代码阅读的综合评估，兼顾代码量、模块复杂度与 Prompt 工程工作量。

| 贡献者 | 总 commits | 有效净增行 | Feat commits | Fix commits | 贡献度占比 | 主要领域 |
|---|---|---|---|---|---|---|
| **SeiyunSky / 沫路**（同一人） | 86 | ~33,800 | — | — | **~52%** | 整体架构设计、核心功能全栈实现、核心Agent Loop、Orchestrator完整实现、Prompt工程、前端设计优化 |
| **musuyin** | 48 | ~8,900 | — | — | **~26%** | Adapter全链路打通、后端特性实现 |
| **Wang / Uzemiu**（同一人） | 55 | ~11,600 | — | — | **~20%** | 前端框架 + UI 功能 |

### 5.2 各人核心贡献领域（按功能模块）

> 格式：**模块名** — 主责人（贡献内容）

---

#### 项目立项 & 架构设计
**adam** — 前期调研选型；定义 Orchestrator ↔ Adapter 通信协议（AgentEvent 事件模型、AgentAdapter 抽象接口、工具 Input Schema、业务 Pydantic DTO）；ContentBlock 数组 + 块级流式 SSE 协议设计（block_start/delta/stop）；数据结构设计 + ORM + Alembic 迁移体系搭建

**Wang/Uzemiu** — 前端脚手架搭建（路由驱动布局、LeftPanel + RouterView 框架）

---

#### OrchestratorService 八步 Loop
**adam** — 完整实现八步循环：abort 检查 → pending_events 消费 → 六层 Prompt 管道（prompt_builder.py）→ LLM 调用 → 三路错误恢复（max_tokens/prompt_too_long/api_error）→ end_turn 判断 → 工具派发 → 上下文压缩；子 Thread 唤醒机制（wake_event）；context_compactor 接入；提示词多轮调优（工具描述瘦身、占位符防御）

---

#### 22 个 Orchestrator 工具
**adam** — 全部实现（任务调度 4 + 任务链 5 + 用户交互 3 + 上下文 3 + 文件沙箱 4 + 部署 3 + 网络 1）；tool_registry：Pydantic → JSON Schema 转换、`$ref` inline 展开（绕 Anthropic 不处理 `$defs`）、16KB tool_result 截断

**Musuyin** — 子 Agent system_prompt 注入；D7-blocker 修复（`seed_from_db` 改同步 + `_run_thread` 独立 `SessionLocal`）

---

#### Hook 体系（PRE/POST_TOOL_USE）
**adam** — HookManager 注册中心（同步串行链/异步线程池调度、异常隔离、深拷贝 ctx 防审计污染）；PreExecutionHook（黑名单 + 路径穿越防护）；ApprovalHook（asyncio.Event 阻塞等待）；PostExecutionHook（异步审计）

---

#### 审批闭环（ApprovalHook + 前端 ApprovalOverlay）
**adam** — 审批决策 DB 持久化；ApprovalUI 结构化展示（tool_input JSON 化）；`MessageAppendedEvent` 字段映射修复（审批气泡空白）

**Musuyin** — `message_appended` SSE 事件（approval/diff 消息走非 streaming 路径，绕开流式气泡混入）；Approval 改用 http 实例

**Wang/Uzemiu** — 启动时清理僵尸 pending approval blocks；approval overlay 在 SSE stream 结束后不消失

---

#### Adapter 层
**adam** — cancel_event 中止机制；ClaudeAdapter：stdin 传 prompt（绕 Windows 8191 字符限制）、全量 stdout read（绕 readline 64KB 限制）、`_flatten_for_cli` 换行转空格；Windows cmd.exe 兼容性重构；token usage 上报

**Musuyin** — Claude 接入模式从 Anthropic SDK 改为 CLI subprocess；CodexAdapter 适配新版 CLI + 用户身份注入；`StreamInput` 传 `agent_name` 修复 agent_start 显示 ID 问题

---

#### Docker 一键部署（DockerRuntimeService + deploy_app 工具链）
**adam** — DockerRuntimeService（镜像 build/pull、会话级容器生命周期、host 端口映射解决 Windows Docker Desktop 不走 bridge IP、30 分钟闲置回收）；`deploy_app` / `stop_app` / `read_app_logs` 工具

---

#### 沙箱文件系统（文件工具 + SandboxFilesView）
**adam** — 文件工具沙箱路径校验（`_resolve_sandbox_path`）；tool_result 上限 16KB；SandboxFilesView debounce 刷新 + PreviewCard iframe

**Musuyin** — DiffApply 走沙箱路径，修补任意路径写入漏洞

---

#### SSE 流式协议 & StreamService
**adam** — 块级协议设计；主 Agent 工具调用时推 BlockStart/Stop 事件；SSE 先连后发顺序保证（group 路径）；`agent_start` 即时推送 + token usage

**Musuyin** — `agent_start` 携带 avatar 字段；`message_appended` 事件

---

#### 群聊 / Orchestrator 群聊路由（ChatService）
**adam** — ChatService 五路分流（single/broadcast/mention/group/local_edit）；conversation 锁 + pending 队列；handle_stop 中止；broadcast 模式：概率自决回复（70%/30%）、`__READ_RECEIPT__` sentinel、互聊深度 ≤ 1 控制、打字机回复、表情包；多轮自对话无限调用修复

---

#### 前端多 Agent 并行 Streaming（chat.ts / useSSE）
**adam** — `streamingMap<convId, Map<agentId, AgentStreamingState>>` 设计（解决群聊多气泡并发 streaming 问题）；`handleSchedulingTool`（从 tool_use block input 虚拟出 ThreadActivity 调度卡片）；`isSentinelOnly` 检测（丢弃纯 `__READ_RECEIPT__` 气泡）；stop 流程前端侧

**Wang/Uzemiu** — streaming commit 时从 conversationsStore 兜底头像名称；`appendPersistedMessage` ID 碰撞保护

---

#### Workflow 视图（WorkflowView + workflow.ts + 后端持久化）
**adam** — WorkflowView 前端初版（工具调用详情展示）

**Musuyin** — 持久化全链路：每轮快照落库（WorkflowService）、`persistCurrent`（round_done 触发）、historyMap 历史回看、`skipNextPersist` stop 路径跳过；`workflow.ts` 状态机（onAgentStart/onBlockStart/onBlockStop/onAgentDone/onAgentError）

---

#### Agent / Skill 子系统
**Musuyin** — Agent/Skill CRUD 后端实装；AgentBuilderService（LLM 辅助创建）；Skill content 从文件迁至 DB；编辑页只读 UI（非创建者禁用）；GUGA 系统用户统一写权限；Agent type 可修改；Skill 修改不落文件

**Wang/Uzemiu** — 前端 Agent/Skill CRUD 页面；Skill CRUD（list/create/edit/delete）

---

#### Agent 头像全链路
**Musuyin** — 后端静态服务 + 消息携带头像快照；头像透传（适配器 / SSE / Workflow / 气泡）

**Wang/Uzemiu** — 前端气泡头像显示；会话设置中头像；streaming commit 时头像兜底

---

#### Artifact Apply（Diff 展示 + Monaco 编辑器）
**Musuyin** — DiffApply Service（沙箱路径校验 + diff 应用）+ 前端 DiffCard + Monaco Diff 编辑器 + Apply 打通

**Wang/Uzemiu** — Artifact Edit 模式（Monaco 编辑器 + 文件同步）；HTML 文件 Edit 的 iframe 分支

---

#### 前端 UI & 消息列表
**Wang/Uzemiu** — 消息列表滚动优化（切换会话自动滚底 + 向上加载更多）；scroll 节流；markdown-it + Shiki 代码高亮；@mention 输入；ApprovalBlock UI；消息 reaction；主题系统（多 Accent 配色 + Settings）；登录/注册页面重设计；消息气泡超高内容折叠；代码块最大高度；会话列表（archived 分类、时间戳、删除）；Agent Builder 双栏布局（mock，未对接 API）；前端 CLAUDE.md

---

#### 系统基建 & 稳定性 & Prompt 工程
**adam** —
- **structlog** + stdlib 桥接（console / JSON 双格式、trace_id contextvars 注入）
- 统一响应格式 `{code, message, data}`
- 启动收尸（stale thread / stale approval block）；`/chat/stop` 锁释放
- context_compactor **降级标志**（count_tokens API 失败后切字符数估算）
- seed 系统（岁家四角色 + dev_squad / data_squad）
- **Prompt 工程**：Orchestrator 系统提示词多轮迭代（六层管道设计；工具描述瘦身；占位符防御与自检清单；子 Agent 身份与人格提示词体系；岁家四角色人设提示词）

**Musuyin** — 启动时幂等建库（MySQL）；Alembic 自动迁移接入；CancelledError 漏 rollback 修复；UTC tzinfo 修复（前端显示晚 8 小时）
