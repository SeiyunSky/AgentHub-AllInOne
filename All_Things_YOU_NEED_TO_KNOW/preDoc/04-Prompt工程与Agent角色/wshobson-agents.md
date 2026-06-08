# wshobson/agents

## 1. 项目基本信息

- **项目名**：Claude Code Plugins: Orchestration and Automation（wshobson/agents）
- **GitHub**：https://github.com/wshobson/agents
- **Star 数 / 主要语言**：35.6k / Python（实际内容主要是 Markdown）
- **简介**（≤200 字）：

Claude Code 的插件市场，提供 80 个聚焦单一职责的插件，包含 185 个专业 Agent、153 个 Agent Skill、16 个多 Agent 工作流编排器、100 个命令。每个插件按领域划分（架构、Python、JS/TS、K8s、安全、数据、文档、SEO、量化交易等），用户按需安装单个插件，只加载该插件的 Agent 与 Skill 到上下文，最小化 token 占用。同时支持 Gemini CLI 作为 native extension。本质是"Agent 角色与领域知识的 Marketplace"，不是运行时框架。强调三层模型策略（Haiku/Sonnet/Opus）、progressive disclosure、模块组合。

- **核心创新（一句话）**：把 Agent 角色和领域技能作为可独立安装的细粒度插件，让用户只装当前任务需要的 Agent，避免 Claude Code 上下文被无关角色撑爆。

## 2. 项目架构概览

### 技术栈

- **核心格式**：Markdown（Agent 定义、Skill、命令均为 markdown 文件）
- **元数据**：`.claude-plugin/` 目录 + `plugin.json`（推测）
- **宿主**：Claude Code（plugin marketplace）+ Gemini CLI（extension）
- **构建工具**：Makefile（用于 Gemini 扩展生成）
- **本质**：声明式资源库，无运行时代码

### 目录结构

```
wshobson/agents/
├── plugins/                        ← 80 个独立插件
│   ├── agent-orchestration/        ← 多 Agent 编排
│   │   ├── .claude-plugin/         ← 插件元数据
│   │   ├── agents/                 ← Agent 角色定义（markdown）
│   │   └── commands/               ← 命令定义
│   ├── agent-teams/                ← 团队协作
│   ├── full-stack-orchestration/   ← 全栈多 Agent 工作流
│   ├── conductor/                  ← 协调器
│   │
│   ├── python-development/         ← Python 领域（python-pro / django-pro / fastapi-pro）
│   ├── javascript-typescript/      ← JS/TS 领域
│   ├── jvm-languages/              ← Java/Kotlin/Scala
│   ├── julia-development/          ← Julia
│   ├── dotnet-contribution/        ← .NET
│   ├── functional-programming/     ← 函数式
│   ├── systems-programming/        ← 系统编程
│   │
│   ├── backend-development/        ← 后端
│   ├── api-scaffolding/            ← API 脚手架
│   ├── frontend-mobile-development/ ← 前端 / 移动
│   │
│   ├── kubernetes-operations/      ← K8s
│   ├── cloud-infrastructure/       ← AWS / Azure / GCP
│   ├── deployment-strategies/      ← 部署策略
│   ├── cicd-automation/            ← CI/CD
│   │
│   ├── database-design/            ← 数据库设计
│   ├── database-migrations/        ← 迁移
│   ├── database-cloud-optimization/ ← 云上数据库优化
│   ├── data-engineering/           ← 数据工程
│   ├── machine-learning-ops/       ← MLOps
│   │
│   ├── comprehensive-review/       ← 多视角代码审查
│   ├── code-refactoring/           ← 重构
│   ├── code-documentation/         ← 代码文档
│   ├── codebase-cleanup/           ← 代码库清理
│   ├── unit-testing/               ← 单测
│   ├── tdd-workflows/              ← TDD
│   ├── debugging-toolkit/          ← 调试
│   ├── error-debugging/ + error-diagnostics/  ← 错误诊断
│   ├── distributed-debugging/      ← 分布式调试
│   │
│   ├── security-scanning/          ← SAST
│   ├── security-compliance/        ← 合规
│   ├── backend-api-security/       ← API 安全
│   ├── frontend-mobile-security/   ← 前端 / 移动安全
│   ├── reverse-engineering/        ← 逆向
│   │
│   ├── observability-monitoring/   ← 监控
│   ├── api-testing-observability/  ← API 测试 + 可观测
│   ├── application-performance/    ← 应用性能
│   ├── performance-testing-review/ ← 性能测试
│   │
│   ├── llm-application-dev/        ← LLM 应用开发
│   ├── plugin-eval/                ← 插件评估框架
│   ├── protect-mcp/                ← MCP 保护
│   ├── review-agent-governance/    ← Agent 治理审查
│   ├── signed-audit-trails/        ← 签名审计
│   │
│   ├── git-pr-workflows/           ← Git/PR 流程
│   ├── dependency-management/      ← 依赖管理
│   ├── framework-migration/        ← 框架迁移
│   ├── data-validation-suite/      ← 数据校验
│   │
│   ├── content-marketing/          ← 内容营销
│   ├── seo-analysis-monitoring/    ← SEO 分析
│   ├── seo-content-creation/       ← SEO 内容
│   ├── seo-technical-optimization/ ← SEO 技术
│   ├── brand-landingpage/          ← 落地页
│   ├── ui-design/                  ← UI 设计
│   ├── meigen-ai-design/           ← AI 设计
│   ├── customer-sales-automation/  ← 销售自动化
│   ├── business-analytics/         ← 商业分析
│   ├── startup-business-analyst/   ← 创业商业分析
│   ├── hr-legal-compliance/        ← HR / 法律合规
│   │
│   ├── arm-cortex-microcontrollers/ ← ARM Cortex MCU
│   ├── blockchain-web3/            ← 区块链
│   ├── game-development/           ← 游戏
│   ├── multi-platform-apps/        ← 多平台 App
│   ├── payment-processing/         ← 支付
│   ├── quantitative-trading/       ← 量化交易
│   ├── shell-scripting/            ← Shell
│   ├── web-scripting/              ← Web 脚本
│   ├── accessibility-compliance/   ← 无障碍合规
│   ├── c4-architecture/            ← C4 架构图
│   ├── context-management/         ← 上下文管理
│   ├── deployment-validation/      ← 部署验证
│   ├── developer-essentials/       ← 开发者基础
│   ├── documentation-generation/   ← 文档生成
│   ├── documentation-standards/    ← 文档规范
│   ├── ship-mate/                  ← 发布助手
│   ├── team-collaboration/         ← 团队协作
│   ├── incident-response/          ← 事故响应
│   └── block-no-verify/            ← 阻止 --no-verify
│
├── tools/                          ← 工具脚本
├── docs/
│   ├── plugins.md                  ← 80 插件目录
│   ├── agents.md                   ← 185 Agent 目录
│   ├── agent-skills.md             ← 153 Skill 目录
│   ├── usage.md                    ← 使用指南
│   ├── architecture.md             ← 架构文档
│   └── plugin-eval.md              ← PluginEval 评估框架
│
├── README.md / GEMINI.md / CLAUDE.md
├── Makefile                        ← Gemini 扩展生成命令
└── gemini-extension.json
```

### 核心机制

**一句话**：每个插件是一个 markdown 文件包，独立宣告自己提供的 Agent / Skill / Command；用户在 Claude Code 里 `/plugin install <name>`，宿主只加载该插件的资源到上下文，其他插件不影响 token。

整个仓库 **没有运行时代码**——所有 Agent、Skill、Command 都是 markdown 文件。Agent 是带 frontmatter 的 markdown（声明 name、description、tools、model 等），主体是 system prompt。Skill 是可被 Agent 自动加载的领域知识包（progressive disclosure：仅在匹配时加载）。Command 是 slash 命令的声明性定义。Claude Code（或 Gemini CLI）作为宿主负责实际运行——读取插件文件，把 Agent 注册为可调用的角色，把 Skill 装进检索池，把 Command 注册为 slash 命令。安装一个插件（例如 `python-development`）只加载它的 3 个 Agent（python-pro / django-pro / fastapi-pro）+ 16 个 Skill 到上下文（约 1000 token），不会拉取整个 marketplace 的资源。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **Agent 即 Markdown 文件**：每个 Agent 角色就是一个带 frontmatter 的 markdown，用 git 管理、用 PR 协作，无运行时代码。这种"Prompt as Code"模式让 Agent 角色可版本化、可 review、可复用。
2. **细粒度插件 + 按需加载**：80 个插件每个聚焦单一领域，平均每个含 3.6 个组件（符合 Anthropic 推荐的 2-8 模式）。用户只装需要的，避免 Claude 上下文被 185 个 Agent 全量塞满。
3. **三层模型策略 + Progressive Disclosure**：Agent 配置时声明用 Haiku（简单）/ Sonnet（中等）/ Opus（复杂）。Skill 在被任务匹配时才加载具体内容（progressive disclosure）。两者共同把 token 成本压到极致。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `plugins/agent-orchestration/` | 多 Agent 怎么协调 | 提供编排相关的 Agent 角色 + 命令 |
| `plugins/agent-teams/` | 团队协作 | 团队级 Agent 角色定义 |
| `plugins/full-stack-orchestration/` | 全栈多 Agent 工作流 | 跨前后端的 Agent 组合 |
| `plugins/conductor/` | 协调器抽象 | Orchestrator 角色实现 |
| `plugins/comprehensive-review/` | 多视角代码审查 | architect-review / code-reviewer / security-auditor 三个 Agent 协同 |
| `plugins/context-management/` | 上下文怎么管 | 上下文管理相关的 Agent 与策略 |
| `plugins/python-development/` | Python 领域专家 | python-pro / django-pro / fastapi-pro 三个 Agent + 16 Skill |
| `plugins/javascript-typescript/` | JS/TS 领域专家 | javascript-pro / typescript-pro |
| `plugins/security-scanning/` | 安全扫描 | SAST 相关 Agent |
| `plugins/llm-application-dev/` | LLM 应用开发 | LLM 相关 Agent 与 Skill |
| `plugins/observability-monitoring/` | 可观测性 | 监控相关 Agent |
| `plugins/plugin-eval/` | 插件质量评估 | 评估框架（layers / dimensions / scoring） |
| `plugins/review-agent-governance/` | Agent 治理审查 | 治理相关角色与流程 |
| `plugins/signed-audit-trails/` | 审计追溯 | 签名审计相关组件 |
| `plugins/protect-mcp/` | MCP 保护 | MCP 安全相关 Agent |
| `docs/architecture.md` | 项目架构原则 | 设计原则与模式说明 |
| `docs/plugin-eval.md` | 插件评估方法 | layers / dimensions / scoring 框架 |
| `Makefile` | 多平台构建 | `make generate-plugin PLUGIN=<name>` 生成 Gemini 扩展 |

### 详细说明

- **Agent 即 Markdown 文件**：每个 Agent 是一个 `.md` 文件，frontmatter 声明 `name`、`description`、`tools`、`model`、`triggers`，主体是 system prompt。例如 `python-pro.md` 里写"你是 Python 专家，擅长 X、Y、Z..."。这种格式：①人类可读；②git 友好；③无需运行时；④跨平台（Claude Code、Gemini CLI 都消费同一份）。

- **80 插件按"职责单一"拆分**：每个插件平均 3.6 个组件（Agent + Skill + Command），符合 Anthropic 推荐的 2-8 模式。安装一个插件只加载它的资源，避免 token 浪费。例如装 `python-development` 只加载 3 个 Python Agent + 16 个 Python Skill（约 1000 token），不拉取整个 marketplace。

- **三层模型策略**：每个 Agent 配置时声明使用 Haiku（轻量、快速、便宜）/ Sonnet（中等推理）/ Opus（强推理、慢、贵）。简单任务（语法检查、格式化）用 Haiku，复杂任务（架构设计、安全审计）用 Opus。文档明确推荐这种分级路由，节省成本。

- **Progressive Disclosure（渐进披露）**：Skill 是"领域知识包"，平时不加载到上下文。Agent 接到任务时，系统检索匹配的 Skill 自动注入上下文。例如 Python Agent 接到 Django 任务，只加载 Django 相关 Skill，不加载 FastAPI 的。这是把 RAG 思想用到 prompt 工程的实践。

- **PluginEval 框架（`docs/plugin-eval.md`）**：项目自带插件质量评估方法论，分 layers（评估层级）、dimensions（评估维度）、scoring（评分规则）。任何人提交新插件都按这个框架评估。这是"插件市场治理"的一种工程化做法。

- **Gemini CLI 跨平台**：同一份 markdown 文件可以同时被 Claude Code 和 Gemini CLI 消费。Gemini 通过 `gemini extensions install` 安装，识别同样的 Agent / Skill 定义。这种"声明式格式 + 多宿主"模式让 Agent 资源可移植。

- **Makefile + 选择性 commit**：`make generate-plugin PLUGIN=<name>` 在本地生成对应插件的 slash 命令文件，不 commit 到仓库。这种"用户态生成、不污染上游"的工作流让用户可定制但不会反向污染主仓库。

- **`comprehensive-review` 是多 Agent 协作模板**：单个插件就含三个 Agent（architect-review / code-reviewer / security-auditor），协同完成"多视角审查"。这是把 OMC、ruflo 那种"swarm 协作"概念落地到插件粒度的范例——一个插件即一个小团队。

- **不提供编排运行时**：仓库本身只有定义没有运行时。多 Agent 编排靠宿主（Claude Code 内置）或其他工具（OMC 等）实现。这种"职责分离"让插件库专注于内容，运行时另选。

## 4. 关键细节

- **数量级**：80 plugins / 185 agents / 153 skills / 100 commands / 16 workflow orchestrators。规模反映"agent 角色应该按职责精细切分"的设计哲学。
- **`docs/agents.md`**：完整的 Agent 索引，按类别组织。这是 Agent prompt 写作的最佳参考库。
- **`docs/agent-skills.md`**：153 个 Skill 的索引，按 progressive disclosure 模式组织。Skill 是 prompt 工程的进阶——把"什么时候用什么知识"也工程化。
- **`docs/architecture.md`**：项目自身的架构与设计原则文档。明确写出 plugin 设计模式、组件粒度、加载策略。
- **`docs/plugin-eval.md`**：PluginEval 框架文档。这是开源项目里少见的"自带质量评估方法论"。
- **`gemini-extension.json`**：Gemini CLI 扩展声明文件，列出哪些 Skill 暴露给 Gemini。这是跨宿主能力声明的范例。
- **Smithery badge**：项目接入 Smithery（MCP 包注册中心），意味着 Skill 也可以作为 MCP 工具暴露。
- **没有 `src/` 或代码语言专属目录**：项目本身只有 markdown 和 yaml 类元数据。语言标签 Python 是因为 `tools/` 里有 Python 脚本。这佐证了"声明式资源库"定位。
- **`block-no-verify` 插件**：阻止 git commit `--no-verify`（绕过 hooks）的小插件。反映项目对工程纪律的重视——把"不该绕过 hook"做成可强制执行的插件。
- **`signed-audit-trails`**：提供"签名审计追踪"的 Agent。这是企业级合规场景的角色，也对应可观测性 / 溯源能力的需求。
- **`Makefile` 的 `generate-plugin` 命令**：体现"按需生成 + 不入库"的工程模式。用户在本地按需展开，仓库只保留模板源。
- **README 反复强调"零运行时代码"**：项目作者明确把"内容"和"运行时"解耦——这是成熟开源项目的常见模式（运行时由宿主提供，内容通过 marketplace 持续演进）。
