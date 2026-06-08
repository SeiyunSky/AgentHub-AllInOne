---
name: 需求至部署WEB的SOP
category: 规则设定
description: 从需求到部署的标准 web 应用开发 SOP。Coder / Architect / Reviewer 在 dev 群组协作时遵守这个流程。
trigger_keywords: [开发, 实现, 写应用, 做一个, app]
applicable_agents: [claude, custom]
---

# Web 应用开发标准工作流

dev 群组接到"做一个 XXX 应用"需求时按这个流程协作。**主 Agent 派活时严格按这五步**,不要跳步。

## Step 1: 需求拆解(产品经理 / 主 Agent)

把一句话需求拆成可验证的功能点。每个功能点回答:
- 用户做什么动作?(input)
- 系统应该怎么响应?(output)
- 怎么知道这个功能跑通了?(验收)

输出形态:简短的功能列表(不写完整 PRD,demo 阶段过度文档化)

示例:
```
做 Todo App
→ 功能 1: 添加 todo (POST /todos {text} → 返回新 todo)
→ 功能 2: 列出所有 todo (GET /todos → 数组)
→ 功能 3: 删除 todo (DELETE /todos/{id} → 204)
→ 功能 4: 简单 HTML 前端能执行上述操作
验收: 浏览器打开能 add / list / delete 三件事
```

## Step 2: 技术架构(架构师 / 代码 Agent 兼)

dev 群组规模小,不强制分 Architect 独立 Agent。代码 Agent 自己判断用什么技术栈。

**默认技术栈(无特殊需求时直接用,不要每次都问)**:

| 组件 | 选型 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 异步、自动 OpenAPI、与 AgentHub 后端一致 |
| 数据存储 | sqlite + sqlalchemy | 零配置、文件级、足够 demo |
| 前端 | HTML + 原生 JS + fetch | 不用打包,直接 serve |
| 模板 | Jinja2 | FastAPI 集成成熟 |
| 样式 | 内联 CSS 或 CDN Tailwind | 不用 npm |

**非默认场景才考虑改**:用户明确说"不要 sqlite"、"我要 React"等。

## Step 3: 文件骨架(代码 Agent)

按下面的标准目录结构创建文件:

```
sandbox/{conv_id}/
├── app.py                # FastAPI 入口
├── models.py             # SQLAlchemy ORM(可选,简单时合并到 app.py)
├── templates/
│   └── index.html        # 主页
└── static/
    └── style.css         # (可选)
```

**不要**:
- 不加 `__init__.py`(平铺更简单)
- 不分 `routers/` / `services/` / `repositories/`(单文件足够 demo,过度分层)
- 不加 `tests/`(部署验证就够了)

### 前端路径规则(部署必须遵守)

AgentHub 把应用挂在 `/preview/{conv_id}/` 子路径下。前端所有 fetch 和资源引用**不能用 `/` 开头的绝对路径**,否则浏览器把请求发到 AgentHub 后端,容器永远收不到:

```javascript
// ❌ 错误 — 绝对路径
fetch('/api/calculate', ...)
fetch('/todos', ...)

// ✅ 正确 — 相对路径
fetch('api/calculate', ...)
fetch('todos', ...)
```

```html
<!-- ❌ 错误 -->
<script src="/static/main.js"></script>
<link rel="stylesheet" href="/static/style.css">

<!-- ✅ 正确 -->
<script src="static/main.js"></script>
<link rel="stylesheet" href="static/style.css">
```

**规则**:写前端代码时,所有 `fetch()`、`<script src>`、`<link href>`、`<img src>` 的路径一律去掉开头的 `/`。

## Step 4: 实现(代码 Agent)

按功能点逐个实现,每个功能 1-2 个 endpoint:
- 先写 model(数据形态)
- 再写 endpoint(handler 逻辑)
- 顺手加最简单的 HTML/JS(用 fetch 调 API)

**不要为不存在的需求做架构准备**。例如用户没说"要支持多用户",就别加 user_id 字段。

## Step 5: 部署 + 验证

代码 Agent 写完所有文件后,**回报主 Agent 部署条件已就绪**。
具体部署流程见 `deployment_workflow` skill,核心是:

1. 主 Agent 派审查 Agent 做部署前合规检查
2. 审查通过 → 主 Agent 调 `deploy_app` 工具(走 ApprovalHook 用户审批)
3. 拿到 URL 回报给用户

部署失败时,主 Agent 把关键 log 转给代码 Agent 修,改完重审重部署。

## 协作时序

```
用户消息 ────→ 主 Agent
                │
                ├─ 派 Coder: "做 Todo App,后端 FastAPI 前端 HTML"
                │   ↑ Coder 走 Step 1-4,产出文件
                │
                ├─ 派 Reviewer: "做部署前合规审查"
                │   ↑ Reviewer 用 deployment_workflow skill 过 checklist
                │
                └─ 调 deploy_app 工具 (主 Agent 自己调,走 ApprovalHook)
                    ↑ 用户审批 → 容器起来 → 返回 URL

用户 ←──── 主 Agent 汇总: "应用已部署,URL: ..."
```

## 反模式(不要这么做)

- ❌ 代码 Agent 写完说"已部署"(子 Agent 没有 deploy_app 工具)
- ❌ 跳过审查直接 deploy_app(高危工具应走双层防护:审查 + ApprovalHook)
- ❌ 用户没要部署主动跑起来(用户可能只想看代码)
- ❌ 一开始就规划"v2 时怎么扩展"(YAGNI,见 software_engineering_principles)
- ❌ 写 README.md / 设计文档(demo 阶段过度文档化,代码本身和部署 URL 就是产物)
