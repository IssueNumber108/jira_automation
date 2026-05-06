"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All Jira connection parameters sourced from environment variables.

    Required variables (set in .env or the shell):
        JIRA_URL          – base URL, e.g. https://myorg.atlassian.net
        JIRA_API_TOKEN    – personal access token or Basic-auth token
        JIRA_CERT_PATH    – path to the PEM certificate used for TLS verification
        JIRA_EMAIL        – email address paired with the API token (Cloud only)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Jira connection ────────────────────────────────────────────────────────
    jira_url: Annotated[AnyHttpUrl, Field(description="Jira base URL")]
    jira_api_token: Annotated[str, Field(description="API token or PAT")]
    jira_email: Annotated[str, Field(description="Account email (Cloud)")]
    jira_cert_path: Annotated[
        Path,
        Field(description="Path to PEM certificate for TLS verification"),
    ]

    # ── Fetch tuning ───────────────────────────────────────────────────────────
    jira_max_results_per_page: int = Field(default=100, ge=1, le=1000)
    jira_request_timeout: float = Field(default=30.0, gt=0)
    jira_max_retries: int = Field(default=3, ge=0)

    # ── Output ─────────────────────────────────────────────────────────────────
    output_dir: Path = Field(default=Path("outputs"))

    @field_validator("jira_cert_path")
    @classmethod
    def cert_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Certificate file not found: {v}")
        return v

    @field_validator("output_dir")
    @classmethod
    def ensure_output_dir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def jira_base_url(self) -> str:
        return str(self.jira_url).rstrip("/")


# ---------------------------------------------------------------------------
# Lazy singleton — instantiated on first access to avoid import-time errors
# when required env vars are absent (e.g. in unit tests that don't need them).
# ---------------------------------------------------------------------------
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance (created on first call)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()  # type: ignore[call-arg]
    return _settings_instance


class _SettingsProxy:
    """Proxy that forwards attribute access to the lazy singleton."""

    def __getattr__(self, name: str) -> object:
        return getattr(get_settings(), name)


settings: Settings = _SettingsProxy()  # type: ignore[assignment]
