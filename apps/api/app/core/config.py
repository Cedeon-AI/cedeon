"""Application configuration (pydantic-settings). All keys are prefixed ``CEDEON_``."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]

_DEV_SECRET_MARKER = "dev-only-change-me"  # noqa: S105 - marker string, not a credential


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CEDEON_",
        # Local dev: repo-root .env whether run from the repo root or apps/api.
        env_file=(".env", "../.env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = "local"
    log_level: str = "INFO"
    log_json: bool = False

    # Database — async URL for the app, sync URL for Alembic + Procrastinate.
    database_url: str = "postgresql+asyncpg://cedeon:cedeon@localhost:5432/cedeon"
    database_url_sync: str = ""

    # Auth / sessions
    session_secret: str = f"{_DEV_SECRET_MARKER}-{'0' * 48}"
    session_ttl_hours: int = 12
    session_idle_timeout_hours: int = 2
    cookie_name: str = "cedeon_session"
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # Team invitations
    invitation_ttl_days: int = 7
    # Public origin the accept link points at (the single Next.js origin, ADR-0004).
    public_base_url: str = "http://localhost:3000"
    # "console" logs the message (dev / no provider). "ses" uses Amazon SES via the
    # ambient AWS credential chain — inert until AWS creds + a verified sending domain
    # exist (ADR-0027).
    email_sender: Literal["console", "ses"] = "console"
    email_from: str = "Cedeon <no-reply@cedeon.app>"
    ses_region: str = "us-east-1"

    # Signup gating (ADR-0028). "open" self-serve · "code" needs an access code you
    # minted (`just mint-code`) · "closed" no self-serve at all. Forced to code/closed
    # outside local/test by the validator below.
    signup_mode: Literal["open", "code", "closed"] = "open"
    signup_code_ttl_days: int = 30
    # Where org-creation and AI-budget notices are sent. None → only the audit log +
    # structured logs record them.
    ops_email: str | None = None

    # Object storage
    object_store: Literal["filesystem", "s3"] = "filesystem"
    filesystem_store_root: str = ".data/objectstore"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "cedeon-local"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_force_path_style: bool = True

    # Document pipeline
    document_parser: Literal["pymupdf", "docling"] = "pymupdf"
    document_max_upload_mb: int = 50

    # Loss import pipeline
    loss_import_max_upload_mb: int = 25

    # AI providers — accept the bare vendor env names too (ANTHROPIC_API_KEY etc.).
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CEDEON_ANTHROPIC_API_KEY"),
    )
    # Required when the Anthropic key is identity-linked / workspace-scoped.
    anthropic_workspace_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_WORKSPACE_ID", "CEDEON_ANTHROPIC_WORKSPACE_ID"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "CEDEON_OPENAI_API_KEY"),
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "CEDEON_GOOGLE_API_KEY"),
    )
    # Per-task model config (provider:model). Do not hard-code model names elsewhere.
    treaty_extraction_model: str = "anthropic:claude-opus-5"
    recovery_investigator_model: str = "anthropic:claude-opus-5"
    notice_drafter_model: str = "anthropic:claude-opus-5"
    ai_enabled: bool = True

    # Recovery Investigator bounds (docs/AI_ARCHITECTURE.md §2b — bounded, read-only).
    investigator_request_limit: int = 12
    investigator_tool_calls_limit: int = 24
    investigator_total_tokens_limit: int = 200_000
    investigator_timeout_seconds: int = 120

    # Notice drafter (docs/AI_ARCHITECTURE.md §2c — one output_type call, no tools).
    notice_drafter_timeout_seconds: int = 90

    # Telemetry
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""
    service_name: str = "cedeon-api"

    # CORS — empty by design (single public origin, see ADR-0004).
    cors_allow_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _derive_and_validate(self) -> Settings:
        # Managed platforms (Render, Fly, Heroku, …) inject a bare `postgres://` or
        # `postgresql://` URL. Attach the drivers Cedeon uses: asyncpg for the app,
        # psycopg (v3) for Alembic + Procrastinate.
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
        self.database_url = url
        if not self.database_url_sync:
            self.database_url_sync = self.database_url.replace("+asyncpg", "+psycopg")

        # Accept a scheme-less public origin (e.g. Render's `fromService` host value).
        if self.public_base_url and "://" not in self.public_base_url:
            self.public_base_url = f"https://{self.public_base_url}"

        if self.env in ("staging", "production"):
            if _DEV_SECRET_MARKER in self.session_secret:
                raise ValueError(
                    "CEDEON_SESSION_SECRET must be set to a real secret outside local/test"
                )
            if len(self.session_secret) < 32:
                raise ValueError("CEDEON_SESSION_SECRET must be at least 32 characters")
            if "localhost" in self.database_url:
                raise ValueError(
                    "CEDEON_DATABASE_URL still points at localhost in a deployed environment"
                )
            if self.signup_mode == "open":
                raise ValueError(
                    "CEDEON_SIGNUP_MODE must be 'code' or 'closed' outside local/test "
                    "(open self-serve registration is not allowed in a deployed environment)"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
