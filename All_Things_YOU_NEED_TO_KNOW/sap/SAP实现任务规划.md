# AgentHub SAP 特化实现任务规划

> 本文档作为独立 Agent 的开发提示词，包含完整的任务步骤、技术细节、文件路径和验收标准。
>
> **背景**：AgentHub 参加 SAP 内部 Competition（7/3 提交），核心 Demo 是"SAP 本地化研究"场景——用户提供 ABAP 代码和目标国家，多个 Agent 并行调研法规/现有实现/本地化建议，汇总生成开发方案。

---

## 任务一：Orchestrator 动态加载场景 Prompt

### 目标

让 Orchestrator 根据当前会话挂载的子 Agent 组合，自动加载对应的专属调度 prompt（而不是把所有场景逻辑都塞进一个 `orchestrator.md`）。同时保留 default 通用 prompt 作为兜底。

### 背景

当前架构：`prompt_builder.py` 的 `_layer_4_agenthub_md_chain` 读取项目根 `AGENTHUB.md` 和部署 cwd `AGENTHUB.md` 作为"部署级全局指令"。**这个层可以扩展为按 squad 动态加载 scene prompt。**

Squad JSON 当前结构：
```json
{ "id": "dev_squad", "name": "...", "agent_ids": [...] }
```

目标结构（新增 `scene_prompt_key` 字段）：
```json
{ "id": "dev_squad", "scene_prompt_key": "dev_scene", "agent_ids": [...] }
```

### 实现步骤

**1.1 修改 Squad JSON 格式**

给每个 Squad JSON 加 `scene_prompt_key` 字段，值对应 `backend/prompts/scenes/` 目录下的 `.md` 文件 stem：

```
backend/squads/dev_squad.json      → scene_prompt_key: "dev_scene"
backend/squads/data_squad.json     → scene_prompt_key: "data_scene"
backend/squads/sap_squad.json      → scene_prompt_key: "sap_localization_scene"  (新建)
```

**1.2 创建 `backend/prompts/scenes/` 目录**

每个 `.md` 文件包含该场景下 orchestrator 的**专属调度指令**（拆出来的部分），例如：

- `dev_scene.md`：现有 orchestrator.md 里"全链路协作任务调度（调研 → 代码 → 审核 → 部署）"章节
- `data_scene.md`：现有 orchestrator.md 里"数据分析群组专属调度"章节
- `sap_localization_scene.md`：新写的 SAP 本地化研究专属调度章节

**1.3 修改 `prompt_builder.py`**

文件：`backend/services/orchestrator/prompt_builder.py`

修改 `_layer_4_agenthub_md_chain` 方法（或新增 `_layer_4b_scene_prompt` 方法），在构建 system prompt 时：

1. 通过 `ctx.conversation_id` 查询当前会话关联的 Squad（需要查 `conversations` 表的 `squad_id` 字段，或从会话 agents 集合推断）
2. 读取 Squad JSON 的 `scene_prompt_key` 字段
3. 加载 `backend/prompts/scenes/{scene_prompt_key}.md` 内容，追加到 prompt

推断逻辑（如果没有 squad_id 字段，可以通过匹配 agent_ids）：
```python
async def _get_scene_prompt_for_conversation(self, conversation_id: str) -> str:
    """根据会话中的 Agent 组合，查找匹配的 squad 并加载其 scene prompt。"""
    from backend.core.database import SessionLocal
    from backend.services.conversation_service import conversation_service
    import json
    from pathlib import Path

    try:
        agents = await conversation_service.get_active_agents(conversation_id)
        agent_ids = {a.id for a in agents}

        squads_dir = Path(__file__).resolve().parent.parent.parent / "squads"
        for path in squads_dir.glob("*.json"):
            squad = json.loads(path.read_text(encoding="utf-8"))
            squad_agent_ids = set(squad.get("agent_ids", []))
            scene_key = squad.get("scene_prompt_key")
            if scene_key and squad_agent_ids and squad_agent_ids.issubset(agent_ids):
                scene_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "scenes" / f"{scene_key}.md"
                if scene_path.exists():
                    return scene_path.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""
```

**1.4 修改 orchestrator.md（精简）**

把现有 orchestrator.md 中场景专属的章节**剪切**到对应 scene 文件，orchestrator.md 保留：
- 通用工作流（派活规则、dispatch_prompt 规范、子 Thread 结果处理）
- default 兜底行为：当没有匹配 scene 时，orchestrator 仅依赖 Layer 6 动态上下文中的 Agent 描述信息进行调度

### 验收

- 创建一个 dev_squad 会话，system prompt 里包含 dev_scene.md 的内容
- 创建一个 data_squad 会话，system prompt 里包含 data_scene.md 的内容
- 创建一个没有 squad 对应的普通会话，system prompt 里只有通用 orchestrator.md 内容

---

## 任务二：编写 SAP 本地化场景 Prompt

### 目标

生成两个文件：
1. `backend/prompts/scenes/sap_localization_scene.md`：SAP 本地化研究的 orchestrator 专属调度指令
2. `backend/prompts/agents/sap_*.md`：各子 Agent 的人格 prompt

### 背景：场景流程

```
用户输入：ABAP 代码 + 目标国家（如越南）
    ↓
Orchestrator 预处理：
  - 调 globalization-taxonomy MCP 查目标国家本地化能力范围
  - 从消息中提取 ABAP 代码内容
    ↓
[并行，3 个子 Agent 同时出发]
├── 法规调研 Agent → 搜该国 SAP Notes、KBAs、法规要求
├── ABAP 探索 Agent → 搜 GLO Repo 现有本地化 ABAP 实现参考
└── 本地化顾问 Agent → 分析用户代码，给出针对该国的修改建议
    ↓
方案汇总 Agent（整合三路结果）
    ↓
respond_to_user：完整本地化开发方案报告
```

### 2.1 `sap_localization_scene.md` 内容要求

- **场景识别条件**：用户提到"本地化"、"e-invoicing"、"localization"、具体国家名（越南/韩国等），或提供了 ABAP 代码
- **MCP 预处理**：明确说明 orchestrator 需要先调 `globalization-taxonomy` MCP 查该国范围，把结果备用
- **三路并行**：明确三个子 Agent 各自的任务段、背景段要贴什么内容、交付物格式
- **串行汇总**：方案汇总 Agent 需要 `blocked_by` 三个并行 Thread
- **MCP 能力限制说明**：所有 MCP 只读，输出是"建议方案"而非直接写入 SAP 系统
- **输出格式**：法规摘要 + 现有实现参考 + 代码修改建议 + 实施 roadmap

### 2.2 子 Agent prompt 文件

需要创建以下文件（格式参考现有 `backend/prompts/agents/coder.md`）：

| 文件名 | Agent 名称 | 核心职责 |
|---|---|---|
| `sap_law_researcher.md` | 法规调研 Agent | 使用 glo-document-grounding skill 搜索目标国家 SAP Notes、KBAs、法规要求 |
| `sap_abap_explorer.md` | ABAP 代码调研 Agent | 使用 glorepo-abap skill 搜索 GLO Repo 中现有的本地化 ABAP 实现参考 |
| `sap_localization_advisor.md` | 本地化顾问 Agent | 使用 localization-support-assistant skill，分析用户 ABAP 代码给出修改建议 |
| `sap_solution_synthesizer.md` | 方案汇总 Agent | 整合三路调研结果，生成结构化本地化开发方案和实施 roadmap |

每个 prompt 文件需包含：
- 角色定位
- 输入格式约束（从 dispatch_prompt 里能拿到什么）
- 禁止行为（不能修改 SAP 系统、不能捏造 SAP Note）
- 输出格式规范

---

## 任务三：手动下载 L2A Skills 到本地

### 目标

把 L2A 仓库中与 SAP 本地化场景相关的 skill 内容复制到 `backend/skills/` 目录，让 `scan_builtin()` 自动入库。

### 需要的 Skills

从 `https://github.tools.sap/law-to-action/l2a-capability-hub` 获取以下文件内容：

| L2A 源路径 | 本地目标文件 | 备注 |
|---|---|---|
| `skills/glo-document-grounding/SKILL.md` | `backend/skills/glo_document_grounding.md` | 完整保留 |
| `skills/glorepo-abap/SKILL.md` | `backend/skills/glorepo_abap.md` | 完整保留 |
| `skills/localization-support-assistant/SKILL.md` | `backend/skills/localization_support_assistant.md` | **裁剪**：只保留 Workflow、Constraints、Output Format 三章节，原文 47KB 过大 |

**文件格式要求**：

- 保留 frontmatter（`---` 包裹），但去掉 `tools:` 字段（这是 Claude Code CLI 专用的，AgentHub 不需要）
- 正文 markdown 内容完整保留

**frontmatter 示例**（处理后）：
```markdown
---
name: glo_document_grounding
description: 搜索 SAP Globalization 内部文档，回答 DRC、e-invoicing、本地化相关问题
category: SAP 本地化
---

（正文内容）
```

### 验收

后端启动后，`skills` 表中应出现三条新记录（`name` 分别为 `glo_document_grounding`、`glorepo_abap`、`localization_support_assistant`）。

---

## 任务四：完善 MCP Server Seed

### 目标

在 `backend/seeds/mcp_servers.py` 的 `PRESET_MCP_SERVERS` 中添加 SAP 本地化场景所需的 L2A MCP Server 配置。

### 需要添加的 MCP

**文件**：`backend/seeds/mcp_servers.py`

> URL 从 `DO_NOT_COMMIT/sap_l2a_mcp_config.md` 获取，填入下方 `url` 字段。

```python
import os

# 在 PRESET_MCP_SERVERS 列表中追加：

{
    "id": "l2a-globalization-taxonomy",
    "name": "Globalization Taxonomy",
    "description": "SAP 本地化知识图谱 — 语义搜索国家本地化范围、S/4HANA 能力关系，SPARQL 查询",
    "transport": "streamable_http",
    "url": "<见 DO_NOT_COMMIT/sap_l2a_mcp_config.md>",
    "headers": {"Authorization": f"Bearer {os.environ.get('L2A_TAXONOMY_TOKEN', '')}"},
    "author_id": "GUGA",
    "is_public": 1,
    "is_active": 1,
},
{
    "id": "l2a-sap-mcp-glorepo",
    "name": "SAP GLO Repository",
    "description": "GLO 知识图谱 — 搜索 ABAP 对象、CDS 视图、DRC 报表配置、eDocument 配置",
    "transport": "streamable_http",
    "url": "<见 DO_NOT_COMMIT/sap_l2a_mcp_config.md>",
    "headers": {"Authorization": f"Bearer {os.environ.get('L2A_GLOREPO_TOKEN', '')}"},
    "author_id": "GUGA",
    "is_public": 1,
    "is_active": 1,
},
{
    "id": "l2a-spec-to-code",
    "name": "Spec to Code",
    "description": "SAP GLO 综合 AI 服务 — document grounding、ABAP artifact 读取、SAP Note 查询、ServiceNow 集成",
    "transport": "streamable_http",
    "url": "<见 DO_NOT_COMMIT/sap_l2a_mcp_config.md>",
    "headers": {"Authorization": f"Bearer {os.environ.get('L2A_SPEC_TO_CODE_TOKEN', '')}"},
    "author_id": "GUGA",
    "is_public": 1,
    "is_active": 1,
},
```

### 认证说明

所有 L2A MCP 均需 SAP 内部认证，`headers` 暂时留空，**Demo 前手动填入 token**（通过环境变量注入方案待后续完善）。headers 格式：`{"Authorization": "Bearer <token>"}`。

### `seed_orchestrator_mcp_links()` 无需修改

现有函数自动把所有 `PRESET_MCP_SERVERS` 关联到 orchestrator，追加配置后自动生效。

---

## 任务五：完善 Agent Seed

### 目标

在 `backend/seeds/agents.py` 的 `PRESET_AGENTS` 中添加 SAP 本地化场景的四个子 Agent，并绑定 skills 和 MCP。

### 新增 Agent 配置

**文件**：`backend/seeds/agents.py`

在 `PRESET_AGENTS` 末尾（岁家四人组之后）追加 SAP 小队：

```python
# ====================================================================
# SAP 本地化研究小队（L2A 接入）
# ====================================================================
{
    "id": "agent-sap-law-researcher",
    "user_id": "GUGA",
    "name": "SAP 法规调研 Agent",
    "description": "搜索目标国家的 e-invoicing/本地化法规要求、SAP Notes 和 KBAs",
    "type": "claude",
    "prompt_key": "sap_law_researcher",
    "capabilities": {},
    "avatar": "/static/avatars/avatar-10.jpg",
    "is_active": 1,
    "is_public": 1,
    "default_skills": ["glo_document_grounding"],
},
{
    "id": "agent-sap-abap-explorer",
    "user_id": "GUGA",
    "name": "SAP ABAP 探索 Agent",
    "description": "在 GLO Repo 中搜索目标国家现有的 ABAP 本地化实现参考对象",
    "type": "claude",
    "prompt_key": "sap_abap_explorer",
    "capabilities": {},
    "avatar": "/static/avatars/avatar-11.jpg",
    "is_active": 1,
    "is_public": 1,
    "default_skills": ["glorepo_abap"],
},
{
    "id": "agent-sap-localization-advisor",
    "user_id": "GUGA",
    "name": "SAP 本地化顾问 Agent",
    "description": "分析现有 ABAP 代码，给出针对目标国家的本地化修改建议",
    "type": "claude",
    "prompt_key": "sap_localization_advisor",
    "capabilities": {},
    "avatar": "/static/avatars/avatar-12.jpg",
    "is_active": 1,
    "is_public": 1,
    "default_skills": ["localization_support_assistant"],
},
{
    "id": "agent-sap-solution-synthesizer",
    "user_id": "GUGA",
    "name": "SAP 方案汇总 Agent",
    "description": "整合三路调研结果，生成结构化的 ABAP 本地化开发方案和实施 roadmap",
    "type": "claude",
    "prompt_key": "sap_solution_synthesizer",
    "capabilities": {},
    "avatar": "/static/avatars/avatar-13.jpg",
    "is_active": 1,
    "is_public": 1,
    "default_skills": [],
},
```

### MCP 绑定

SAP Agent 本身不直接调用 MCP（当前架构中子 Agent 无工具权限），MCP 由 orchestrator 调用后把结果粘贴给子 Agent。**因此 Agent 的 MCP 绑定暂时不需要**，待后续架构升级再处理。

### 验收

后端启动后，`agents` 表中应出现四条新记录；`agent_skills` 表中应有对应的 skill 绑定关系。

---

## 任务六：添加 SAP 小队 JSON

### 目标

创建 `backend/squads/sap_squad.json`，让前端新建对话页面自动显示 SAP 本地化研究小队。

### 文件内容

```json
{
  "id": "sap_localization_squad",
  "name": "SAP 本地化研究小队",
  "description": "并行调研目标国家 e-invoicing/本地化要求，结合现有 ABAP 实现，生成本地化开发方案",
  "icon": "global",
  "scene_prompt_key": "sap_localization_scene",
  "agent_ids": [
    "agent-sap-law-researcher",
    "agent-sap-abap-explorer",
    "agent-sap-localization-advisor",
    "agent-sap-solution-synthesizer"
  ]
}
```

同时，给现有其他 squad 的 JSON 补上 `scene_prompt_key` 字段：
- `dev_squad.json` → `"scene_prompt_key": "dev_scene"`
- `data_squad.json` → `"scene_prompt_key": "data_scene"`

---

## 任务七：前端群聊选择 UI 优化

### 目标

当前 `NewChatDialog.vue` 的群聊选择是 `grid grid-cols-2` 的平铺卡片，随着群聊数量增加会撑高对话框。改为可折叠的分类展示或下拉式组件。

### 方案：分类折叠列表

**分类规则**（可以在 squad JSON 中加 `category` 字段）：

```json
{ "category": "工程研发", "id": "dev_squad", ... }
{ "category": "数据分析", "id": "data_squad", ... }
{ "category": "SAP 开发", "id": "sap_localization_squad", ... }
{ "category": "角色扮演", "id": "chat_squad", ... }
```

**前端修改位置**：`frontend/src/components/chat/NewChatDialog.vue`

将现有的 `grid grid-cols-2` 平铺改为按 `category` 分组，每组显示分类标题 + 展开/折叠按钮，默认展开第一个分类，其他折叠。

**技术实现建议**：
- `squads` 按 `category` 分组：`const groupedSquads = computed(() => groupBy(squads.value, s => s.category ?? '其他'))`
- 每组用 `<details>/<summary>` 原生折叠或 `v-show` + 展开状态变量
- 已选中的 squad 所在分组自动展开

**图标补充**：在现有 `squadIcon` 的 icon map 中加 `"global": "🌐"`（SAP 用）。

---

## 任务八（补充）：迁移现有场景 Prompt 并保持兼容

### 目标

把 `orchestrator.md` 中场景专属的两个章节剪切到 scene 文件，同时确保没有 scene 的旧会话不受影响。

### 操作

1. 新建 `backend/prompts/scenes/dev_scene.md`，内容为现有 orchestrator.md 的"全链路协作任务调度（调研 → 代码 → 审核 → 部署）"章节（约 40 行）
2. 新建 `backend/prompts/scenes/data_scene.md`，内容为现有 orchestrator.md 的"数据分析群组专属调度"章节（约 60 行）
3. 从 `orchestrator.md` 删除这两个章节，改为一句引导语：`具体场景的调度规则由场景 prompt 动态加载，当前场景无特殊规则时根据 Agent 描述自行判断。`

---

## 文件清单汇总

### 新建文件

```
backend/prompts/scenes/                     ← 新建目录
backend/prompts/scenes/dev_scene.md         ← 从 orchestrator.md 迁移
backend/prompts/scenes/data_scene.md        ← 从 orchestrator.md 迁移
backend/prompts/scenes/sap_localization_scene.md  ← 新写

backend/prompts/agents/sap_law_researcher.md
backend/prompts/agents/sap_abap_explorer.md
backend/prompts/agents/sap_localization_advisor.md
backend/prompts/agents/sap_solution_synthesizer.md

backend/skills/glo_document_grounding.md   ← 从 L2A 下载
backend/skills/glorepo_abap.md             ← 从 L2A 下载
backend/skills/localization_support_assistant.md  ← 从 L2A 下载（裁剪版）

backend/squads/sap_squad.json              ← 新建
```

### 修改文件

```
backend/prompts/orchestrator.md            ← 精简，删除场景专属章节
backend/squads/dev_squad.json              ← 加 scene_prompt_key
backend/squads/data_squad.json             ← 加 scene_prompt_key
backend/seeds/agents.py                    ← 追加 4 个 SAP Agent
backend/seeds/mcp_servers.py               ← 追加 3 个 L2A MCP
backend/services/orchestrator/prompt_builder.py  ← 添加 scene prompt 加载逻辑
frontend/src/components/chat/NewChatDialog.vue   ← 群聊选择 UI 优化
```

---

## 依赖关系与执行顺序

```
任务三（下载 L2A Skills）
    ↓
任务四（MCP Seed）─┐
任务五（Agent Seed）←─ 依赖任务三的 skill 文件存在
    ↓               │
任务六（Squad JSON）←─ 依赖任务五的 agent_ids
    ↓
任务一（动态 prompt 加载）←─ 依赖任务六的 scene_prompt_key 字段
    ↓
任务二（SAP scene prompt 内容）
    ↓
任务八（迁移现有 prompt）
    ↓
任务七（前端 UI 优化）   ← 可并行，不依赖上述任务
```

**推荐执行顺序**：三 → 四 → 五 → 六 → 二 → 一 → 八 → 七

---

## 验收标准

1. 启动后端，`skills` 表有 3 条 L2A skill 记录，`agents` 表有 4 条 SAP Agent 记录，`mcp_servers` 表有 3 条 L2A MCP 记录
2. 前端新建对话页面显示"SAP 本地化研究小队"选项
3. 选择 SAP 小队创建会话，发送"帮我研究越南 e-invoicing 要求"，orchestrator 的 system prompt 中包含 `sap_localization_scene.md` 的内容
4. 会话中看到 3 个 Agent 并行启动的"思考中"指示条
5. 前端新建对话页面的群聊列表支持分类展示，不再是全部平铺
