"""
全局配置 —— 从 .env 加载

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """全局配置,字段名对齐 .env 的环境变量名(大小写不敏感)。"""

    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 数据库 ----
    DB_URL: str = Field(description="SQLAlchemy 数据库连接串")

    # ---- 记忆根目录 ----
    MEMORY_ROOT: Path = Field(
        default=_BACKEND_ROOT / "runtime" / "memory",
        description="长期记忆文件根目录",
    )

    # ---- 主 Agent (Orchestrator) LLM(Anthropic 兼容协议)----
    EXTERNAL_API_BASE: str = Field(description="主 Agent LLM 端点(Anthropic 兼容)")
    EXTERNAL_API_KEY: str = Field(description="主 Agent LLM API key")
    EXTERNAL_MODEL: str = Field(description="主 Agent 模型 id")

    # ---- HTTP 服务 ----
    HOST: str = Field(default="0.0.0.0", description="监听地址")
    PORT: int = Field(default=8000, description="监听端口")
    CORS_ALLOWED_ORIGINS: str = Field(
        default="",
        description="逗号分隔的允许来源",
    )

    # ---- 日志 ----
    LOG_LEVEL: str = Field(
        default="INFO",
        description="日志等级,DEBUG / INFO / WARNING / ERROR",
    )
    LOG_FORMAT: str = Field(
        default="console",
        description="日志格式,console=开发彩色对齐 / json=生产单行 JSON",
    )
    LOG_FILE: str = Field(
        default="",
        description="日志文件路径,非空时同时写入文件(文件用 JSON 格式),为空则仅输出到 stderr",
    )

    # ---- 上下文压缩 ----
    ENABLE_COUNT_TOKENS_API: bool = Field(
        default=True,
        description="是否调 anthropic count_tokens API 精确估 token。"
        "Kimi /anthropic 端点不支持,可设 false 强制走字符数 / 4 兜底,"
        "避免每轮 404 噪音。设 true 时仍会自动降级(首次失败后本进程不再重试)。",
    )

    # ---- 鉴权 (JWT) ----
    JWT_SECRET: str = Field(
        default="dev-only-secret-change-me-in-production-min-32-chars",
        description="JWT 签名密钥。生产必须改成 32+ 字节强随机串(用 secrets.token_urlsafe(32))。"
        "默认值仅用于开发环境兜底,生产环境必须从 .env 注入。",
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT 签名算法。HS256 对称(本地开发够用),生产可考虑 RS256 非对称。",
    )
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="access token 有效期(分钟)。默认 1440 分钟(1 天),可按团队策略调整。",
    )
    JWT_REFRESH_EXPIRE_DAYS: int = Field(
        default=30,
        description="refresh token 有效期(天)。默认 30 天,过期后必须重新登录。",
    )
    AUTH_DEV_HEADER_FALLBACK: bool = Field(
        default=True,
        description="是否允许通过 X-User-Id header 兜底鉴权(开发后门)。"
        "true: 解 JWT 失败时回退读 header(集成测试 / 前端联调阶段使用);"
        "false: 强制走 JWT(生产环境必须设 false)。",
    )

    # ---- Redis (可选) ----
    REDIS_URL: str | None = Field(
        default=None,
        description="Redis 连接串,例 redis://default:password@localhost:6379/0。"
        "未设置时 logout JWT 黑名单功能降级为 no-op(仍允许 logout 但 token 不在服务端失效),"
        "其他依赖 Redis 的子系统(分布式锁 / 断点恢复)同样降级。",
    )

    # ---- Microsoft OAuth2 (Azure AD) ----
    AZURE_CLIENT_ID: str | None = Field(
        default=None,
        description="Azure AD 应用的 client_id（Application ID）。未配置时禁用微软登录入口。",
    )
    AZURE_CLIENT_SECRET: str | None = Field(
        default=None,
        description="Azure AD 应用的 client_secret。生产环境从 KeyVault 注入，禁止明文提交。",
    )
    AZURE_TENANT_ID: str = Field(
        default="common",
        description="AAD 租户 ID。'common' 允许任意微软账号登录；"
        "填具体租户 GUID 则仅允许该组织账号登录。",
    )
    AZURE_REDIRECT_URI: str = Field(
        default="http://localhost:5173/auth/microsoft/callback",
        description="OAuth2 授权码回调地址，必须与 Azure 应用注册中的重定向 URI 完全一致。"
        "本地开发默认指向 Vite dev server；生产环境改为真实域名。",
    )
    AZURE_OAUTH_STATE_TTL: int = Field(
        default=300,
        description="OAuth state 在 Redis 中的 TTL（秒）。防 CSRF，默认 5 分钟。",
    )


settings = Settings()
