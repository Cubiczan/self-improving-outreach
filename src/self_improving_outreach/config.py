"""Environment-driven settings. Missing keys imply mock mode — never required in CI."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sam's credit: https://inference.boundless.network/ — do not use api.boundlessapi.com
DEFAULT_BOUNDLESS_BASE_URL = "https://api.inference.boundless.network/v1"
DEFAULT_BOUNDLESS_MODEL = "glm-5.2"
LLM_PROVIDERS = ("openai", "boundless")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    crewai_model: str = "gpt-4o-mini"
    crewai_verbose: bool = False

    llm_provider: str = "openai"
    boundless_api_key: Optional[str] = None
    boundless_base_url: str = DEFAULT_BOUNDLESS_BASE_URL
    boundless_model: str = DEFAULT_BOUNDLESS_MODEL

    mock_mode: Optional[bool] = None

    you_api_key: Optional[str] = None
    ydc_api_key: Optional[str] = None

    daytona_api_key: Optional[str] = None
    daytona_api_url: str = "https://app.daytona.io/api"
    daytona_otel_enabled: bool = False
    daytona_sandbox_runs: bool = False

    livekit_api_key: Optional[str] = None
    livekit_api_secret: Optional[str] = None
    livekit_url: Optional[str] = None
    livekit_feedback_auto: bool = False
    livekit_transcript_path: Optional[str] = None

    clickhouse_host: Optional[str] = None
    clickhouse_port: int = 8443
    clickhouse_secure: bool = True
    clickhouse_user: str = "default"
    clickhouse_password: Optional[str] = None
    clickhouse_database: str = "outreach"

    human_gate_enabled: bool = False
    default_channel: str = "linkedin"
    swarm_concurrency: int = 5
    swarm_interval_seconds: int = 300
    simulate_outcomes: bool = True
    pending_approvals_path: str = "pending_approvals.jsonl"

    @field_validator("llm_provider")
    @classmethod
    def _normalize_llm_provider(cls, value: str) -> str:
        normalized = (value or "openai").strip().lower()
        if normalized not in LLM_PROVIDERS:
            raise ValueError("LLM_PROVIDER must be 'openai' or 'boundless'")
        return normalized

    @property
    def you_key(self) -> Optional[str]:
        key = self.you_api_key or self.ydc_api_key
        return key or None

    @property
    def clickhouse_configured(self) -> bool:
        return bool(self.clickhouse_host and self.clickhouse_password is not None)

    @property
    def effective_llm_provider(self) -> str:
        """Requested provider, or Boundless when OpenAI is selected but only Boundless is keyed."""
        if self.llm_provider == "boundless":
            return "boundless"
        if self.openai_api_key:
            return "openai"
        if self.boundless_api_key:
            return "boundless"
        return "openai"

    @property
    def llm_api_key(self) -> Optional[str]:
        if self.effective_llm_provider == "boundless":
            return self.boundless_api_key
        return self.openai_api_key

    @property
    def llm_base_url(self) -> Optional[str]:
        if self.effective_llm_provider == "boundless":
            return self.boundless_base_url or DEFAULT_BOUNDLESS_BASE_URL
        return None

    @property
    def llm_model(self) -> str:
        if self.effective_llm_provider == "boundless":
            return self.boundless_model or self.crewai_model
        return self.crewai_model

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def is_mock(self) -> bool:
        if self.mock_mode is not None:
            return self.mock_mode
        return not (self.has_llm_credentials and self.you_key)

    @property
    def use_crewai(self) -> bool:
        return (not self.is_mock) and self.has_llm_credentials


def public_settings_view(settings: Settings) -> dict[str, Any]:
    """Non-secret configuration for CLI / diagnostics. Never includes key material."""
    from self_improving_outreach.brand import BRAND
    from self_improving_outreach.paths import sample_queue_path

    return {
        "brand": BRAND,
        "mock_mode": settings.is_mock,
        "llm_provider": settings.effective_llm_provider,
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "openai_configured": bool(settings.openai_api_key),
        "boundless_configured": bool(settings.boundless_api_key),
        "you_com_configured": bool(settings.you_key),
        "clickhouse_configured": bool(settings.clickhouse_host),
        "daytona_configured": bool(settings.daytona_api_key),
        "livekit_configured": bool(settings.livekit_api_key),
        "livekit_feedback_auto": settings.livekit_feedback_auto,
        "crewai": settings.use_crewai,
        "sample_queue": str(sample_queue_path()),
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
