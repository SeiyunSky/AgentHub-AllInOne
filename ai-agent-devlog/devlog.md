# AgentHub Dev Log

---

## Session 001 — 2026-06-08

### 任务背景
在已有的 JWT 本地登录体系基础上，新增微软账号（Azure AD）OAuth2 登录选项。
允许任意微软账号登录（tenant_id = common）。

### 技术方案
Authorization Code Flow（不用 MSAL，用 httpx 直接对接 Azure AD 端点）。
OAuth state 存 Redis（TTL 5min）防 CSRF；Redis 不可用时 fail-open + 警告日志。

### 已采取的行动

**后端（6处改动）：**

1. `backend/models/user.py`
   - `password_hash` 由 `nullable=False` 改为 `nullable=True`（OAuth 用户无本地密码）
   - 新增字段：`oauth_provider`、`oauth_subject`、`oauth_tenant_id`

2. `backend/migrations/versions/642b2725e844_add_oauth_fields_to_users.py`
   - Alembic autogenerate migration，已运行 `alembic upgrade head`，数据库已变更

3. `backend/repositories/user_repo.py`
   - 新增 `get_by_oauth(provider, subject)` 方法
   - 新增 `create_oauth_user(...)` 方法（无密码注册）
   - `create_user` 重命名注释（本地密码专用）

4. `backend/config.py`
   - 新增配置字段：`AZURE_CLIENT_ID`、`AZURE_CLIENT_SECRET`、`AZURE_TENANT_ID`（默认 common）、`AZURE_REDIRECT_URI`、`AZURE_OAUTH_STATE_TTL`

5. `backend/services/auth_service.py`
   - 新增 `AuthService.login_or_register_oauth()` 方法
     - 查找顺序：(provider, subject) → email 合并 → 自动注册
     - `_generate_username()` 辅助方法：从 email 生成合法 username，冲突加随机后缀

6. `backend/api/v1/auth.py`
   - 新增 `GET /auth/oauth/microsoft` — 生成授权 URL，state 写 Redis
   - 新增 `GET /auth/oauth/microsoft/callback` — 接收 code，换微软 token，调 Graph API 拿用户信息，login_or_register_oauth，重定向前端携带 JWT

**前端（4处改动）：**

7. `frontend/src/api/auth.ts`
   - 新增 `getMicrosoftOAuthUrl()` 方法

8. `frontend/src/api/http.ts`
   - `SKIP_AUTH_PATHS` 新增 `/auth/oauth/`

9. `frontend/src/views/MicrosoftCallbackView.vue`（新文件）
   - 接收后端 redirect 的 URL 参数（access_token、refresh_token 等）
   - 构造 TokenResponse → `authStore.setSession()` → 跳 /chat

10. `frontend/src/views/LoginView.vue`
    - 新增分割线 + "Sign in with Microsoft" 按钮
    - 新增 `handleMicrosoftLogin()` 调 `getMicrosoftOAuthUrl()` 后 `window.location.href` 跳转

11. `frontend/src/router/index.ts`
    - 新增路由 `/auth/microsoft/callback` → `MicrosoftCallbackView`

12. `backend/.env.example`
    - 新增第十三节 Microsoft OAuth2 配置说明及 Azure 门户操作步骤

### 关键设计决策
- OAuth state 存 Redis：Redis 不可用时 fail-open（安全降级而非阻断服务）
- 账号合并策略：先按 oauth_subject 精确匹配，其次按 email 合并，避免孤立账号
- 回调以 HTTP 302 重定向携带 JWT（非 POST JSON），原因：浏览器从微软跳回，只有 GET
- 前端 callback view 收到 JWT 后补调 /me 获取完整 user 对象（TODO，当前用 username 占位）

### 已知局限 / 后续可做
- [ ] MicrosoftCallbackView 收到 token 后可调 /me 补全 user.id 等字段
- [ ] UserPublic.id 在 OAuth 登录后首次为空串，刷新后正常（/me 走 JWT 能补全）
- [ ] 生产环境建议把 JWT 从 URL query 改为短命 code（避免 token 出现在浏览器历史）
- [ ] 可支持将微软账号绑定到现有本地账号（Settings 页面）

### 下一步计划
- 在 Azure 门户注册应用，填入 .env 配置，进行联调测试
