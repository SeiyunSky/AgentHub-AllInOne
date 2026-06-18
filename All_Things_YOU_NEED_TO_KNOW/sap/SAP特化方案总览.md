# AgentHub SAP 特化方案总览

> 文档记录 AgentHub 参加 SAP 内部 Competition（截止 7/3）的设计思路、技术方案和接入机制。

---

## 一、背景与核心定位

### 比赛背景

- SAP 内部竞赛，6/19 了解思路，**7/3 提交 Idea**
- 需要和 L2A（Law to Action）团队联动，Demo 场景用真实 Capability Hub 工具

### 核心 Pitch

> **"Capability Hub 告诉我们能做什么，AgentHub 告诉我们怎么组合起来做。"**
>
> Capability Hub 有 70+ skills 和 11 个 MCP server，每个都是强大的单点工具。
> 但复杂的本地化任务需要同时用多个工具，并行调研多个数据源，再合成结果。
> AgentHub 是 Capability Hub 的**并行编排层**。

### 差异化定位（三层结构）

| 层次 | 代表产品 | 解决什么 |
|---|---|---|
| 基础能力层 | Joule、ABAP AI Code Gen | 单点任务加速 |
| 工具库层 | L2A Capability Hub | "有哪些 skill/MCP" |
| **编排层** | **AgentHub（我们的）** | "怎么让工具协作完成复杂任务" |

---

## 二、主 Demo 场景：新国家本地化研究

### 场景描述

**输入**：
- 用户的 ABAP 代码（需要适配本地化的代码片段）
- 目标国家（如：越南、韩国）

**输出**：
- 该国法规要求分析
- 现有 ABAP 实现参考
- 本地化修改建议
- 结构化开发方案（推荐创建/修改的 ABAP 对象 + 实施 roadmap）

### 流程设计

```
用户输入: "帮我研究越南的 e-invoicing 要求，这是需要本地化的代码：[ABAP代码]"
    ↓
Orchestrator 预处理：
  - 调 globalization-taxonomy MCP 查越南本地化能力范围：Globalization Taxonomy Knowledge Graph — semantic search over SAP Help Portal content and SPARQL queries for country localization features, business processes, and S/4HANA capability relationships.
  - 读取用户 ABAP 代码内容
    ↓
[并行，3 个 Agent 同时出发]
├── 法规调研 Agent (glo-document-grounding skill)
│     → 搜索该国 SAP Notes、KBAs、法规要求
├── ABAP 探索 Agent (glorepo-abap skill)
│     → 搜索 GLO Repo 现有本地化 ABAP 实现参考
└── 本地化顾问 Agent (localization-support-assistant skill)
      → 分析用户代码，给出针对该国的修改建议
    ↓
方案汇总 Agent（整合三路结果）
    ↓
Orchestrator → respond_to_user（完整方案报告）
```

### 为什么是主 Demo

1. **视觉冲击**：3个 Agent 并行出发，前端能同时看到多个"思考中"指示条
2. **直接对应 L2A 使命**：Law to Action = 把各国法规转化为 ABAP 行动
3. **非技术评委友好**：不需要懂 ABAP，能看懂"多人同时去不同地方查资料，然后汇总"
4. **MCP 全部 stable**：Demo 用到的 MCP 全是 stable 状态，不是 mock

---

## 三、L2A Capability Hub 能力清单（真实仓库数据）

仓库地址：`https://github.tools.sap/law-to-action/l2a-capability-hub`

### MCP Servers（相关的 stable 状态）

| MCP Name | Status | 用途 | Demo 场景 |
|---|---|---|---|
| `spec-to-code` | stable | 综合服务：document grounding、ABAP 读取、SAP Note | 所有场景 |
| `globalization-taxonomy` | stable | 本地化知识图谱，语义搜索国家本地化范围 | **场景预处理** |
| `sap-mcp-glorepo` | stable | GLO 知识图谱：搜 ABAP 对象、CDS、DRC 配置 | 调研现有实现 |
| `solution-patterns` | stable | DRC 方案蓝图、业务上下文 | 查方案参考 |
| `servicenow` | stable | CS Case 管理 | 场景三（bug fix）|

### Skills（主 Demo 用到的）

| Skill | 文件路径 | 用途 |
|---|---|---|
| `localization-support-assistant` | `skills/localization-support-assistant/SKILL.md` | 本地化顾问主力，处理法规问题 |
| `glo-document-grounding` | `skills/glo-document-grounding/SKILL.md` | 搜内部文档、SAP Notes、KBAs |
| `glorepo-abap` | `skills/glorepo-abap/SKILL.md` | 搜 GLO Repo 中的 ABAP 对象 |

---

## 四、子 Agent 配置方案

### Squad 模板文件

文件位置：`backend/squads/sap_localization_squad.json`

```json
{
  "id": "sap_localization_squad",
  "name": "SAP 本地化研究小队",
  "description": "并行调研目标国家的 e-invoicing/本地化要求，结合现有 ABAP 实现，生成本地化开发方案",
  "icon": "global",
  "agent_ids": [
    "agent-sap-law-researcher",
    "agent-sap-abap-explorer",
    "agent-sap-localization-advisor",
    "agent-sap-solution-synthesizer"
  ]
}
```

### 四个子 Agent

| Agent ID | 名称 | 挂载 Skill | 职责 |
|---|---|---|---|
| `agent-sap-law-researcher` | 法规调研 Agent | `glo_document_grounding` | 搜法规要求、SAP Notes |
| `agent-sap-abap-explorer` | ABAP 代码调研 Agent | `glorepo_abap` | 搜现有 ABAP 实现参考 |
| `agent-sap-localization-advisor` | 本地化顾问 Agent | `localization_support_assistant` | 分析代码给出修改建议 |
| `agent-sap-solution-synthesizer` | 方案汇总 Agent | 无 | 整合三路结果生成开发方案 |

---

## 五、Orchestrator 新增调度章节

在 `backend/prompts/orchestrator.md` 中增加"SAP 本地化研究专属调度"章节，参见 `SAP_Orchestrator_Scene_Prompt.md`。

---

## 六、动态 Scene Prompt 加载机制

### 现有机制

- Squad JSON = 哪些 Agent 组成集群
- `orchestrator.md` 的专属调度章节 = 该集群的 orchestrator 行为

### 扩展建议

在 Squad JSON 加 `scene_prompt_key` 字段，`prompt_builder.py` 读取时动态追加对应 scene prompt 文件。

```json
{
  "id": "sap_localization_squad",
  "scene_prompt_key": "sap_localization_scene"
}
```

`prompt_builder.py` 的 `_layer_4_agenthub_md_chain` 可以扩展为读取 `prompts/scenes/{scene_prompt_key}.md` 文件。

---

## 七、时间节点

| 截止 | 任务 |
|---|---|
| 6/19 | 确定主 Demo 场景（场景一），口头描述清楚 pitch |
| 6/25 | Scene prompt 文件格式确定，写出 SAP 本地化调度 prompt |
| 6/27 | AgentHub 接入 Capability Hub 至少一个 MCP（globalization-taxonomy 开始）|
| 7/1 | Demo 视频录制（并行 Agent 运行可视化）|
| 7/3 | Idea 提交，附 Demo 视频链接 |
