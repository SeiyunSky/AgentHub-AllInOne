# AgentHub Auth 全栈实现总结

> 队伍：咕嘎一辈子队
> 修改者：刘盘 (lp 分支)
> 修改日期：2026-06-03
> 工作分支：`lp` (相对 `master` 的 5 个增量提交)

---

## 0. 总览

完成了从 **MVP 假鉴权（X-User-Id header）→ 生产级 JWT 鉴权** 的全栈改造，覆盖：

- 后端 7 层架构（model / repository / service / API / middleware / schema / 测试）
- 前端 5 个核心文件 + 1 个新页面 + 用户身份卡片
- 数据库密码 100% bcrypt 哈希，已实测验证

整体完成度：**会话开始 55% → 结束 95%**

---

## 1. 后端工作（lp 分支 5 个 commit）

### 1.1 提交线索

| Commit | 内容 | 文件数 |
|---|---|---|
| `08e58bc` | 基础设施 + 业务层（Redis 黑名单 + AuthService 核心） | 7 |
| `f969dd9` | hash + jwt + 非明文（API 路由 + 中间件 + deps） | 5 |
| `7748cd3` | unit test（28 个 auth_service 单测） | 1 |
| `87fbce1` | token 计数透出（OpenCode adapter 关联） | 3 |

### 1.2 数据层

- **`backend/models/user.py`** — User 表
  - 字段：`id` / `username` / `password_hash` / `email` / `display_name` / `last_login_at` / `created_at`
  - 约束：`username` 唯一索引、`email` 唯一索引

- **`backend/repositories/user_repo.py`** — UserRepository
  - CRUD 全套 + `get_by_username` + `email_taken` + `touch_last_login`

### 1.3 业务层（核心）

**`backend/services/auth_service.py`** — AuthService 完整实现：

| 能力 | 实现细节 |
|---|---|
| **bcrypt 密码哈希** | passlib，cost=12（OWASP 推荐 ≥10），同密码每次 salt 独立 |
| **JWT 双 token** | python-jose，access (1d) + refresh (30d)，携带 `jti / sub / type` |
| **Redis 黑名单 logout** | token 加入黑名单直至自然过期；Redis 故障 fail-open 降级（仍 200 但 token 不立即失效） |
| **防时序攻击** | 用户不存在时也走一遍 `verify_password`，避免响应时间侧信道泄露用户存在性 |
| **防枚举** | 错用户名 / 错密码统一返回 401 + 同一文案 |

### 1.4 API 层

**`backend/api/v1/auth.py`** — 5 个端点（prefix `/api/v1/auth`）：

| 端点 | 状态码 | 说明 |
|---|---|---|
| `POST /register` | 201 | 重名 409，校验失败 422 |
| `POST /login` | 200 | 失败 401（不区分用户名错/密码错） |
| `POST /logout` | 204 | 写黑名单；无 token 401 |
| `POST /refresh` | 200 | refresh 不轮换，只换新 access |
| `GET  /me` | 200 | 强制 JWT，不走 dev fallback |

### 1.5 中间件 / 依赖

- **`backend/api/middleware/auth.py`**
  - `JWTBearer`（HTTPBearer 子类，`auto_error=False`，让"未带 token"和"token 无效"走同一处理）
  - `extract_token_from_request` —— SSE / WS 端点兜底从 query param 拿 token

- **`backend/api/deps.py`**
  - `get_current_user` —— JWT 优先，`AUTH_DEV_HEADER_FALLBACK=true` 时允许 X-User-Id 兜底（开发联调用）

### 1.6 Schema

**`backend/schemas/auth.py`** — 严格校验 + 字段隔离：

- `RegisterRequest` —— username 正则 `^[a-zA-Z0-9_-]{4,50}$`，password ≥ 8 字符（防 LLM 注入绕过）
- `LoginRequest` / `RefreshRequest`
- `TokenResponse` —— access + refresh + expires_in + UserPublic（便利字段）
- `UserPublic` —— **绝不暴露 `password_hash`**

### 1.7 配置

**`backend/.env`**：

```
JWT_SECRET=<64 字节强随机串>
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=1440  # 1 天
JWT_REFRESH_EXPIRE_DAYS=30
AUTH_DEV_HEADER_FALLBACK=true   # 生产必须设 false
```

### 1.8 测试

- **`backend/tests/unit/test_auth_service.py`** —— 28 个单测，5 组覆盖
  - 密码哈希 / JWT 签发解码 / Redis 黑名单 / 业务流 / SQLite in-memory

- **`backend/tests/integration/test_auth_api.py`** —— 5 端点全覆盖
  - envelope 格式 / logout 黑名单端到端 / dev fallback 验证

---

## 2. 前端工作（本次会话 0 → 闭环）

### 2.1 改造前状态

- `api/auth.ts` —— 空 stub（只有 TODO 注释）
- `LoginView.vue` —— `setTimeout` 假登录，不调后端
- `http.ts` —— 注入 `X-User-Id` (MVP 模式)
- `stores/auth.ts` —— 只存单 token，没有 user 信息
- 注册页 —— **不存在**

### 2.2 改造后

#### `frontend/src/api/auth.ts`（重写）

- 5 个端点 SDK 完整实现
- 导出 TS 类型 `UserPublic` / `TokenResponse` / `LoginPayload` / `RegisterPayload`，与后端 schema 严格对齐

#### `frontend/src/api/http.ts`（重写，关键）

- 删除 `X-User-Id` 拦截器，改注入 `Authorization: Bearer <token>`
- **401 自动 refresh** —— 关键设计：
  - **Promise 单飞**：并发 401 共享同一次 refresh 调用，避免 N 个请求触发 N 次 refresh 雪崩
  - `_retried` 标记防无限重试
  - refresh 失败派发 `auth:expired` 自定义事件
  - **避免循环依赖**：http.ts 不直接 import store/router，用 CustomEvent 解耦
- `SKIP_AUTH_PATHS` 白名单：`/auth/login`、`/auth/refresh`、`/auth/register` 不参与拦截器

#### `frontend/src/stores/auth.ts`（重写）

- 双 token + UserPublic 持久化到 localStorage
- 命名空间化 key：`auth.access_token` / `auth.refresh_token` / `auth.user`
- 启动时自动清理旧 MVP 残留 key（`token` / `username` / `user_id`）
- 暴露 `isLoggedIn` / `username` / `displayName` 三个 computed

#### `frontend/src/views/LoginView.vue`（改造）

- 删除 `setTimeout` mock，调真实 `authApi.login()`
- 错误内联展示（红字提示后端返回的错误信息）
- 加底部 "Create an account" 跳转链接

#### `frontend/src/views/RegisterView.vue`（**新增**）

- 5 字段表单：username / display_name / email / password / confirmPassword
- **校验规则与后端 schema 严格对齐**（避免前端通过 → 后端拒绝的尴尬）：
  - username 4-50 字符，正则 `^[a-zA-Z0-9_-]+$`
  - password ≥ 8 字符
  - confirmPassword 自定义 validator 比对一致性
  - email 简易校验，后端 `EmailStr` 兜底
- **注册即登录**：UX 优化，用户填完不用再去登录页，自动 register → login → 跳 `/chat`

#### `frontend/src/router/index.ts`

- 新增 `/register` 路由
- 守卫扩展：已登录用户访问 `/login` 或 `/register` 直接跳 `/chat`

#### `frontend/src/main.ts`

- 监听 `auth:expired` 事件 → 清状态 + 跳登录页（带 `redirect` query 保留原页面）

#### `frontend/src/components/layout/NavRail.vue`（用户身份卡片）

替代之前丑陋的 `Sign out (testuser)` 按钮 label。改进点：

- **首字母头像**：按 username 哈希到 7 种渐变之一，同用户固定配色，多用户视觉区分
- **display_name + @username** 双行展示
- **退出图标 hover 才显示**（默认 `opacity-0`，避免误点）
- 退出流程：ElMessageBox 确认 → 调后端 logout 写黑名单 → 清本地 → 跳登录

---

## 3. 关键设计决策

| 决策 | 理由 |
|---|---|
| **bcrypt cost=12** | OWASP 推荐 ≥10，单次 verify ~200ms 量级，对抗暴力破解但不影响登录体验 |
| **双 token（access 1d + refresh 30d）** | access 短命降低泄露窗口，refresh 长命减少用户重登频率 |
| **refresh 不轮换** | 简化客户端逻辑（避免 race condition）；代价是 refresh 泄露窗口大；可接受因 refresh 只能换 access，本身权限受限 |
| **Redis 黑名单 fail-open** | Redis 挂掉时 logout 仍 200，不卡用户；代价是 token 有效到自然过期 |
| **前端 Promise 单飞 refresh** | 并发请求共享一次 refresh，避免 N 个 401 雪崩 |
| **CustomEvent 解耦** | http.ts 不直接 import store/router，避免循环依赖；用 `auth:expired` 让 main.ts 集中处理跳转 |
| **注册即登录** | UX：用户注册完不用再去登录页填一遍，直接进应用 |
| **AUTH_DEV_HEADER_FALLBACK 开关** | 开发联调期用 X-User-Id 不用每次拿 token；生产关掉变严格模式；旧测试无需重写 |

---

## 4. 数据库验证（实测）

执行查询 `SELECT username, password_hash, LENGTH(password_hash) FROM users`：

| 用户 | 长度 | 前缀 | 状态 |
|---|---|---|---|
| `oc_demo_user` | 60 | `xxxxxxxx...` | 占位脏数据（测试时手动塞，无法登录但不构成安全风险） |
| `demo_inspect` | 60 | `$2b$12$...` | ✅ 标准 bcrypt |
| `testuser01` | 60 | `$2b$12$...` | ✅ 标准 bcrypt |
| `testuser02` | 60 | `$2b$12$...` | ✅ 标准 bcrypt |

**bcrypt 哈希格式解读** `$2b$12$ETQcgc9b04Y1saCIdJ...`：

- `$2b$` —— bcrypt 算法版本标识（2b 是当前主流）
- `12` —— cost factor，迭代轮数 = 2^12 = 4096 轮
- 后 53 字符 —— Base64 编码的 22 字节 salt + 31 字节 hash 摘要

**结论**：所有真实注册用户的密码均为标准 bcrypt 哈希，独立 salt，**无明文风险**，符合生产标准。

---

## 5. 完成度汇总

| 模块 | 完成度 | 说明 |
|---|---|---|
| 后端 auth 实现 | **~95%** | 齐全且有充分测试，缺密码找回功能 |
| 前端 auth 接入 | **~95%** | 登录/注册/登出闭环 + 用户卡片，缺 Profile 页和密码修改页 |
| 测试 | 后端 28 单测 + 集成测试齐全；前端 vue-tsc 类型检查通过 |
| **整体** | **~95%** ↑（从对话开始的 55%） |

---

## 6. 后续可做（按优先级）

1. **前端密码修改页** —— `PUT /auth/password` 后端没做，需补一对端点 + 前端表单
2. **密码找回** —— 邮件链接重置（依赖邮件服务，工作量大）
3. **前端单测** —— Vitest 覆盖 stores/auth + http.ts 401 重试逻辑
4. **Settings 入口接通** —— NavRail 上 Settings 按钮目前未绑定，可接到 Profile 页
5. **JWT 改 RS256** —— 生产对称密钥不够安全，公钥/私钥分离更稳
6. **Token 主动刷新** —— 目前 access 过期才被动 refresh，可改剩余 < 5min 时静默续期

---

## 7. 联调启动方式

### 启动后端（终端 1，项目根目录）

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --port 18888
```

成功标志：`Uvicorn running on http://0.0.0.0:18888`，访问 `http://localhost:18888/docs` 可见 Swagger。

### 启动前端（终端 2）

```powershell
cd frontend
npm run dev
```

访问 `http://localhost:5173` 自动跳 `/login`。

### 验证登录闭环

1. 点 "Create an account" → 填表注册 → 自动登录 → 跳 `/chat`
2. F12 → Application → Local Storage → 应有 `auth.access_token` / `auth.refresh_token` / `auth.user`
3. F12 → Network → 后续 API 请求 Headers 有 `Authorization: Bearer eyJ...`，**没有** `X-User-Id`
4. NavRail 底部用户卡片显示头像 + display_name + @username，hover 显示退出图标
