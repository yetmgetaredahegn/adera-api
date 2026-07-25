"""Typed settings.

The one rule (05 §2): every environment value is read here and nowhere else.
`os.getenv` outside this module is a bug — it defeats typing, defaults, and the
ability to see the whole configuration surface in one place.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_KEY = "dev-only-insecure-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "ci", "staging", "prod"] = "local"
    debug: bool = False

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+asyncpg://adera:adera@localhost:5432/adera")
    )
    redis_url: RedisDsn = Field(default=RedisDsn("redis://localhost:6379/0"))

    secret_key: str = _INSECURE_SECRET_KEY

    @model_validator(mode="after")
    def _reject_insecure_secret_in_prod(self) -> "Settings":
        # SECURITY.md gap G1: this key signs session cookies (app/core/security.py)
        # -- shipping the known default in prod means anyone can forge a session.
        if self.env == "prod" and self.secret_key == _INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the insecure default in a prod environment. "
                'Set a real SECRET_KEY (python -c "import secrets; '
                'print(secrets.token_urlsafe(48))") before deploying.'
            )
        return self

    # Session cookies (05 §3). A `Secure` cookie is NEVER sent back by a real
    # browser over plain HTTP -- curl ignores the flag, which is why the auth
    # flow could be "proven" while a browser on http://localhost silently got
    # no session at all. Defaults to False only for env=local so web/mobile can
    # integrate without TLS; every other environment keeps it on. Set
    # COOKIE_SECURE explicitly to override either way.
    cookie_secure: bool = True

    @model_validator(mode="after")
    def _relax_cookie_secure_for_local(self) -> "Settings":
        if "cookie_secure" not in self.model_fields_set and self.env == "local":
            self.cookie_secure = False
        return self

    # CORS: the browser clients (adera-web, Phase 2) are a different origin from
    # the API, and cookie auth means credentialed requests -- which forbids the
    # "*" wildcard, so origins must be listed explicitly. PROD MUST OVERRIDE.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, value: object) -> object:
        # Accept "a,b" as well as JSON '["a","b"]' -- a comma-separated env var is
        # what a deploy pipeline actually writes.
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # HTTP rate limiting (docs/11 §0: 429 `rate_limited` + Retry-After).
    rate_limit_enabled: bool = True
    rate_limit_per_min: int = 300
    # Only trust X-Forwarded-For when a reverse proxy (Caddy, infra/) actually
    # sets it. Trusting it unconditionally lets any client forge its own IP and
    # walk around the limiter one fake header at a time.
    trust_proxy_headers: bool = False

    # AI Kernel (ADR-014). NFR-COST-1: a hard daily cap with a breaker, not a hope.
    kernel_daily_budget_usd: float = 5.0
    kernel_cache_ttl_seconds: int = 60 * 60 * 24 * 7

    # Storage: R2 behind an adapter (ADR-013). Absent locally until Week 2.
    r2_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str | None = None

    # Ingestion (FR-2.5): identify ourselves, and be rate-limited by default.
    fetch_user_agent: str = "ADERA/0.1 (+https://adera.bid/about/crawler)"
    fetch_timeout_seconds: int = 30

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once per process."""
    return Settings()


settings = get_settings()
