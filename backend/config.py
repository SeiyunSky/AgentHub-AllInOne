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


settings = Settings()
