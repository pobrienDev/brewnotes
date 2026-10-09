"""Application settings.

Loaded from environment variables (and a .env file in development). APP_ENV defaults to
production so that secure defaults apply unless development is chosen explicitly, and in
production the application refuses to start when any secret is missing.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["production", "development", "test"]

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = "production"

    database_url: str
    test_database_url: str | None = None
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_timeout_s: int = 5
    db_statement_timeout_ms: int = 10_000

    secret_key: str
    public_base_url: str
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1"]
    )

    github_client_id: str | None = None
    github_client_secret: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None

    forwarded_allow_ips: str = "127.0.0.1"
    sentry_dsn: str | None = None

    # Directory holding the built frontend (index.html and assets/). When unset, the API
    # serves no frontend, which is the case in development where Vite serves it.
    static_dir: Path | None = None

    max_body_bytes: int = 1_048_576
    log_level: str = "INFO"

    # Sessions: idle timeout, absolute lifetime, and how often last_seen_at is written.
    session_idle_days: int = 14
    session_absolute_days: int = 30
    session_touch_interval_s: int = 3600
    # The signed cookie that carries OAuth state between the redirect and the callback.
    oauth_state_max_age_s: int = 600
    login_rate_limit_per_minute: int = 10
    write_rate_limit_per_minute: int = 120
    # Per-account quotas (plan Section 5). Starting values; tune later.
    quota_recipes: int = 500
    quota_custom_ingredients: int = 200
    quota_batches: int = 1000
    quota_readings_per_batch: int = 20_000
    quota_beers: int = 5000
    quota_tastings: int = 5000
    # Phase 3: breweries come from Open Brewery DB's MIT-licensed dump (plan Appendix B).
    brewery_dump_url: str = (
        "https://raw.githubusercontent.com/openbrewerydb/openbrewerydb/master/breweries.csv"
    )
    brewery_dump_max_bytes: int = 50_000_000
    # Most breweries one map request returns; the map clusters them and asks to zoom in.
    map_max_results: int = 500
    # Origin the browser loads map tiles from (allowed in the CSP); empty disables tiles.
    map_tile_host: str = "https://api.maptiler.com"

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @field_validator("public_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _fail_closed_in_production(self) -> Settings:
        if self.app_env != "production":
            return self
        problems: list[str] = []
        if len(self.secret_key.encode()) < MIN_SECRET_KEY_LENGTH or "change-me" in self.secret_key:
            problems.append(f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} random bytes")
        if not self.public_base_url.startswith("https://"):
            problems.append("PUBLIC_BASE_URL must use https in production")
        for name in (
            "github_client_id",
            "github_client_secret",
            "google_client_id",
            "google_client_secret",
        ):
            if not getattr(self, name):
                problems.append(f"{name.upper()} is required in production")
        if problems:
            raise ValueError("Refusing to start in production: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def secure_cookies(self) -> bool:
        """Secure + __Host- prefixed cookies everywhere except plain-http development."""
        return not self.is_development

    @property
    def session_cookie_name(self) -> str:
        return "__Host-session" if self.secure_cookies else "session"

    @property
    def oauth_cookie_name(self) -> str:
        return "__Host-oauth" if self.secure_cookies else "oauth"

    @property
    def configured_providers(self) -> list[str]:
        providers: list[str] = []
        if self.github_client_id and self.github_client_secret:
            providers.append("github")
        if self.google_client_id and self.google_client_secret:
            providers.append("google")
        return providers

    def oauth_redirect_uri(self, provider: str) -> str:
        return f"{self.public_base_url}/api/v1/auth/callback/{provider}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # required fields come from the environment


def tooling_settings() -> Settings:
    """Settings for commands that never touch the database or secrets, e.g. OpenAPI export."""
    return Settings(
        _env_file=None,
        app_env="development",
        database_url="postgresql+psycopg://brewnotes@localhost:5432/brewnotes",
        secret_key="0" * MIN_SECRET_KEY_LENGTH,
        public_base_url="http://localhost:5173",
    )
