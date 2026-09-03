from functools import lru_cache
from typing import List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. Loaded once from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "REVIVE Autonomous Revenue Recovery Agent"
    app_version: str = "2.1.0"

    database_url: str = "sqlite+aiosqlite:///./revive.db"

    razorpay_key_id: str = "rzp_test_revive_key"
    razorpay_key_secret: str = "rzp_test_revive_secret"
    razorpay_webhook_secret: str = "test_webhook_secret_revive_2026"
    razorpay_enable_live_api: bool = False

    openai_api_key: str = ""
    gemini_api_key: str = ""
    openai_model: str = "vertex_ai/gemini-3.5-flash"
    openai_base_url: str = "https://litellm-platform.penpencil.guru"

    jwt_secret: str = "dev-only-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    operator_username: str = "ops"
    operator_password: str = "revive-ops-2026"
    operator_role: str = "admin"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    auth_required: bool | None = None
    chaos_enabled: bool | None = None
    worker_enabled: bool = True
    worker_interval_seconds: float = 5.0
    rate_limit_enabled: bool | None = None
    webhook_rate_limit_per_minute: int = 120
    api_rate_limit_per_minute: int = 300

    sentry_dsn: str = ""

    circadian_send_enabled: bool | None = None
    link_followup_seconds: int | None = None

    # High Concurrency & Connection Pool Settings
    db_pool_size: int = 50
    db_max_overflow: int = 100
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # Enterprise Security & Replay Window
    webhook_replay_tolerance_seconds: int = 300
    enforce_replay_window: bool = False

    # AI Reasoning Latency Budget & Cache
    ai_timeout_seconds: float = 1.5
    strategy_cache_enabled: bool = True
    strategy_cache_ttl_seconds: int = 3600

    # Stamped Caching & Singleflight Coalescing (Thundering Herd Protection)
    stamped_cache_enabled: bool = True
    stamped_cache_default_ttl: float = 60.0
    stamped_cache_swr_grace: float = 30.0
    stamped_cache_beta: float = 1.0

    @field_validator("database_url")
    @classmethod
    def strip_database_url(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def require_auth(self) -> bool:
        if self.auth_required is not None:
            return self.auth_required
        return self.is_production

    @property
    def allow_chaos(self) -> bool:
        if self.chaos_enabled is not None:
            return self.chaos_enabled
        return not self.is_production

    @property
    def allow_hmac_bypass(self) -> bool:
        if self.chaos_enabled is True:
            return True
        return self.app_env in ("development", "test")

    @property
    def enable_rate_limit(self) -> bool:
        if self.rate_limit_enabled is not None:
            return self.rate_limit_enabled
        return self.is_production

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def normalized_database_url(self) -> str:
        """
        Normalizes database URL for SQLAlchemy asyncpg driver.
        Automatically converts Neon / Postgres URLs (postgres:// or postgresql://)
        to postgresql+asyncpg:// and filters out unsupported parameters like channel_binding.
        """
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://") :]
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]

        if url.startswith("postgresql+asyncpg://"):
            parsed = urlparse(url)
            if parsed.query:
                params = dict(parse_qsl(parsed.query))
                params.pop("channel_binding", None)
                params.pop("gssencmode", None)
                if "sslmode" in params:
                    mode = params.pop("sslmode")
                    if mode in ("require", "verify-ca", "verify-full"):
                        params["ssl"] = "require"
                new_query = urlencode(params)
                url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

        return url

    @property
    def use_circadian_send(self) -> bool:
        if self.circadian_send_enabled is not None:
            return self.circadian_send_enabled
        return self.app_env != "test"

    @property
    def followup_seconds(self) -> int:
        if self.link_followup_seconds is not None:
            return int(self.link_followup_seconds)
        return 120 if self.app_env == "development" else 86_400

    @property
    def llm_endpoint_url(self) -> str:
        """
        Normalizes the OpenAI/LiteLLM chat completions endpoint URL.
        Accepts root base URLs, /v1 endpoints, or full paths.
        """
        base = (self.openai_base_url or "https://api.openai.com/v1").strip().rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/chat/completions"


@lru_cache
def get_settings() -> Settings:
    return Settings()
