# AgentHub × SAP L2A PPT 生成提示词

> 用途：直接提供给支持 PPT 生成的 AI（Gamma、MindShow、GPT-4 with code interpreter 等）

---

请帮我生成一份 PowerPoint 演示文稿，主题是 AgentHub × SAP L2A 能力中心的融合方案展示。用于学生竞赛 Demo 汇报，受众是 SAP 技术评委和产品负责人。

---

## 演示文稿要求

- 风格：科技感、简洁专业，蓝色/深色系为主调
- 总页数：12~15 页
- 语言：中文为主，技术术语保留英文
- 每页包含：标题、核心内容（文字 + 示意图或表格）、最多 4 条 bullet point

---

## 内容结构与每页要点

### 第1页：封面
- 标题：AgentHub × SAP L2A —— 国家本地化 AI 研究助理
- 副标题：多 Agent 并行协作 · MCP 工具原生接入 · SAP 专业知识沉淀
- 配图：多个 Agent 并行执行的流程示意（圆形节点 + 并行箭头）

### 第2页：问题背景
- 痛点1：SAP 国家本地化研究工作量大，法规、ABAP 代码、已有方案散落在多个系统
- 痛点2：现有 AI 工具（Joule/ABAP AI）能力碎片化，缺乏系统性协同
- 痛点3：L2A Capability Hub 积累了 70+ 专业 Skill、11 个 MCP Server，但缺乏统一编排入口
- 结论引导：需要一个能把这些专业能力「拼」起来的平台

### 第3页：解决方案定位
- 三层能力架构图（横向）：
  - 最底层：SAP 基础 AI（Joule、ABAP AI）
  - 中层：L2A Capability Hub（70+ Skills、11 MCP Servers）
  - 顶层：AgentHub 编排层（本项目）
- 核心定位句：「L2A 告诉我们能做什么，AgentHub 告诉我们怎么组合」

### 第4页：AgentHub 核心架构
- 架构图：用户 → Orchestrator（主 Agent） → N 个子 Agent 并行运行 → 汇总回答
- 关键设计理念（4条）：
  - Orchestrator 独享工具权限（文件写入、代码部署、MCP 调用），保证操作可审计
  - 子 Agent 纯文本输出，职责清晰、相互隔离
  - asyncio.Event 唤醒机制，子 Agent 完成即触发 Orchestrator 继续
  - SSE 流式推送，前端实时可见每个 Agent 的"思考"过程

### 第5页：五大会话模式
展示为5个卡片（图标 + 名称 + 一句话说明）：
- 单聊模式 — 直连子 Agent，轻量快速
- 群聊模式 — Orchestrator 8步循环，多 Agent 协作
- 广播模式 — 全员参与，70% 响应概率，模拟 IM 群聊
- @提及模式 — 静默调度，等待结果后汇报用户
- 本地编辑模式 — DiffApplyService 直接文件修改

### 第6页：SAP L2A 专项功能 — 能力接入
左右分栏：
- 左：L2A Skills 接入（3个 Skill 卡片）
  - glo_document_grounding：GLO 文档语义检索
  - glorepo_abap：ABAP 对象图谱搜索
  - localization_support_assistant：本地化方案顾问
- 右：L2A MCP Server 接入（3个 Server 卡片）
  - globalization-taxonomy：国家本地化范围、S/4HANA 能力关系图谱（OIDC 认证）
  - sap-mcp-glorepo：GLO 知识图谱，ABAP/CDS/DRC 配置（OAuth2 认证）
  - spec-to-code：综合 AI 服务，SAP Note 查询（OIDC 认证）
- 说明：Skills 作为背景知识注入子 Agent prompt，MCP Server 由 Orchestrator 工具调用

### 第7页：SAP 本地化研究小队
四个 Agent 介绍（2×2 卡片布局）：
- 法规研究 Agent — 绑定 glo_document_grounding Skill，搜索法规法条
- ABAP 代码探索 Agent — 绑定 glorepo_abap Skill，分析现有实现
- 本地化顾问 Agent — 绑定 localization_support_assistant Skill，生成改造建议
- 方案综合 Agent — 整合三路输出，生成完整研究报告

底部说明：四 Agent 并行运行，前端实时可见"思考"气泡

### 第8页：Demo 场景 — 新国家本地化研究
流程图（从上到下）：
1. 用户输入：「帮我分析 Vietnam 的电子发票 eDocument 本地化需求，我有一段 ABAP 代码」
2. Orchestrator：调用 globalization-taxonomy MCP 预处理，识别场景，并行派发3个 Agent
3. 并行执行：法规研究 / ABAP 探索 / 顾问建议（三路并行箭头）
4. 方案综合 Agent：整合三路输出
5. 输出：结构化研究报告（法规摘要 + ABAP 参考 + 改造路径 + 开发计划）

强调：全程前端可见每个 Agent 实时"思考"过程

### 第9页：前端交互展示
截图或示意图：多 Agent 并行"思考"气泡（typing indicator）

展示特性列表：
- Workflow 视图：实时显示 Orchestrator 派发的 Thread 树
- 流式输出：每个 Agent 的回答实时逐字显示
- 审批流：高风险操作（写文件/部署）弹出审批卡片，用户确认后执行
- 头像系统：每个 Agent 独立头像，群聊场景视觉清晰

### 第10页：技术亮点
- 6层 Prompt 流水线（横向管道示意图）：
  - 静态层（缓存）：orchestrator.md / Skills 索引 / 场景 Prompt（sap_localization_scene.md）
  - 动态层（每轮重算）：记忆索引 / 对话历史 / Agent 列表 / 任务图
- AnthropicSDKAdapter 新特性：直连 Anthropic API，原生支持 MCP 工具注入，无需 CLI 进程
- Docker 沙箱：每会话独立容器，30 分钟空闲自动回收

### 第11页：竞争对比

| 维度 | Joule / ABAP AI | L2A Capability Hub 单独使用 | AgentHub + L2A（本方案） |
|---|---|---|---|
| 专业知识深度 | 通用 | ✅ 深度 SAP 专业 | ✅ 深度 SAP 专业 |
| 多任务并行 | ❌ | ❌ | ✅ 并行子 Agent |
| MCP 工具集成 | 部分 | ✅ 原生 | ✅ 原生集成 |
| 编排与协调 | ❌ | ❌ | ✅ Orchestrator |
| 操作审批 | ❌ | ❌ | ✅ 全链路可审计 |
| 可视化过程 | ❌ | ❌ | ✅ 实时 Workflow 视图 |

### 第12页：总结与展望
三大核心价值（图标 + 一句话）：
- 🔗 融合：将 L2A 70+ 专业能力统一接入可编排的 AI 平台
- ⚡ 效率：并行 Agent 架构，复杂研究任务分钟级完成
- 🔍 可信：全链路审批 + 实时可见，AI 操作不再是黑盒

后续方向（3条）：
- 接入更多 L2A MCP Server（solution-patterns、spec-to-code）
- 支持更多本地化场景（eDocument、DRC 报表、SAP Note 解析）
- 前端 Squad 选择优化，支持场景分组与智能推荐

### 第13页：致谢页
- 项目名：AgentHub × SAP L2A
- 团队：咕嘎一辈子队
- 技术栈：Python + FastAPI + Vue 3 + Anthropic API + SAP L2A Capability Hub

---

## 特别说明

- 流程图和架构图请用简洁的矩形框 + 箭头形式描述，我会在 PPT 中手动绘制
- 如果工具支持，请直接生成 .pptx 文件；否则请输出每页的详细文字内容和布局建议
- 技术细节请保持准确，勿过度简化 MCP 和 Orchestrator 的工作机制
