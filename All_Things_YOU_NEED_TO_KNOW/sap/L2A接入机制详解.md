# L2A Capability Hub 接入机制详解

> 说明 AgentHub 如何接入 L2A 的 Skill 和 MCP Server，包括具体步骤和技术路径。

---

## 一、Skill 接入

### Skill 是什么

L2A 的 skill 本质是一个 `SKILL.md` 文件，frontmatter + 正文，例如：

```markdown
---
name: glo-document-grounding
description: Answers generic SAP Globalization questions...
tools: Read, Write, mcp__spec-to-code__l2a-document-grounding
model: sonnet
---

# GLO Document Grounding
（正文内容）
```

AgentHub 自己的 `backend/skills/*.md` 格式完全对齐（都是 frontmatter + 正文 markdown），只是 L2A 的 `tools:` 字段是给 Claude Code CLI 用的，AgentHub 不需要这个字段。

### 接入步骤

**Step 1：复制 SKILL.md 内容到 AgentHub skills 目录**

从 L2A 仓库读取 skill 的 SKILL.md，去掉或保留 frontmatter（AgentHub 的 `_parse_md` 会自动处理），保存到：

```
backend/skills/glo_document_grounding.md
backend/skills/glorepo_abap.md
backend/skills/localization_support_assistant.md
```

> 注意：文件名用下划线（AgentHub 规范），L2A 用连字符。

**Step 2：`scan_builtin()` 自动入库**

服务启动时 `skill_service.scan_builtin()` 自动扫描 `backend/skills/*.md`，把内容写入 `skills` 表。无需手动操作。

**Step 3：在 `seeds/agents.py` 的 Agent 配置中指定 `default_skills`**

```python
{
    "id": "agent-sap-law-researcher",
    "default_skills": ["glo_document_grounding"],  # 对应 backend/skills/glo_document_grounding.md 的 stem
}
```

`seed_agents()` 会通过 `_seed_agent_skills()` 把 skill 关联到 agent。

### 注意事项

- L2A 的 `localization-support-assistant` SKILL.md 有 47KB，内容很长，建议**只保留 Workflow 和 Constraints 核心部分**，裁剪到合理大小
- 如果 skill 内容引用了 MCP 工具（如 `mcp__spec-to-code__*`），在 AgentHub 里这些工具需要是真实配置好的 MCP Server，否则 Agent 会尝试调用但失败
- Skill 是注入到子 Agent system_prompt 里的"背景知识"，不是可执行工具——子 Agent 用 skill 内容理解自己的职责和方法，实际调用 MCP 由 orchestrator 或 Agent 的工具权限决定

---

## 二、MCP Server 接入

### MCP Server 是什么

L2A 的 MCP server 是 HTTP 服务（OIDC 或 OAuth2 认证）。

> **敏感信息已移至**：`DO_NOT_COMMIT/sap_l2a_mcp_config.md`（已加入 .gitignore，不会提交）。
> MCP 的实际 URL、token 和 OAuth2 credentials 请查阅该文件。

### AgentHub 的 MCP 数据模型

```python
# backend/models/mcp_server.py
class MCPServer(Base):
    __tablename__ = "mcp_servers"
    
    id        # UUID
    name      # 名称
    transport # "stdio" | "sse" | "streamable_http"
    url       # HTTP 端点
    headers   # {"Authorization": "Bearer ..."}  ← 认证 token 放这里
    env       # stdio 专用环境变量
    command   # stdio 可执行文件
    args      # stdio 参数
    author_id # "GUGA" = 系统内置
    is_public / is_active
```

关联表：`agent_mcp_servers`（agent_id + mcp_server_id 多对多）

### 接入步骤

**Step 1：在 `seeds/mcp_servers.py` 的 `PRESET_MCP_SERVERS` 中添加配置**

URL 从 `DO_NOT_COMMIT/sap_l2a_mcp_config.md` 获取，token 从环境变量读取：

```python
import os

PRESET_MCP_SERVERS: list[dict] = [
    {"id": "deepwiki", ...},  # 现有的

    {
        "id": "l2a-globalization-taxonomy",
        "name": "Globalization Taxonomy",
        "description": "语义搜索国家本地化范围、S/4HANA 能力关系图谱",
        "transport": "streamable_http",
        "url": "<见 DO_NOT_COMMIT/sap_l2a_mcp_config.md>",
        "headers": {
            "Authorization": f"Bearer {os.environ.get('L2A_TAXONOMY_TOKEN', '')}"
        },
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
    {
        "id": "l2a-sap-mcp-glorepo",
        "name": "SAP GLO Repository",
        "description": "搜索 ABAP 对象、CDS 视图、DRC 报表配置",
        "transport": "streamable_http",
        "url": "<见 DO_NOT_COMMIT/sap_l2a_mcp_config.md>",
        "headers": {
            "Authorization": f"Bearer {os.environ.get('L2A_GLOREPO_TOKEN', '')}"
        },
        "author_id": "GUGA",
        "is_public": 1,
        "is_active": 1,
    },
]
```

**Step 2：在 `seed_orchestrator_mcp_links()` 中关联到 orchestrator**

现有函数已经自动把所有 `PRESET_MCP_SERVERS` 关联到 orchestrator。只要在列表里添加了配置，关联就会自动建立。

**Step 3：如果子 Agent 也需要直接调用 MCP**

需要手动添加 `AgentMCPServer` 关联：

```python
# seeds/mcp_servers.py 中增加函数
def seed_sap_agent_mcp_links(db: Session) -> int:
    links = [
        ("agent-sap-law-researcher", "l2a-globalization-taxonomy"),
        ("agent-sap-abap-explorer", "l2a-sap-mcp-glorepo"),
    ]
    # ... 同 seed_orchestrator_mcp_links 的幂等逻辑
```

### 认证方案分析

L2A 的 MCP 有两种认证，详细 URL 和 credentials 见 `DO_NOT_COMMIT/sap_l2a_mcp_config.md`：

| 认证类型 | MCP | 环境变量 |
|---|---|---|
| OIDC | `globalization-taxonomy`、`spec-to-code` | `L2A_TAXONOMY_TOKEN`、`L2A_SPEC_TO_CODE_TOKEN` |
| OAuth2 | `sap-mcp-glorepo`、`solution-patterns` | `L2A_GLOREPO_TOKEN`、`PATTERN_BLUEPRINT_TOKEN` |

**Demo 阶段方案：**

1. **OAuth2**：通过 client credentials 换取 token，放入 `backend/.env`，seed 里 `os.environ.get()` 读取
2. **OIDC**：浏览器 SSO 手动获取 token，放入 `backend/.env`，Demo 时使用
3. **Mock 方案**：认证不可用时，在 orchestrator prompt 里直接粘贴预置的 taxonomy 数据作背景

---

## 三、与现有接入流程的对比

| 类别 | 现有（通用内置）| L2A 接入 |
|---|---|---|
| **Skill** | `backend/skills/*.md` → `scan_builtin()` 入库 → `seeds/agents.py` 里 `default_skills` 关联 | **完全一样**，只是多了一步"先从 L2A 仓库复制 SKILL.md 内容" |
| **MCP Server** | `seeds/mcp_servers.py` 的 `PRESET_MCP_SERVERS` → `seed_mcp_servers()` 入库 → `seed_orchestrator_mcp_links()` 关联 | **完全一样**，多了认证配置（headers 里填 token 或 OAuth2 credentials）|
| **认证** | 现有 MCP（DeepWiki）无需认证 | L2A MCP 需要 OIDC 或 OAuth2，Demo 阶段手动填 token |

---

## 四、需要进一步讨论的问题

1. **子 Agent 是否需要直接调用 MCP？**
   - 当前 AgentHub 架构：子 Agent 无工具权限，orchestrator 调 MCP 再把结果粘贴给子 Agent
   - 这个架构对 SAP Demo 场景是够用的——orchestrator 调 globalization-taxonomy，再派给调研 Agent
   - 如果需要子 Agent 直接调 MCP，需要修改 Adapter 层（Claude Adapter 支持传入 tools 列表）

3. **SKILL.md 内容裁剪标准？**
   - `localization-support-assistant` 有 47KB，全量注入会占大量 context
   - 建议只保留"Workflow"、"Constraints"、"Output Format"三个核心章节

# 传递方式

Skill — 直接拼进内容传给 CLI

StreamInput.system_prompt 在 thread_service 里已经把运行时 header + agent 基础 prompt 组合好了。Skill 的内容由上层（_build_system_prompt，line 292）以 \n---\n 分隔追加进去，整体通过 --append-system-prompt 参数传给 CLI。就是纯文本直接贴进去，没有任何"工具调用"机制。

MCP — 是的，现在是配置驱动，不是代码接入

好消息是：不需要为每个 MCP 手动写接入代码。流程是：

用户/管理员在 AgentHub 界面配置一个 MCP Server（填写 command/url/transport 等）
存入数据库 mcp_servers 表 + agent_mcp_servers 关联表
AdapterRegistry._build_adapter() 启动时从数据库读出，转成 MCPServerConfig
_write_mcp_config() 把所有配置写入一个临时 JSON 文件
调用 Claude CLI 时带上 --mcp-config <tempfile> --allowedTools mcp__*
Claude CLI 自己负责连接这些 MCP Server，自己管理工具调用
所以对于 ClaudeAdapter 来说，MCP 完全是配置文件的事，项目代码只负责把数据库里的配置序列化成 Claude CLI 认识的 JSON 格式（支持 stdio、sse、http 三种 transport），工具的注册、调用、结果解析全部由 Claude CLI 内部处理，结果只以文本形式出现在 stream-json 的 assistant 事件里回传给后端。

这和 CustomAdapter 形成了明显对比——Custom 需要自己 list_tools() 再 call_tool()，Claude 把这层完全外包给了 CLI。
