---
name: deployment_workflow
description: 部署前合规检查清单与触发条件 — 给主 Agent 决定何时调 deploy_app,给审查 Agent 兼任部署前合规审查
trigger_keywords: [部署, deploy, 上线, 跑起来]
applicable_agents: [claude, custom]
---

# 部署工作流

部署在 AgentHub 里是**主 Agent 调用 deploy_app 工具**完成的(走 ApprovalHook 用户审批),
不是某个子 Agent 干的活。这份 skill 解决两件事:

1. **主 Agent 视角**: 什么时候该调 deploy_app、传什么参数
2. **审查 Agent 视角**: 收到"准备部署"信号时,先做合规检查再放行

## 流程总览

```
用户: "做一个 Todo App"
  ↓
主 Agent dispatch → 代码 Agent 写完 app.py / requirements / 模板
  ↓
主 Agent dispatch → 审查 Agent (本 skill 部分)
  ↓ 通过
主 Agent 调 deploy_app(entry_point="app.py") → ApprovalHook → 用户审批
  ↓ approve
deploy_app 起容器 → 返回 URL
  ↓
主 Agent 把 URL 发给用户
```

---

## 审查 Agent 视角:部署前合规检查清单

收到主 Agent 派的"部署前合规审查"任务时,**逐项过这张表**。任何 ❌ 项必须修复才能放行。

### A. 入口文件

- [ ] 沙箱根目录有 `app.py` 或 `main.py`
- [ ] 入口文件里创建了 app 实例(变量名是 `app`)
- [ ] **没有** `if __name__ == "__main__"` 块自启 uvicorn (容器由 deploy_app 接管启动)
- [ ] 监听 `0.0.0.0:8000`,不是 127.0.0.1 / 其他端口

### B. 依赖

- [ ] 所有 `import` 都在 `python_runtime_environment` skill 的预装清单里
- [ ] 如果有 `requirements.txt`,里面没出现清单外的库
- [ ] **不要写** `pip install` / `subprocess` 调用

### C. 数据库

- [ ] 不连外部数据库 server (PostgreSQL / MySQL / Redis 等)
- [ ] 用 sqlite (文件落沙箱) 或纯内存,不依赖外部服务

### D. 路径与文件

- [ ] 文件读写路径用相对路径,不出现 `/etc/` / `C:\` 之类宿主机路径
- [ ] 静态资源、模板放标准位置 (`templates/` / `static/`)

### E. 端到端可启动性

- [ ] 入口文件能被 `from app import app` 直接 import (没有 import 阶段就抛错的代码)
- [ ] 没有读取沙箱外文件 (例如 `~/.aws/credentials`)

## 输出格式

```
## 部署前合规审查结果

✅ 通过 / ❌ 拒绝

### 检查项
A. 入口文件: ✅
B. 依赖: ❌ requirements.txt 含清单外的 redis==5.0
C. 数据库: ✅
D. 路径: ✅
E. 启动性: ✅

### 必修问题
- [requirements.txt:3] redis 不在预装清单。如果只是缓存场景,
  改用 sqlite 或内存 dict 即可。让代码 Agent 调整。

### 建议
通过修复 requirements.txt 后可以部署。
```

---

## 主 Agent 视角:何时调 deploy_app

主 Agent 在以下时机考虑调 deploy_app:

1. **代码 Agent 已经产出完整应用** (有 entry point + 必要文件)
2. **审查 Agent 通过部署前合规检查**
3. **用户明确要求"部署 / 跑起来 / 演示一下"**

**不要主动**部署的场景:
- 用户只让"写代码",没说要跑
- 审查 Agent 报了 ❌ 项还没修
- 代码还在中间状态(只写了一半)

## 工具调用

```
deploy_app(entry_point="app.py")
```

返回:
```json
{
  "url": "http://localhost:18888/preview/{conv_id}/",
  "status": "running" | "error",
  "logs": "..."
}
```

`status="error"` 时,把 logs 关键 5-10 行发给代码 Agent 让它修,然后让审查 Agent 重审,再调一次 deploy_app。

## 反模式

- ❌ 代码 Agent 写完直接说"已部署" (它没有 deploy_app 工具)
- ❌ 跳过审查直接部署 (高危工具应该走审查 + ApprovalHook 双层防护)
- ❌ 审查不通过强行部署 (容器内运行时崩,白浪费一次审批)
- ❌ 用户没说要部署就主动跑起来 (用户可能只想看代码)
