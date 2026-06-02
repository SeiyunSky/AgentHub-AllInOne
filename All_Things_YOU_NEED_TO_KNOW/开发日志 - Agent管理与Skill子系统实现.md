# AgentHub 开发日志 — Agent 管理与 Skill 子系统实现

**最后更新：** 2026-05-29
**分支：** `dev/musuyin/codex`
**涉及文件：** `api/v1/agents.py`、`api/v1/skills.py`、`services/agent_builder_service.py`、`services/skill_service.py`、`repositories/agent_repo.py`、`repositories/skill_repo.py`

---

## 背景

对应开发进度文档中的**模块四（Agent 管理全栈）**和**模块五（Skill 子系统）**，本阶段完成：

1. **Agent CRUD API**：标准增删改查 + 启停端点
2. **对话式 Agent 创建**：LLM 辅助生成草稿 → 用户确认 → 落库（两步流程）
3. **Skill CRUD API**：元数据写 DB + 正文写文件
4. **SkillService**：内置 Skill 扫描、运行时注入、orchestrator 接口
5. **SkillRepository**：agent_skills 多对多关系管理

---

## 模块四：Agent 管理全栈

### `api/v1/agents.py` — 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/agents` | 列表（当前用户可见） |
| `POST` | `/agents` | 创建 |
| `GET` | `/agents/{id}` | 详情 |
| `PATCH` | `/agents/{id}` | 更新 |
| `DELETE` | `/agents/{id}` | 删除 |
| `POST` | `/agents/{id}/activate` | 启用 |
| `POST` | `/agents/{id}/deactivate` | 停用 |
| `POST` | `/agents/build` | LLM 辅助生成草稿（返回 session_id + draft） |
| `POST` | `/agents/build/confirm` | 用户确认草稿后落库 |

**注意路由注册顺序**：`/agents/build` 和 `/agents/build/confirm` 必须在 `/agents/{agent_id}` 系列之前注册，否则 FastAPI 会把 `"build"` 当 path param 匹配，导致 404。

#### 响应辅助函数 `_to_response`

```python
def _to_response(agent, skill_repo: SkillRepository) -> AgentResponse:
    resp = AgentResponse.model_validate(agent)
    resp.skill_ids = skill_repo.list_skill_ids_for_agent(agent.id)
    return resp
```

每次响应都附带 `skill_ids` 列表（从 agent_skills 关联表查）。

#### capabilities 字段处理

创建和更新时，`capabilities` 字段需手动序列化为 `dict` 才能写入 DB JSON 列：

```python
if "capabilities" in fields and fields["capabilities"] is not None:
    fields["capabilities"] = fields["capabilities"].model_dump()
```

#### 鉴权占位

当前用固定 `_DEMO_USER_ID = "GUGA"` 占位，auth 模块（模块三）完成后替换为 JWT 中取的 `current_user`。

---

### `services/agent_builder_service.py` — 对话式创建流程

#### 整体流程

```
POST /agents/build
  └─ AgentBuilderService.build(user_id, description)
       ├─ 调 OrchestratorLLMClient.chat_completion(系统 prompt + 用户描述)
       │     → LLM 返回 JSON（name/description/type/system_prompt/capabilities/tags/suggested_skill_names）
       ├─ _parse_draft(raw_text) → AgentBuildDraft
       ├─ session_id = gen_uuid()
       └─ _store_put(user_id, session_id, draft) → 内存暂存，TTL 1小时
       返回 (session_id, draft)

POST /agents/build/confirm
  └─ AgentBuilderService.confirm(user_id, session_id, edited_draft)
       ├─ _store_get(user_id, session_id) → 校验 session 有效性（防伪造 / TTL 过期）
       ├─ suggested_skill_names → skill_id（查不到抛 LookupError → 422）
       ├─ AgentRepository.create(...)
       ├─ SkillRepository.sync_agent_skills(agent.id, skill_ids)
       └─ _store_delete(user_id, session_id)
       返回 Agent ORM 对象
```

#### LLM System Prompt

```
你是 AgentHub 的 Agent 设计助手。用户用自然语言描述需要的 Agent，
你输出 JSON：name / description / type / system_prompt / capabilities / tags / suggested_skill_names
只输出 JSON，不要有任何解释文字。
```

使用 `response_format={"type":"json_object"}` 强制 JSON 输出（OpenAI-compatible）。

#### 草稿存储设计（Redis 兼容接口）

| | 当前实现 | 生产替换 |
|-|---------|---------|
| 存储 | 进程内字典 `_draft_store` | `redis.setex(key, 3600, json)` |
| 锁 | `threading.Lock` | 不需要（Redis 原子操作） |
| 过期 | 主动 evict（写入时触发） | Redis TTL 自动过期 |
| 接口 | `_store_put / _store_get / _store_delete` | 签名不变，只换实现 |

Key 格式：`agent_draft:{user_id}:{session_id}`，自带归属校验。

#### `_parse_draft()` — LLM 输出容错

兼容两种格式：纯 JSON + Markdown 代码块包裹的 JSON（\`\`\`json ... \`\`\`）。

额外容错：
- `type` 字段非法值（如 `"claude-3"`）→ 自动归为 `"claude"`
- `capabilities` 字段漏字段 → 用 `False` 兜底，不报错

---

### `repositories/agent_repo.py` — AgentRepository

继承 `BaseRepository[Agent]`，补充业务专有方法：

| 方法 | 说明 |
|------|------|
| `list_visible_for_user(user_id)` | 自己创建的 + 公开的，默认过滤 `is_active=0` |
| `list_by_ids(ids)` | 批量按 ID 查，返回顺序不保证 |
| `set_active(id, bool)` | 启用 / 停用，只 flush 不 commit |
| `set_public(id, bool)` | 切换可见性，只 flush 不 commit |

可见性规则：`WHERE is_active=1 AND (user_id=:me OR is_public=1)`

---

## 模块五：Skill 子系统

### `services/skill_service.py` — SkillService

#### 文件路径约定

| Skill 类型 | 文件路径 |
|-----------|---------|
| 内置 Skill（`author_id="GUGA"`） | `backend/skills/{name}.md` |
| 用户 Skill | `backend/skills/user_{author_id}/{name}.md` |

#### `scan_builtin()` — 启动时扫描

```
FastAPI lifespan 启动
  └─ SkillService(db).scan_builtin()
       ├─ glob backend/skills/*.md
       ├─ 解析 frontmatter（name / display_name / description / category）
       │     文件正文不入库，只记 file_path
       ├─ 不存在 → INSERT
       ├─ 存在但 description 为空 → UPDATE description
       └─ 存在且 description 非空 → SKIP（幂等）
       返回实际影响行数
```

frontmatter 格式：
```yaml
---
name: code_review
display_name: 代码审查
description: 提供系统化的代码审查指导
category: engineering
---
（正文内容，不入库，运行时按需读取）
```

#### `list_with_content_for_agent(agent_id)` — 子 Thread 运行时注入

```python
# thread_service._run_thread 调用
agent_skills = SkillService(own_session).list_with_content_for_agent(agent_id)
# 1. 查 agent_skills 关联表，找 Agent 挂载了哪些 Skill
# 2. 按 skill.file_path 读取文件正文
# 3. 返回 list[SkillWithContent]（含 content 字段）
```

读取正文时，`_parse_md(path)` 剥掉 frontmatter，只返回 body。文件不存在时 body="" + 记 warning 日志，不抛异常。

#### `list_for_orchestrator(user_id)` — Prompt Builder Layer 3

```python
def list_for_orchestrator(self, user_id: str) -> list[SkillSummary]:
    skills = self._repo.list_visible_for_user(user_id)
    return [SkillSummary.model_validate(s) for s in skills]
```

返回精简信息（不含正文），供 `prompt_builder._layer_3` 塞进主 Agent system prompt。

#### 用户 Skill CRUD 双写机制

**创建**：
1. 计算文件路径，`mkdir -p` 确保目录存在
2. 写文件（正文）
3. INSERT skills 表（元数据）

**更新**：
1. 校验 `author_id` 归属（他人的 Skill 不可改）
2. 更新 DB 元数据字段
3. 如果 `content` 字段有值，覆写文件

**删除**：
- 只删 DB 记录，文件留存（防止意外丢失，可从 DB 重新生成路径回溯）

---

### `repositories/skill_repo.py` — SkillRepository

继承 `BaseRepository[Skill]`，重点在 **agent_skills 多对多关系管理**：

| 方法 | 说明 |
|------|------|
| `list_visible_for_user(user_id)` | 自己创建的 + 公开的，按 name 升序 |
| `list_builtin()` | `author_id='GUGA'` 的内置 Skill |
| `get_by_name(name, author_id)` | 按 `(author_id, name)` 唯一键查找 |
| `list_skills_for_agent(agent_id)` | JOIN agent_skills，返回 Skill 列表 |
| `list_skill_ids_for_agent(agent_id)` | 只返回 skill_id 列表（AgentResponse 用） |
| `attach_skill(agent_id, skill_id)` | 已存在则 no-op |
| `detach_skill(agent_id, skill_id)` | 不存在则 no-op |
| `sync_agent_skills(agent_id, skill_ids)` | **增量 diff 替换**：新增 + 删除多余 |

#### `sync_agent_skills` 增量 diff 实现

```python
def sync_agent_skills(self, agent_id: str, skill_ids: list[str]) -> None:
    current = set(self.list_skill_ids_for_agent(agent_id))
    target = set(skill_ids)
    for sid in target - current:   # 新增
        self.attach_skill(agent_id, sid)
    for sid in current - target:   # 删除多余
        self.detach_skill(agent_id, sid)
```

每次 PATCH agent（更新 `skill_ids` 字段）时调用，保证关联表与传入列表一致。

---

### `api/v1/skills.py` — Skills API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/skills` | 列表（不含正文） |
| `POST` | `/skills` | 创建（双写：DB + 文件） |
| `GET` | `/skills/{id}` | 详情（含正文） |
| `PATCH` | `/skills/{id}` | 更新 |
| `DELETE` | `/skills/{id}` | 删除 |

`POST /skills` 有重名校验：按 `(name, author_id)` 查重，重复返回 409。

---

## 全链路数据流

### Agent 创建（对话式）

```
用户描述 → POST /agents/build
  └─ LLM → JSON → AgentBuildDraft
       └─ 暂存内存（session_id，TTL 1h）
            └─ 返回给前端（展示/编辑）

用户确认 → POST /agents/build/confirm
  └─ 校验 session_id
       ├─ skill names → skill_ids（422 如找不到）
       ├─ INSERT agents 表
       ├─ sync_agent_skills（INSERT agent_skills）
       └─ 删草稿 → 返回 AgentResponse
```

### Skill 注入链路（子 Thread）

```
FastAPI 启动
  └─ scan_builtin() → skills 表同步内置 Skill 元数据

chat 请求 → thread_service._run_thread(thread)
  └─ SkillService.list_with_content_for_agent(agent_id)
       ├─ agent_skills 表查该 Agent 挂载的 Skill IDs
       ├─ 按 file_path 读各 .md 文件正文
       └─ 返回 list[SkillWithContent]

构造 StreamInput
  └─ skills=agent_skills
       └─ ClaudeAdapter._build_system_prompt(system_prompt, skills)
            └─ 合并为单字符串 → --append-system-prompt 传 CLI
```

> **遗留问题**：`ClaudeAdapter.stream()` 当前只用 `inp.system_prompt`，未调用 `_build_system_prompt` 将 skills 合并进去。`_build_system_prompt` 函数已实现但未接入，skills 字段有值但对 ClaudeAdapter 暂时无效（P1 优先级）。

---

## 遗留 TODO

| 优先级 | 位置 | 内容 |
|--------|------|------|
| P0 | `api/v1/agents.py` | 接入 Auth 中间件，`_DEMO_USER_ID` 换为 JWT current_user |
| P0 | `api/v1/skills.py` | 同上 |
| P1 | `adapters/claude.py` | `stream()` 改为调 `_build_system_prompt`，将 skills 合并进 system prompt |
| P1 | `agent_builder_service.py` | 草稿存储换 Redis（上线前） |
| P1 | `seeds/agents.py` | `agent_id='orchestrator'` 行入库，prompt_builder layer 3 才能查它的 skill |
| P2 | `api/v1/agents.py` | `agent_builder_service` 的 LLM client 换成 ClaudeAdapter（去掉对 OrchestratorLLMClient 的额外依赖） |
| P2 | `skill_service.delete` | 删除时同步删文件（当前只删 DB，文件留存） |

---

## 验证结果

```
$ PYTHONPATH=. DB_URL=sqlite:///./test.db .venv/bin/pytest backend/tests/unit/ -v
======================== 70 passed, 1 warning ========================
```

Agents / Skills API 端点通过手动测试（FastAPI `/docs` Swagger UI）。集成测试待补充（模块零 mock_adapter fixture 就绪后）。
