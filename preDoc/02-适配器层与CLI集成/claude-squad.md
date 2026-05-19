# claude-squad

## 1. 项目基本信息

- **项目名**：Claude Squad（smtg-ai/claude-squad）
- **GitHub**：https://github.com/smtg-ai/claude-squad
- **Star 数 / 主要语言**：7.5k / Go
- **简介**（≤200 字）：

终端 TUI 应用，在同一个终端窗口里管理多个 AI Agent CLI 实例（Claude Code、Codex、Gemini CLI、Aider 等），每个 Agent 跑在独立的 tmux session + 独立的 git worktree。支持 yolo / auto-accept 后台模式、跨会话切换、change diff 预览、commit/push 流程。配置基于 profiles（每个 profile 是一个启动命令），用户在创建 session 时选择 profile 启动对应 Agent。整体只有一个 Go 二进制 `cs`，依赖 tmux 和 gh CLI。

- **核心创新（一句话）**：用 tmux session + git worktree 把多个 Agent CLI 实例隔离到独立工作区，并通过一个统一 TUI 同时管理它们的生命周期与代码改动。

## 2. 项目架构概览

### 技术栈

- **语言**：Go
- **TUI 框架**：Bubble Tea / Lip Gloss（Go 生态主流）
- **运行时依赖**：tmux（终端会话管理）、gh CLI（git push 流程）、git worktree（代码隔离）
- **持久化**：本地 `~/.claude-squad/config.json` + 状态文件
- **License**：AGPL-3.0

### 目录结构

```
claude-squad/
├── main.go                        ← 入口
├── cmd/                           ← CLI 子命令（completion / debug / reset / version）
├── app/                           ← TUI 主应用
│   ├── app.go         (31 KB)     ← TUI 主循环、视图、键盘事件
│   ├── help.go         (6 KB)     ← 帮助菜单
│   └── app_test.go    (14 KB)     ← TUI 测试
├── session/                       ← 会话管理（核心）
│   ├── instance.go    (19 KB)     ← Instance 实体（一个 Agent 实例 = tmux + worktree）
│   ├── storage.go      (4 KB)     ← Instance 状态持久化
│   ├── git/                       ← git worktree 操作封装
│   └── tmux/                      ← tmux session 操作封装
├── daemon/                        ← 后台守护进程
│   ├── daemon.go       (4 KB)     ← daemon 主体
│   ├── daemon_unix.go             ← Unix 平台特化（信号/fork）
│   └── daemon_windows.go          ← Windows 平台特化
├── config/                        ← 配置加载
├── ui/                            ← TUI 组件（侧边栏、diff 视图、菜单）
├── web/                           ← 可选 Web UI（推测）
├── keys/                          ← 键位映射
├── log/                           ← 日志
├── assets/                        ← 截图、文档资源
└── install.sh                     ← 一键安装脚本
```

### 核心机制

**一句话**：每个 Agent 实例 = 一个 tmux session（隔离 stdin/stdout）+ 一个 git worktree（隔离代码改动），TUI 主循环在它们之间切换。

用户在 TUI 里按 `n` 创建新 session：从 profile 列表选一个（如 `claude` / `codex` / `aider`），claude-squad 创建一个新的 git worktree（一个隔离的工作目录），在新的 tmux session 里执行 profile 对应的命令（如 `claude`），把 tmux pane 当作这个 Agent 的"窗口"。`session/instance.go` 维护 Instance 实体：tmux session id + worktree path + Agent 状态。TUI 通过 `tmux capture-pane` 抓 pane 内容渲染到主界面。daemon 后台支持长任务：用户按 `c` 保存进度（commit + 暂停），按 `r` 恢复（reattach tmux）。所有 Instance 的状态持久化到 `~/.claude-squad/`，重启程序能恢复全部 session。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Instance 抽象（`session/instance.go`）**：Instance = tmux session + git worktree + Agent 程序的三元组。这是把"一个 AI Agent CLI"工程化封装的最小单元。
2. **profile 机制配置不同 Agent**：用户在 `config.json` 声明多个 profile（每个 profile 是一个启动命令），创建 session 时选择 profile。这是"统一适配多种 Agent CLI"的极简实现——不写适配器代码，直接用启动命令封装差异。
3. **git worktree 隔离工作空间**：每个 Instance 一个独立 worktree，多 Agent 并行改代码不冲突，commit/push 流程不互相影响。这是把"多 Agent 改同一个 repo"工程化的标准方案。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `session/instance.go` | 怎么抽象一个 Agent 实例 | tmux session + worktree + 启动命令的三元组 |
| `session/git/` | 多 Agent 改代码怎么不冲突 | git worktree，每个 Instance 一个独立工作目录 |
| `session/tmux/` | 怎么和交互式 CLI 通信 | tmux session + capture-pane / send-keys |
| `session/storage.go` | Instance 状态怎么持久化 | 本地状态文件，重启可恢复 |
| `daemon/daemon.go` | 长任务怎么后台跑 | 守护进程持续维护 tmux session |
| `daemon/daemon_unix.go` + `daemon/daemon_windows.go` | 跨平台 daemon 怎么写 | 平台分文件，公用接口 |
| `config/` + profiles | 怎么支持多种 Agent CLI | profile 列表，每个 profile = 一条启动命令 |
| `app/app.go` | TUI 主循环怎么写 | Bubble Tea 状态机 + 键盘事件路由 |
| `ui/` | 如何同时显示多 session | 侧边栏列表 + 主区 tmux pane 实时渲染 + diff 视图 |
| `keys/` | 键位怎么模块化 | 键位映射独立模块 |
| `cmd/` | CLI 子命令怎么组织 | 子命令独立文件，按职责拆分 |

### 详细说明

- **Instance 抽象**：`session/instance.go` 19 KB 是项目最核心的文件。Instance 包含 `tmux_session_id`、`worktree_path`、`program`、`status`、`paused_at` 等字段。所有操作（创建、暂停、恢复、销毁）都围绕 Instance 展开。这种"实体即数据"的设计让 Instance 的状态完全可序列化，重启程序能从 `storage.go` 恢复全部 Instance。

- **profile 机制**：`config.json` 里 `profiles` 数组每项有 `name` 和 `program` 两个字段，`program` 是启动 Agent 的 shell 命令。这种设计极简——不写适配器代码，差异完全通过命令行参数表达（如 `aider --model ollama_chat/gemma3:1b`）。新增 Agent CLI 支持只需要加一行 profile，不改代码。

- **git worktree 隔离**：传统多人改代码靠 branch + checkout，同一时刻只能在一个分支上工作。git worktree 允许同一个 repo 在多个目录下 checkout 不同分支，互不干扰。Claude Squad 给每个 Instance 创建一个 worktree，Agent 在自己的目录里随便改不影响其他 Agent。

- **tmux session 双用途**：①隔离 stdin/stdout（Agent CLI 不知道自己被外部接管）；②持久化（用户关掉 TUI 不影响 tmux 内的 Agent，重新打开能 attach 回来）。tmux 在这里既是通信通道也是保活机制。

- **daemon 跨平台分文件**：Unix 和 Windows 的 daemon 实现完全不同（Unix 用 fork、Windows 用服务）。项目用 `daemon_unix.go` + `daemon_windows.go` 双文件 + `//go:build` tag 的方式分离，公共接口在 `daemon.go`。这是 Go 跨平台代码的标准模式。

- **TUI 主循环**：`app/app.go` 31 KB 包含整个 TUI 的状态机。Bubble Tea 的模式是 Model-Update-View（类似 Elm）：所有状态在 Model 里，键盘事件触发 Update，Update 返回新 Model + 命令。31 KB 单文件说明 TUI 状态机不需要复杂分层。

- **commit/checkout/push 工作流（`s` / `c` / `r` 键）**：用户随时可以让 Agent 暂停（`c` = commit + pause），稍后恢复（`r` = resume）。这是"长任务可中断 + 可恢复"的工程实现，依赖 git worktree 的 commit 状态作为 checkpoint。

## 4. 关键细节

- **整个项目代码量小**：核心目录（app/session/daemon/cmd）加起来不到一万行 Go，`go.mod` 主要依赖是 Bubble Tea 系列。这是"轻量级"项目的范例。
- **`AGENTS.md` 11 KB**：项目自带的 Agent 配置说明文档，描述支持的 Agent 类型、启动命令、特殊参数。是参考"如何文档化多 Agent CLI 适配"的好例子。
- **`install.sh` 11 KB**：一键安装脚本，处理 OS 检测、二进制下载、PATH 设置、依赖检查（tmux、gh）。展示了"用户友好的 CLI 工具安装"应该怎么写。
- **`web/` 目录存在**：root 列表显示有 `web/`，说明项目除 TUI 外还在做 Web UI（推测）。
- **`-y / --autoyes` 标志（实验性）**：所有 Instance 自动接受 Claude Code/Aider 的确认提示，实现 yolo 模式（无人值守跑任务）。这对"长任务后台执行"是关键能力。
- **`reset` 子命令**：`cs reset` 重置所有存储的 Instance，是"工作流出错时的逃生通道"，工程上不可缺。
- **`bump-version.sh` + `clean.sh` + `clean_hard.sh`**：项目自带版本号升级和清理脚本，反映"工程化纪律"。
- **`.goreleaser.yaml`**：用 GoReleaser 自动化发布流程，CI 触发后自动构建跨平台二进制 + 发布 GitHub Release。这是 Go 项目的标准发布工程。
- **AGPL-3.0 协议**：相对严格的 copyleft 协议。如果直接派生使用要注意——不只是看代码学习，还要考虑商用合规。
- **不区分主子 Agent**：项目里所有 Instance 平级，没有 Orchestrator 概念。用户自己在多个 Agent 之间切换、自己分派任务。这是"工具型"而非"编排型"的定位选择。
