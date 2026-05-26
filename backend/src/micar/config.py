"""Environment-driven settings. Mirrors recruiter/config.py."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Persistence
    database_url: str = "postgresql+psycopg://micar:micar@localhost:5433/micar"

    # Auth bridge with Next.js frontend (HS256 shared secret)
    jwt_shared_secret: SecretStr = Field(default=SecretStr(""))
    jwt_audience: str = "micar-backend"
    jwt_issuer: str = "micar-frontend"

    # Email allowlist for first-run user provisioning (comma-separated)
    user_email_allowlist: str = ""
    # Local development escape hatch. Keep false outside a disposable dev database.
    allow_unrestricted_dev_auth: bool = False

    # LLM
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    # "anthropic" | "bedrock" | "vertex"; production provider requires approval.
    llm_provider: str = "anthropic"
    llm_model_synthesis: str = "claude-opus-4-7"
    llm_model_default: str = "claude-sonnet-4-6"
    llm_model_triage: str = "claude-haiku-4-5"

    # BRAO posture
    # API keys alone never activate external processing.
    external_llm_processing_enabled: bool = False
    # Set only where approval expressly covers identifiable mandate facts.
    allow_unredacted_external_client_data: bool = False
    # When True, client identifiers are redacted before any LLM call.
    redact_client_identifiers_default: bool = True
    # When True, full prompts are persisted to audit log. Default False per § 203 StGB.
    audit_persist_prompt_bodies: bool = False

    # HTTP
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 3

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8090
    cors_allow_origins: str = "http://localhost:3000"

    # Artifact storage
    artifacts_dir: Path = Path("./artifacts_store")

    # Reg feed scheduler
    reg_feed_poll_interval_minutes: int = 60
    reg_feed_enabled: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def allowlisted_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.user_email_allowlist.split(",") if e.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
