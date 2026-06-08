# oh-my-claudecode (OMC)
## 1. 项目基本信息

- **项目名**：oh-my-claudecode（Yeachan-Heo/oh-my-claudecode）
- **GitHub**：https://github.com/Yeachan-Heo/oh-my-claudecode
- **Star 数 / 主要语言**：34.2k / TypeScript
- **简介**（≤200 字）：

Claude Code 的多 Agent 编排插件，安装在 Claude Code 内部运行。核心是 Team 模式：多个 Claude Agent 在共享任务列表上按阶段化流水线协作（plan → prd → exec → verify → fix）。v4.4.0 移除 MCP server 实现，改为通过 tmux 启动真实的 Claude / Codex / Gemini CLI 子进程作为 worker。提供 32 个专业 Agent、智能模型路由（Haiku/Sonnet/Opus 分级）、技能学习系统、HUD 状态栏、OpenClaw 事件桥接（转发给 Discord/Slack/Telegram）。定位：给命令行用户的多 Agent 加速器，不提供独立 IM 界面。

- **核心创新（一句话）**：用 tmux + 文件系统消息总线把多个 Agent CLI 子进程编排成一个"团队"，按 5 阶段流水线协作。

## 2. 项目架构概览

### 技术栈

- **语言**：TypeScript（Node.js 运行时）
- **核心依赖**：tmux（终端会话管理，用于 CLI worker 编排）、git worktree（多 worker 代码隔离）
- **目标宿主**：Claude Code CLI（作为插件运行）
- **可选集成**：Codex CLI、Gemini CLI、MCP 协议（部分弃用）

### 目录结构

```
oh-my-claudecode/
├── src/                              ← 核心运行时（TypeScript）
│   ├── team/                         ← 团队编排核心（60+ 个文件）
│   │   ├── runtime-v2.ts    (84 KB)  ← 团队运行时主循环 v2
│   │   ├── runtime.ts       (36 KB)  ← 旧版运行时
│   │   ├── runtime-cli.ts   (21 KB)  ← CLI worker 运行时
│   │   ├── tmux-session.ts  (38 KB)  ← tmux 会话管理（启动/关闭 pane）
│   │   ├── tmux-comm.ts             ← tmux send-keys / capture-pane 通信
│   │   ├── worker-bootstrap.ts (17 KB) ← worker 启动引导
│   │   ├── worker-health.ts          ← worker 健康检查
│   │   ├── worker-restart.ts         ← 僵死 worker 自动重启
│   │   ├── heartbeat.ts              ← 心跳协议
│   │   ├── inbox-outbox.ts  (12 KB)  ← worker 收发件箱（文件系统）
│   │   ├── leader-inbox.ts           ← Leader worker 专用收件箱
│   │   ├── outbox-reader.ts          ← 从 outbox 抓输出
│   │   ├── message-router.ts         ← 消息路由（按 role / @ / task）
│   │   ├── dispatch-queue.ts (16 KB) ← 任务分发队列
│   │   ├── task-router.ts            ← 任务投递到目标 worker
│   │   ├── role-router.ts            ← 同 role 多 worker 负载均衡
│   │   ├── stage-router.ts           ← 流水线阶段路由
│   │   ├── phase-controller.ts       ← 流水线阶段机
│   │   ├── git-worktree.ts  (25 KB)  ← 每个 worker 独立 worktree
│   │   ├── merge-orchestrator.ts (31 KB) ← 多 worktree 改动合并
│   │   ├── conflict-mailbox.ts       ← 合并冲突由 leader 仲裁
│   │   ├── governance.ts             ← worker 权限控制
│   │   ├── scaling.ts       (26 KB)  ← worker 扩缩容
│   │   ├── allocation-policy.ts      ← 任务分配策略（亲和性/负载/能力）
│   │   ├── capabilities.ts           ← worker 能力描述
│   │   ├── monitor.ts       (19 KB)  ← 团队总监控
│   │   ├── activity-log.ts           ← 活动日志
│   │   ├── audit-log.ts              ← 审计日志
│   │   ├── api-interop.ts   (48 KB)  ← API 互操作层
│   │   ├── mcp-team-bridge.ts (35 KB) ← MCP 桥接（v4.4.0 已弃用）
│   │   ├── usage-tracker.ts          ← Token 使用追踪
│   │   └── ... 共 60+ 个文件
│   │
│   ├── providers/                    ← Git 平台适配（GitHub/GitLab/Bitbucket）
│   ├── platform/                     ← 跨平台抽象
│   ├── interop/                      ← 互操作层
│   ├── mcp/                          ← MCP 协议集成
│   ├── openclaw/                     ← OpenClaw 事件桥接
│   ├── tools/                        ← 工具实现
│   ├── hooks/                        ← Claude Code 钩子集成
│   ├── hud/                          ← 状态栏 HUD
│   ├── installer/                    ← 插件安装器
│   ├── cli/                          ← omc 命令行入口
│   ├── commands/                     ← 用户可调命令
│   ├── notifications/                ← Discord/Slack/Telegram 通知
│   ├── skills/                       ← 自学习的可复用技能
│   ├── planning/                     ← 规划阶段实现
│   └── verification/                 ← 验证阶段实现
│
├── agents/                           ← 32 个专业 Agent 角色定义
├── commands/                         ← 用户命令定义
├── skills/                           ← 技能模板库
├── hooks/                            ← Claude Code Hook 定义
├── bridge/                           ← 事件桥接配置
├── missions/                         ← 任务模板
└── examples/                         ← 使用示例
```

### 核心机制

**一句话**：tmux 起 CLI 子进程当 worker，文件系统当消息总线，phase-controller 按 5 阶段流水线驱动，git worktree 隔离改动，最后 merge-orchestrator 合并。

OMC 装在 Claude Code 内部，通过 plugin 协议接管 Claude Code 的 Hook 与命令。当用户输入 `/team 3:executor "fix lint errors"` 时，phase-controller 进入 plan → prd → exec → verify → fix 流水线；每个阶段由 stage-router 决定派给哪个 role 的 worker；dispatch-queue 把任务文件写到目标 worker 的 inbox（文件系统）；tmux-session 在 tmux pane 里启动一个真实的 `claude` 或 `codex` 子进程作为 worker；worker 从 inbox 读任务、跑完 Claude Code Loop、把结果写到 outbox；outbox-reader 抓输出、message-router 决定下一步路由。每个 worker 有独立的 git worktree，最后由 merge-orchestrator 汇总。横切机制包括 heartbeat 心跳、worker-health 健康检查、worker-restart 自动救活、governance 权限控制、scaling 按负载扩缩容。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **5 阶段流水线模板**（`phase-controller.ts` + `stage-router.ts`）：plan → prd → exec → verify → fix 是经过实战验证的多 Agent 协作 DAG 骨架，每个阶段对应特定 role 的 worker。
2. **inbox/outbox 文件总线**（`inbox-outbox.ts` + `message-router.ts`）：每个 worker 一个 inbox 目录、一个 outbox 目录，消息以 JSON 文件追加形式存储。这种设计天然持久化、可重放、可观测。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `tmux-session.ts` + `tmux-comm.ts` | 怎么把交互式 CLI 当后端服务跑 | tmux send-keys 写 stdin、capture-pane 读 stdout |
| `runtime-cli.ts` + `worker-bootstrap.ts` | CLI worker 怎么启动和初始化 | bootstrap 协议 + 启动握手 |
| `inbox-outbox.ts` + `message-router.ts` | 多 worker 之间怎么传消息 | 文件系统两个目录，JSONL 追加，按规则路由 |
| `dispatch-queue.ts` + `task-router.ts` | 任务怎么分发给具体 worker | 队列 + 任务级路由（投递到目标 inbox） |
| `phase-controller.ts` + `stage-router.ts` | 多阶段流水线怎么驱动 | 阶段机 + 阶段级路由（决定派给哪个 role） |
| `role-router.ts` + `allocation-policy.ts` | 同 role 多 worker 怎么选 | 亲和性 / 负载 / 能力匹配的分配策略 |
| `heartbeat.ts` + `worker-health.ts` + `worker-restart.ts` | worker 崩了怎么办 | 心跳协议 + 僵死检测 + 从 checkpoint 自动重启 |
| `git-worktree.ts` + `merge-orchestrator.ts` | 多 worker 并行改代码怎么不冲突 | 每 worker 一个 worktree + 完成后批量合并 |
| `conflict-mailbox.ts` | 合并冲突怎么处理 | 冲突进 mailbox，由 leader worker 仲裁 |
| `governance.ts` + `capabilities.ts` | worker 能做什么不能做什么 | 能力声明 + 权限策略 |
| `scaling.ts` | worker 数量怎么动态调整 | 按负载和队列深度扩缩容 |
| `monitor.ts` + `activity-log.ts` + `audit-log.ts` | 怎么观察整个团队 | 全局监控聚合 + 双层日志（活动 + 审计） |
| `agents/` 目录 | 怎么定义 Agent 角色 | 32 个专业 Agent 的 markdown 模板，每个含 system prompt + 工具列表 |

### 详细说明

- **5 阶段流水线**：plan（拆解需求）→ prd（产品需求确认）→ exec（执行实现）→ verify（验证结果）→ fix（修复问题，可循环）。每个阶段对应一类 worker：plan 阶段用规划者，exec 用执行者，verify 用审查者。这是把"团队协作"形式化成"流水线"的标准做法，比自由组合 Agent 更可控。

- **inbox/outbox 文件总线**：`inbox/` 和 `outbox/` 是两个普通目录，消息以 JSONL 形式追加。worker 启动后轮询自己的 inbox，处理后把结果写到 outbox。优点：①持久化（崩了重启能恢复）；②可观测（直接 cat 文件就能 debug）；③可重放（保留历史消息可以回放执行）。缺点：轮询有延迟、文件锁要小心。

- **tmux 编排 CLI worker**：tmux 解决的核心问题是"CLI 是交互式终端程序，不是为程序集成设计"。用裸 subprocess 接 stdin/stdout 经常踩坑（行缓冲、TTY 检测、输出格式）。tmux 创建一个虚拟终端给 CLI，CLI 以为自己在真实终端跑，OMC 用 `tmux send-keys` 注入命令、`tmux capture-pane` 抓输出。

- **git worktree 并行改代码**：传统多人改代码靠 git branch + merge。OMC 给每个 worker 起一个 worktree（同一个 repo 的多个工作目录），worker 在自己的 worktree 里随便改不冲突。完成后 merge-orchestrator 批量合并所有 worktree 的改动。冲突进 conflict-mailbox 由 leader worker 用 LLM 仲裁。

- **`agents/` 目录的 32 个角色**：每个 Agent 是一个 markdown 文件，含 frontmatter（name、role、tools、model）和 system prompt 正文。32 个角色覆盖架构、研究、设计、测试、数据科学等领域。这是"Prompt as Code"的实践——Agent 角色像代码一样版本管理、复用。

## 4. 关键细节

- **`runtime-v2.ts` 84 KB**：团队运行时主循环。如果只能读一个文件理解 OMC 的核心调度逻辑，读这个。
- **`api-interop.ts` 48 KB**：API 互操作层，定义了 OMC 与 Claude Code 之间的所有接口。这是"插件如何嵌入宿主程序"的参考实现。
- **HUD 状态栏（`hud/`）**：实时显示 worker 状态、token 消耗、运行阶段。这是"实时面板"的实现案例，对应可观测性 UI 的设计。
- **OpenClaw 桥接（`openclaw/`）**：把 Claude Code 内部事件（session-start、stop、pre-tool-use、post-tool-use 等）转发到 Discord/Slack/Telegram，触发外部网关。模板变量（`{{sessionId}}`、`{{projectName}}`、`{{toolName}}`）让事件可定制。
- **智能模型路由**：Haiku（简单任务）/ Sonnet（中等）/ Opus（复杂推理）三级。简单任务自动用便宜模型，节省 30-50% token。这是适配器层的成本优化创新点。
- **持久执行（Ralph 模式）**：标记为 ralph 的任务必须完整完成才退出，中途崩了从 checkpoint 自动恢复。对应"长周期不可中断任务"的解决方案。
- **HUD 路径解析**：用户用 `claude --plugin-dir <path>` 启动时需要导出 `OMC_PLUGIN_ROOT` 环境变量，HUD bundle 才能解析到同一个 checkout。这是插件机制的细节，反映"宿主程序传参 + 环境变量回退"的工程模式。
- **Skill 自学习**：`/skillify` 命令从对话历史中提取可复用的 prompt 模式，存到 `.omc/skills/` 或 `~/.omc/skills/`，下次匹配场景自动注入上下文。这是"prompt 工程的版本化与复用"的实现。
