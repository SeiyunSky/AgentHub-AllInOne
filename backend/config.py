from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Runtime
    env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    db_url: str = "mysql+pymysql://root:password@localhost:3306/agenthub"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Redis
    redis_url: str | None = None
    rate_limit_backend: str = "memory"

    # Anthropic / Claude
    anthropic_api_key: str | None = None
    anthropic_model_id: str = "claude-sonnet-4-6"
    anthropic_base_url: str = "https://api.anthropic.com"

    # OpenAI / Custom adapter
    openai_api_key: str | None = None
    openai_model_id: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"

    # Codex CLI (https://github.com/openai/codex)
    codex_bin_path: str = "codex"

    # OpenCode CLI
    opencode_bin_path: str = "opencode"

    # HTTP proxy (optional, passed to SDK clients)
    proxy: str | None = None

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
