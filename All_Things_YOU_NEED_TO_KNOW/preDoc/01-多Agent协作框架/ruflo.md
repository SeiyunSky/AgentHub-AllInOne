# ruflo (前身 claude-flow)

## 1. 项目基本信息

- **项目名**：Ruflo（ruvnet/ruflo，前身 ruvnet/claude-flow）
- **GitHub**：https://github.com/ruvnet/ruflo
- **Star 数 / 主要语言**：53.0k / TypeScript（含 Rust 模块）
- **简介**（≤200 字）：

为 Claude Code 增加多 Agent 编排能力的扩展系统。提供 100+ 专业 Agent、32 个独立插件、MCP server 接入、联邦通信（agents 跨机器跨组织安全协作）、自学习记忆（rvf）、向量数据库（agentdb / ruvector）、知识图谱、Graph RAG、IoT 设备管理、神经交易等领域子系统。安装方式两种：插件式（slash 命令 + agent 定义）或 CLI 完整安装（98 agents + 60+ commands + 30 skills + MCP server + hooks + daemon）。底层 Cognitum.One agentic 架构，Rust AI 引擎做 embedding/memory/plugin。

- **核心创新（一句话）**：在 Claude Code 之上叠加"自学习 swarm + 联邦通信 + 向量记忆"，让 100+ 个 Agent 在跨机器、跨信任域的环境下协作。

## 2. 项目架构概览

### 技术栈

- **主语言**：TypeScript + Rust（混合，Rust 提供 AI 引擎核心）
- **运行时**：Node.js（npm 包）+ Rust crates（性能关键路径）
- **包管理**：npm / pnpm（双 lock 文件，pnpm-workspace.yaml）
- **Claude Code 集成**：通过 plugin marketplace + MCP server 双通道
- **MCP 协议**：原生支持，提供 314 个 MCP 工具
- **关键产物**：`ruflo` npm 包、`@claude-flow/codex` npm 包、`ruvector`、`neural-trader` 独立包

### 目录结构

```
ruflo/
├── ruflo/                           ← 主入口（v1）
│   ├── src/                         ← 主源码
│   ├── docs/                        ← 文档
│   ├── docker-compose.yml           ← 容器化部署
│   ├── rvf.manifest.json            ← rvf 持久化清单
│   └── package.json
│
├── v3/                              ← 第三代实现（活跃开发版）
│   ├── src/                         ← v3 源码
│   ├── crates/                      ← Rust crates（核心引擎）
│   ├── @claude-flow/                ← claude-flow 命名空间下的子模块
│   ├── .agentic-flow/               ← agentic-flow 子系统
│   ├── agents/                      ← Agent 定义
│   ├── plugins/                     ← 插件实现
│   ├── mcp/                         ← MCP server 实现
│   ├── docs/                        ← 文档
│   ├── goal_ui/                     ← Goal Planner UI
│   ├── helpers/                     ← 辅助工具
│   ├── implementation/              ← 实现细节
│   ├── scripts/                     ← 工具脚本
│   ├── swarm.config.ts              ← swarm 配置
│   └── index.ts                     ← v3 入口
│
├── plugin/                          ← Claude Code 插件骨架
│   ├── .claude-plugin/              ← 插件元数据
│   ├── hooks/                       ← Hook 实现
│   └── scripts/                     ← 安装脚本
│
├── plugins/                         ← 32 个独立插件
│   ├── ruflo-core/                  ← 基础（server、health、plugin discovery）
│   ├── ruflo-swarm/                 ← swarm 多 Agent 协调
│   ├── ruflo-autopilot/             ← Agent 自主循环
│   ├── ruflo-loop-workers/          ← 定时后台任务
│   ├── ruflo-workflows/             ← 多步任务模板
│   ├── ruflo-federation/            ← 跨机器联邦通信
│   ├── ruflo-agentdb/               ← 向量数据库（Agent 记忆）
│   ├── ruflo-rag-memory/            ← Hybrid 检索 + 图遍历 + 多样性排序
│   ├── ruflo-rvf/                   ← Agent 记忆持久化（保存/恢复 session）
│   ├── ruflo-ruvector/              ← GPU 加速搜索 + Graph RAG（103 tools）
│   ├── ruflo-knowledge-graph/       ← 实体关系图谱
│   ├── ruflo-intelligence/          ← 从过去成功案例学习
│   ├── ruflo-daa/                   ← Dynamic Agent Architecture（动态行为）
│   ├── ruflo-ruvllm/                ← 本地 LLM 路由（Ollama 等）
│   ├── ruflo-goals/                 ← 目标拆解 + 进度追踪
│   ├── ruflo-testgen/               ← 自动测试生成
│   ├── ruflo-browser/               ← Playwright 浏览器自动化
│   ├── ruflo-jujutsu/               ← git diff 分析 + 风险评分
│   ├── ruflo-docs/                  ← 文档自动维护
│   ├── ruflo-security-audit/        ← CVE 扫描
│   ├── ruflo-aidefence/             ← prompt 注入防御 / PII 检测
│   ├── ruflo-adr/                   ← 架构决策记录
│   ├── ruflo-ddd/                   ← DDD 脚手架
│   ├── ruflo-sparc/                 ← SPARC 5 阶段开发方法论
│   ├── ruflo-migrations/            ← 数据库 schema 变更管理
│   ├── ruflo-observability/         ← 日志 / trace / metrics
│   ├── ruflo-cost-tracker/          ← Token 预算与告警
│   ├── ruflo-agent/                 ← rvagent 本地 WASM sandbox + Anthropic 托管 Agent
│   ├── ruflo-plugin-creator/        ← 插件脚手架
│   ├── ruflo-iot-cognitum/          ← IoT 设备管理（信任评分 / 异常检测）
│   ├── ruflo-neural-trader/         ← AI 交易（4 个 agent + 回测，112+ tools）
│   └── ruflo-market-data/           ← 行情数据 + OHLCV 向量化
│
├── bin/                             ← 可执行入口
├── docs/                            ← 项目级文档
├── scripts/                         ← 顶层脚本（含 install.sh）
├── tests/
└── verification/                    ← 验证套件
```

### 核心机制

**一句话**：用户输入 → Ruflo CLI/MCP → Router 路由到对应 Swarm → Swarm 内部 Agent 调度 → Memory 系统记忆 → LLM Provider 出结果，过程通过 Learning Loop 反向优化 Router 和 Swarm。

```
User → Ruflo (CLI/MCP) → Router → Swarm → Agents → Memory → LLM Providers
                          ^                           |
                          +---- Learning Loop <-------+
```

Ruflo 不替代 Claude Code，而是给 Claude Code 装一个"神经系统"：用户继续在 Claude Code 里写代码，Ruflo 通过 hooks 系统自动接管任务路由、自动协调 swarm 中的 Agent、自动从成功模式学习、自动跨 session 保留记忆。Federation 模块让 swarm 跨机器、跨组织安全协作（zero-trust 模型）。MCP server 暴露 314 个工具供 Claude 调用。两种安装方式：Path A（插件式）只装 slash 命令，Path B（CLI install）会写入 `.claude/`、`.claude-flow/`、`CLAUDE.md`、helpers、settings，启用完整 daemon。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **插件化的能力切片（32 个独立插件）**：每个能力（swarm、autopilot、federation、知识图谱等）是独立插件，可单独安装。这种设计让"多 Agent 平台"具备弹性——用户按需启用，避免全量加载。
2. **Learning Loop 自学习架构**：Router → Swarm → Agents → Memory 的执行结果反向喂给 Router，让路由策略和 Agent 选择持续优化。这是把"过去成功模式"变成"未来路由策略"的实现。
3. **Federation 跨信任域协作**：不同机器、不同组织的 Agent 通过 zero-trust 协议发现彼此、认证、交换任务，且不泄露数据。这是把多 Agent 从"同一进程"扩展到"跨网络"的协作层。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `ruflo-core` | 基础设施 | server + health checks + plugin discovery |
| `ruflo-swarm` | 多 Agent 协调 | swarm 模型，Agent 协同执行 |
| `ruflo-autopilot` | Agent 自主循环 | 自主跑直到任务完成 |
| `ruflo-loop-workers` | 定时后台任务 | 调度器驱动的 worker |
| `ruflo-workflows` | 多步任务复用 | 模板化的任务流水线 |
| `ruflo-federation` | 跨机器协作 | zero-trust 发现 + 认证 + 安全交换 |
| `ruflo-agentdb` | Agent 记忆存储 | 向量数据库，快速检索语义记忆 |
| `ruflo-rag-memory` | 智能记忆检索 | hybrid search + graph hops + 多样性排序 |
| `ruflo-rvf` | 跨 session 记忆持久化 | 保存/恢复 Agent 状态到磁盘 |
| `ruflo-ruvector` | 大规模语义搜索 | GPU 加速 + Graph RAG，103 个工具 |
| `ruflo-knowledge-graph` | 实体关系建模 | 知识图谱构建与遍历 |
| `ruflo-intelligence` | Agent 经验学习 | 提取过去成功模式，下次自动应用 |
| `ruflo-daa` | 动态 Agent 行为 | Dynamic Agent Architecture，运行时调整认知模式 |
| `ruflo-ruvllm` | 本地 LLM 路由 | 智能路由（Ollama 本地 / 云端 API） |
| `ruflo-goals` | 目标拆解 | 大目标 → 计划 → 任务追踪 |
| `ruflo-aidefence` | 安全防御 | prompt 注入检测 / PII 识别 / 安全扫描 |
| `ruflo-sparc` | 开发方法论 | 5 阶段开发 + 质量门禁 |
| `ruflo-observability` | 可观测性 | 结构化日志 + trace + metrics 三位一体 |
| `ruflo-cost-tracker` | 成本控制 | Token 用量追踪 + 预算告警 |
| `ruflo-agent` | Agent 执行环境 | 本地 WASM sandbox（rvagent）+ Anthropic 托管 Agent |
| `ruflo-plugin-creator` | 插件开发支持 | 脚手架 + 校验 + 发布工具链 |

### 详细说明

- **插件化能力切片**：32 个插件每个聚焦单一能力。`ruflo-core` 提供基础（server、health、discovery），其他插件基于 core 扩展。这种设计的好处：①新能力作为新插件加，不影响现有；②用户按需启用，控制资源；③插件之间解耦，独立演进。`ruflo-plugin-creator` 还提供官方的插件脚手架。

- **Learning Loop 自学习**：执行链路是 `User → Ruflo → Router → Swarm → Agents → Memory → LLM`。Memory 收集每次执行的输入、决策、结果。`ruflo-intelligence` 从 Memory 中提取"成功模式"（哪种 Router 策略、哪些 Agent 组合、哪些 prompt 在什么场景下成功）。下次类似场景，Router 自动倾向用过去成功的策略。这是"经验驱动"的 Agent 系统，区别于"规则驱动"。

- **Federation（跨信任域协作）**：传统多 Agent 都在同一台机器同一进程。Federation 允许不同机器（不同组织）的 swarm 互相发现、认证、交换任务，且通过 zero-trust 协议保证数据不泄露。具体场景：A 公司的 Coder Agent 调用 B 公司的 Reviewer Agent，B 看不到 A 的代码内容，但能给出审查反馈。

- **rvf（记忆持久化）**：`ruflo-rvf` 把 Agent 的工作记忆（向量、对话、决策）序列化到磁盘，下次启动恢复。支持 manifest 格式（`rvf.manifest.json`），声明哪些状态需要持久化。结合 `ruflo-agentdb`（向量数据库）和 `ruflo-rag-memory`（智能检索），形成完整的"记忆 + 检索"闭环。

- **MCP 双通道**：插件提供 slash 命令（用户视角），MCP server 提供 314 个程序化工具（Agent 视角）。同一能力两种暴露方式：用户用命令，Agent 用 MCP 调用。这种设计让 Ruflo 既是用户工具也是 Agent 基础设施。

- **Path A vs Path B 安装策略**：Path A（plugin marketplace）只装 slash 命令和 agent 定义，零工作区污染，适合"试一下"。Path B（`npx ruflo init`）写入 `.claude/`、`.claude-flow/`、`CLAUDE.md`、settings，启用完整 daemon + MCP server，适合生产。这种"轻量试用 vs 完整安装"的双路径设计降低了用户决策成本。

- **SPARC 方法论（`ruflo-sparc`）**：5 阶段开发方法论 + 质量门禁。每个阶段有明确的入口/出口标准，Agent 协作必须按阶段推进。这是"流水线 + 门禁"模式的实现。

- **`ruflo-jujutsu`**：基于 git diff 分析代码风险评分、自动建议 reviewer。这是把代码审查工程化的尝试，对应"代码 Diff"功能场景。

## 4. 关键细节

- **v1（`ruflo/`）和 v3（`v3/`）并存**：v1 是稳定版，v3 是活跃开发。v3 有完全独立的 `src/`、`crates/`（Rust）、`agents/`、`plugins/`、`mcp/`，说明在做大重构。如果要看最新设计，看 v3。
- **Rust 引擎（`v3/crates/`）**：Cognitum.One 的核心 AI 引擎用 Rust 实现，包括 embedding、memory、plugin system。性能关键路径不用 TypeScript，反映"语言适合任务"的工程取舍。
- **314 个 MCP 工具**：通过 MCP server 暴露给 Claude 的工具数量。这是题目"基于统一适配器层"的极端实现案例——把所有 Ruflo 能力都做成 MCP 工具，让任意 MCP 客户端（不只 Claude Code）都能用。
- **100+ Agent 角色**：`ruflo-agent` 插件管理 Agent 生命周期，支持本地 WASM sandbox（`rvagent`）和 Anthropic 托管 Agent。两种执行环境用同一个 Agent 抽象。
- **联邦通信的协议设计**：Federation 不是简单 RPC，要解决信任、发现、认证、数据隔离四个问题。zero-trust 模型意味着每次交互都验证身份和权限，不假设"内网安全"。这是企业级多 Agent 系统的标准做法。
- **`swarm.config.ts`（v3）**：声明式 swarm 配置文件。用户可以定义"团队组成"、"Agent 角色"、"协作策略"，Ruflo 启动时按配置实例化 swarm。这是"基础设施即代码"思想在 Agent 系统的应用。
- **`docker-compose.yml`（v1）**：项目提供官方 docker-compose 部署配置，包含完整的服务栈（server、daemon、MCP、UI）。一键 `docker-compose up` 拉起完整环境。
- **`ruflo-plugin-creator`**：官方插件脚手架。开发新插件时用它生成骨架（manifest、hooks、commands、agents 定义），降低插件开发门槛。这是平台生态的关键基础设施——让第三方能贡献插件。
- **三个 UI 入口**：`flo.ruv.io`（主 UI Beta）、`goal.ruv.io`（Goal Planner）、`goal.ruv.io/agents`（Live Agents 面板）。说明项目不只有 CLI，也有完整 Web UI——这部分代码主要在 `v3/goal_ui/`。
- **多 npm 包发布**：除主包 `ruflo` 外，还有 `claude-flow`（旧名）、`@claude-flow/codex`（Codex 插件）、`ruvector`（向量库）、`neural-trader`（交易系统）。说明子系统独立可用，不绑定主包。
