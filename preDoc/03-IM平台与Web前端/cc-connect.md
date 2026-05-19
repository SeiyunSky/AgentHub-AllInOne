# cc-connect

## 1. 项目基本信息

- **项目名**：cc-connect（chenhg5/cc-connect）
- **GitHub**：https://github.com/chenhg5/cc-connect
- **Star 数 / 主要语言**：9.8k / Go
- **简介**（≤200 字）：

把本地 AI 编码 Agent CLI（Claude Code、Codex、Cursor、Gemini CLI、Aider、Kimi CLI、Pi、OpenCode、iflow、Devin、Qoder 等 11 种）桥接到主流 IM 消息平台（飞书、钉钉、Slack、Discord、Telegram、LINE、企业微信、个人微信、微博、QQ、QQBot、WPS 协作、Max 等 13 种）。用户在手机/电脑上的 IM 应用里和本地 AI Agent 对话，远程触发代码评审、研究、自动化、数据分析等任务。v1.3.0 起内置 Web 管理 UI，支持项目/Provider/Skill/Cron/Hooks 的可视化配置。大多数平台不需要公网 IP。

- **核心创新（一句话）**：用一个 Go 守护进程把"本地多种 Agent CLI"和"远程多种 IM 平台"做双向桥接，让用户在任意聊天工具里像和同事一样使唤本地 AI Agent。

## 2. 项目架构概览

### 技术栈

- **语言**：Go（单二进制分发）
- **分发**：npm 包（`cc-connect`）+ GitHub Release（多平台二进制）
- **配置**：`config.toml`（声明式配置）+ Web Admin UI（可视化编辑）
- **Web UI**：嵌入在二进制里（无外部依赖），支持 5 种语言（en/zh/zh-TW/ja/es）
- **License**：未声明（可能是默认 All Rights Reserved，使用前要确认）

### 目录结构

```
cc-connect/
├── cmd/                            ← CLI 入口（多个子命令）
├── core/                           ← 核心引擎（最大模块）
│   ├── engine.go      (418 KB)     ← 主引擎（最大文件）
│   ├── bridge.go       (41 KB)     ← Bridge 桥接核心（Agent ↔ Platform）
│   ├── api.go          (14 KB)     ← HTTP API
│   ├── cron.go         (25 KB)     ← Cron 定时任务
│   ├── hooks.go        (14 KB)     ← Hook 事件系统
│   ├── heartbeat.go    (10 KB)     ← 心跳保活
│   ├── command.go       (6 KB)     ← 命令路由
│   ├── card.go          (9 KB)     ← IM 卡片消息渲染
│   ├── doctor.go       (13 KB)     ← 健康检查
│   ├── dedup.go        (1 KB)      ← 消息去重
│   ├── atomicwrite.go  (3 KB)      ← 原子写文件
│   ├── dir_history.go  (4 KB)      ← 目录历史记录
│   ├── bridge_capabilities.go      ← 平台能力声明
│   └── ... 大量 *_test.go
│
├── agent/                          ← 11 种 Agent CLI 的适配
│   ├── claudecode/                 ← Claude Code
│   ├── codex/                      ← OpenAI Codex CLI
│   ├── cursor/                     ← Cursor agent
│   ├── gemini/                     ← Gemini CLI
│   ├── kimi/                       ← Kimi CLI
│   ├── opencode/                   ← OpenCode
│   ├── iflow/                      ← iflow
│   ├── devin/                      ← Devin
│   ├── qoder/                      ← Qoder
│   ├── pi/                         ← Pi agent
│   ├── acp/                        ← Agent Communication Protocol（统一协议层）
│   └── tmux/                       ← tmux 适配（用 tmux 启动 CLI）
│
├── platform/                       ← 13 种 IM 平台适配
│   ├── feishu/                     ← 飞书
│   ├── dingtalk/                   ← 钉钉
│   ├── wecom/                      ← 企业微信
│   ├── weixin/                     ← 个人微信（ilink 长轮询）
│   ├── weibo/                      ← 微博 DM
│   ├── qq/                         ← QQ（NapCat/OneBot 桥接）
│   ├── qqbot/                      ← QQ Bot 官方
│   ├── slack/                      ← Slack
│   ├── discord/                    ← Discord
│   ├── telegram/                   ← Telegram
│   ├── line/                       ← LINE
│   ├── max/                        ← Max
│   └── wps-xiezuo/                 ← WPS 协作
│
├── config/                         ← 配置加载
├── daemon/                         ← 守护进程
├── web/                            ← Web Admin UI（嵌入二进制）
├── npm/                            ← npm 包装
├── docs/                           ← 文档
├── tests/
├── changelogs/                     ← 版本变更日志
├── config.example.toml  (89 KB)    ← 配置示例（巨大，反映项目复杂度）
├── provider-presets.json (22 KB)   ← LLM provider 预设
├── skill-presets.json              ← Skill 预设
├── INSTALL.md         (25 KB)      ← 安装文档（详尽）
├── AGENTS.md          (10 KB)      ← Agent 配置说明
└── CHANGELOG.md       (47 KB)      ← 版本日志（项目持续迭代）
```

### 核心机制

**一句话**：Bridge 是中央枢纽——一边监听 N 个 IM 平台的消息（webhook 或长轮询），一边管理 M 个本地 Agent CLI 进程，把 IM 消息映射为 Agent 输入，把 Agent 输出回流给 IM。

cc-connect 启动后跑一个 Go 守护进程：①每个启用的 IM 平台（如飞书）建立连接（webhook 监听 / 长轮询 / WebSocket）；②每个项目（project）配置一个本地 Agent CLI（如 Claude Code），通过 tmux 或子进程启动；③Bridge 模块（`core/bridge.go` 41 KB）作为中央路由器：IM 收到用户消息 → 解析（@、命令、附件）→ 路由到对应项目的 Agent → Agent 处理 → 流式输出回流到 IM 平台 → 渲染成卡片/Markdown/分块消息。`core/engine.go` 418 KB 是引擎主体，包含会话状态机、消息流式处理、跨平台协议转换。每个 IM 平台都有一个独立子模块（`platform/feishu/` 等）实现该平台的协议（Webhook 验证、消息格式、卡片协议、权限模型）。每个 Agent 都有一个独立子模块（`agent/claudecode/` 等）实现该 CLI 的启动方式、stdin/stdout 协议、状态识别。`agent/acp/` 是 Agent Communication Protocol，作为内部统一协议层，让 Bridge 不感知具体 Agent 类型。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Agent + Platform 双侧适配器分离架构**：`agent/` 11 个子目录适配 11 种 Agent CLI，`platform/` 13 个子目录适配 13 种 IM 平台。中间用 ACP（Agent Communication Protocol）统一协议解耦。新增一种 Agent 或一种平台只需要加一个子目录，不影响其他模块。
2. **Bridge 中央路由器（`core/bridge.go`）**：所有 IM 消息和 Agent 输出都经过 Bridge。Bridge 维护"项目 ↔ Agent CLI 进程 ↔ IM 会话"的映射，处理消息路由、流式分块、卡片渲染、去重、权限。这是 IM Agent 桥接系统的核心模式参考。
3. **跨平台能力声明（`bridge_capabilities.go`）**：每个 IM 平台声明自己支持的能力（streaming、images、voice、cards、group）。Bridge 根据能力差异自动降级（如 LINE 不支持 Markdown 卡片就转纯文本，Weibo 不支持图片就跳过）。这是处理"目标平台多样性"的工程方案。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `core/engine.go` | 整体引擎主循环 | 状态机 + 流式消息处理（418 KB 单文件） |
| `core/bridge.go` | Agent ↔ Platform 路由 | 中央 Bridge 维护映射 + 协议转换 |
| `core/bridge_capabilities.go` | 各平台能力差异 | 能力声明文件 + 自动降级 |
| `core/api.go` | HTTP API 暴露 | 提供给 Web UI 和外部集成 |
| `core/cron.go` | 定时任务 | Agent 自动跑任务（如每天定时分析） |
| `core/hooks.go` | 生命周期事件 | message / session / cron / permission / error 五类 hook，shell 命令或 HTTP webhook |
| `core/heartbeat.go` | 长连接保活 | 心跳协议防超时断连 |
| `core/dedup.go` | 消息重复处理 | 去重机制（IM 平台经常重发） |
| `core/card.go` | IM 卡片消息 | 渲染 Markdown / Card / 分块消息到不同平台 |
| `core/doctor.go` | 健康检查 | 自助诊断工具 |
| `core/atomicwrite.go` | 文件原子写 | 防止配置/状态文件中途崩坏 |
| `agent/<name>/` | 适配单个 Agent CLI | 启动方式 + stdin/stdout 协议 + 状态识别 |
| `agent/acp/` | Agent 通信协议 | 内部统一协议，让 Bridge 不感知具体 Agent |
| `agent/tmux/` | tmux 启动 Agent | 用 tmux session 接管 CLI 的 stdin/stdout |
| `platform/<name>/` | 适配单个 IM 平台 | 协议实现 + webhook/长轮询 + 卡片格式 |
| `platform/feishu/` | 飞书集成 | webhook + 卡片 + @ 解析 + 多级回复链 + done-emoji |
| `platform/weixin/` | 个人微信集成 | ilink 长轮询 + QR 配对 + CDN 媒体（无需公网 IP） |
| `platform/weibo/` | 微博 DM | WebSocket + 文本流式 |
| `web/` | 内嵌 Web 管理界面 | Web UI 嵌入二进制（无外部依赖），管理项目/Provider/Skill/Cron/Hooks |
| `provider-presets.json` (22 KB) | Provider 预设库 | LLM provider 配置预设，导入到项目使用 |
| `skill-presets.json` | Skill 预设 | 推荐的本地 Skill 包 |
| `config.example.toml` (89 KB) | 配置参考 | 完整的 toml 配置示例，含全部选项的注释 |

### 详细说明

- **Agent + Platform 双侧适配器架构**：项目最显眼的设计是 `agent/` 和 `platform/` 两个并列目录，各自独立扩展。这种"两侧独立、中央桥接"的架构对应 N×M 集成问题（11 Agent × 13 平台 = 143 种组合）的标准解法——不写 143 个适配器，而是各侧 11 + 13 = 24 个适配器 + 1 个中央 Bridge。

- **ACP（Agent Communication Protocol）抽象层（`agent/acp/`）**：cc-connect 内部定义了统一的 Agent 通信协议，所有具体 Agent 适配器（claudecode/codex/cursor/...）都实现 ACP 接口。Bridge 只和 ACP 对话，不直接感知具体 Agent 实现。这是"接口与实现分离"在 Agent 适配场景的应用。

- **Bridge 中央路由器（41 KB）**：处理所有跨平台、跨 Agent 的消息路由。一条 IM 消息进入 Bridge 后：①识别来源平台和会话；②查 project 配置找到目标 Agent；③解析消息内容（@、命令、附件、回复链）；④发送到 Agent 的 ACP 通道；⑤接收 Agent 流式输出；⑥根据目标平台能力（capabilities）决定渲染方式（卡片/Markdown/纯文本/语音）；⑦分块发送回 IM。这是 IM-Agent 桥接系统的核心模式范本。

- **跨平台能力声明（`bridge_capabilities.go`）**：每个平台声明自己的能力矩阵——"支持流式""支持图片""支持卡片""支持语音"。Bridge 在转发消息前查目标平台的 capabilities，按能力做格式降级。例如 LINE 不支持 Markdown 卡片，Bridge 自动转换为纯文本；Weibo 不支持图片，跳过图片输出但保留文本。这避免了"在每个平台模块里写降级代码"的重复。

- **Hook 事件系统（`core/hooks.go`）**：v1.3.0 引入的扩展点。可以在 message / session / cron / permission / error 五类事件触发 shell 命令或 HTTP webhook。异步执行、fail-open（hook 失败不影响主流程）。这给用户暴露了"在 Agent 工作流的关键节点插入自定义逻辑"的能力。

- **Cron 定时任务（`core/cron.go` 25 KB）**：用户可以配置 cron 表达式让 Agent 定期执行（如每天 9 点跑数据分析）。结果通过 IM 通知用户。这把 AI Agent 从"被动响应"扩展到"主动执行"。

- **Web Admin UI 嵌入二进制**：v1.3.0 起 Web 管理界面直接编译进 Go 二进制。用户运行 `cc-connect web` 启动管理面板（默认浏览器打开），可以创建/编辑项目、管理 Provider、监控会话、编辑 cron、甚至直接在浏览器里和 Agent 聊天。这种"单二进制 + 嵌入 Web UI"分发对降低使用门槛很关键。

- **个人微信集成（`platform/weixin/`）**：通过 ilink 长轮询 + QR 配对实现，不需要公网 IP。媒体走 CDN。这是国内场景最关键的能力之一——大部分用户实际用微信沟通。

- **飞书深度集成（`platform/feishu/`）**：自动解析 `@name` 提及、识别多级回复链、支持 done-emoji 反应。这种"贴近平台原生体验"的细节让用户感受不到桥接的存在。

- **Skill 管理（`/skills` 页面 + `skill-presets.json`）**：本地技能浏览器 + 推荐预设。这把 Claude Code 的 skill 概念扩展到平台层面——所有桥接的 Agent 都可以共享 skill 包。

- **`config.example.toml` 89 KB**：完整的配置示例文件，含每个选项的注释和示例值。这种"可读的配置文档"是工程化的体现——让用户能不查文档就配置项目。

- **Provider 预设库 + 从 cc-switch 导入**：22 KB 的 `provider-presets.json` 提供大量预配置的 LLM provider，用户在 Web UI 一键启用。还能从 `cc-switch`（另一个相关工具）的配置导入。这种"零配置默认 + 一键迁移"对用户体验是关键。

## 4. 关键细节

- **`core/engine.go` 418 KB 单文件**：整个项目的大脑。这种巨型文件反映项目早期快速迭代的现实，工程上不优雅但功能集中。如果要深读核心逻辑，直接读这个文件。
- **`core/engine_test.go` 410 KB**：测试文件几乎和源文件一样大，说明测试覆盖率很高。这是开源项目工程素养的体现。
- **CHANGELOG 47 KB + `changelogs/` 目录**：项目维护详尽的版本日志，并有专门的 changelogs 目录存历史。说明项目持续迭代且文档化好。
- **多个测试文件覆盖每个核心模块**：`api_test.go`、`bridge_test.go`、`bridge_capabilities_test.go`、`bridge_capabilities_snapshot_test.go`、`atomicwrite_test.go`、`card_test.go`、`command_test.go`、`cron_test.go`、`dedup_test.go`、`heartbeat_test.go`、`hooks_test.go`。每个核心机制都有对应测试。
- **bridge_capabilities_snapshot_test**：snapshot 测试模式，用快照文件验证 capabilities 演化。这是测试"配置型代码"的好做法。
- **`embed.go`**：用 Go 的 `embed` 指令把 Web UI 静态资源、配置示例等打包进二进制。单二进制分发的标准做法。
- **`Makefile` 6 KB**：完整的构建、测试、发布流程自动化。
- **`.golangci.yml`**：Go lint 配置，反映工程纪律。
- **赞助商列表（README 顶部巨大）**：项目接受了 16+ 个 LLM API relay 服务的赞助。这反映项目的商业相关性——它已经成为 LLM relay 服务的"流量入口"。
- **Discord + Telegram 群组**：项目自带活跃社区。
- **Trendshift Badge**：被 Trendshift 收录，说明在 GitHub trending 圈有声量。
- **License 未声明（仓库 root.json 显示 license 为 None）**：使用前必须确认作者意图。可能是疏漏或刻意为之。任何商用衍生都要先咨询作者。
- **支持版本管理 + 依赖嵌入**：项目用 Go 版本号管理 + Web UI embed，单二进制分发，跨平台（Windows/Linux/macOS）。
- **配置驱动 vs 代码驱动**：cc-connect 是典型的配置驱动项目——89 KB toml + 22 KB JSON + 13 KB+ 各种预设。用户大部分时间在配置 UI 里点选，不需要写代码。这是"工具型"项目的标准定位。
- **国内 IM 覆盖最全**：飞书、钉钉、企业微信、个人微信、微博、QQ、QQBot、WPS——国内主流 IM 几乎全覆盖。这是本项目相对其他 IM 桥接（如 lobehub 等）的差异化优势。
