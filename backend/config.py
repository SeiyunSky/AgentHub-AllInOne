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

    # ---- 上下文压缩 ----
    ENABLE_COUNT_TOKENS_API: bool = Field(
        default=True,
        description="是否调 anthropic count_tokens API 精确估 token。"
        "Kimi /anthropic 端点不支持,可设 false 强制走字符数 / 4 兜底,"
        "避免每轮 404 噪音。设 true 时仍会自动降级(首次失败后本进程不再重试)。",
    )


settings = Settings()
