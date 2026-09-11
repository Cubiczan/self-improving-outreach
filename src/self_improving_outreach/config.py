"""Environment-driven settings. Missing keys imply mock mode — never required in CI."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from self_improving_outreach.one_defaults import (
    DEFAULT_DAYTONA_CREATE_SANDBOX_ACTION_ID,
    DEFAULT_DAYTONA_DOCKERFILE,
    DEFAULT_DAYTONA_SNAPSHOT,
    DEFAULT_YOU_RESEARCH_ACTION_ID,
    DEFAULT_YOU_SEARCH_ACTION_ID,
)

# Sam's credit: https://inference.boundless.network/ — do not use api.boundlessapi.com
DEFAULT_BOUNDLESS_BASE_URL = "https://api.inference.boundless.network/v1"
DEFAULT_BOUNDLESS_MODEL = "glm-5.2"
LLM_PROVIDERS = ("openai", "boundless")
RESEARCH_PROVIDERS = ("auto", "one", "you")
SANDBOX_PROVIDERS = ("auto", "one", "daytona")


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

    research_provider: str = "auto"
    sandbox_provider: str = "auto"

    one_secret: Optional[str] = None
    one_cli: str = "one"
    one_cli_auth: Optional[bool] = None
    one_timeout_seconds: float = 90.0
    one_you_connection_key: Optional[str] = None
    one_daytona_connection_key: Optional[str] = None
    one_you_search_action_id: str = DEFAULT_YOU_SEARCH_ACTION_ID
    one_you_research_action_id: str = DEFAULT_YOU_RESEARCH_ACTION_ID
    one_you_contents_action_id: Optional[str] = None
    one_daytona_create_sandbox_action_id: str = DEFAULT_DAYTONA_CREATE_SANDBOX_ACTION_ID
    one_daytona_start_sandbox_action_id: Optional[str] = None
    one_daytona_list_sandbox_action_id: Optional[str] = None
    one_daytona_delete_sandbox_action_id: Optional[str] = None
    one_daytona_sandbox_path_var: str = "sandboxIdOrName"
    one_daytona_dockerfile: str = DEFAULT_DAYTONA_DOCKERFILE
    one_daytona_snapshot: str = DEFAULT_DAYTONA_SNAPSHOT

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
    learn_on_draft: bool = False
    mock_learn_outcomes: bool = False
    pending_approvals_path: str = "pending_approvals.jsonl"

    clickup_api_token: Optional[str] = None
    clickup_list_id: str = "901716996906"
    clickup_queue_status: str = "Queued"

    @field_validator("llm_provider")
    @classmethod
    def _normalize_llm_provider(cls, value: str) -> str:
        normalized = (value or "openai").strip().lower()
        if normalized not in LLM_PROVIDERS:
            raise ValueError("LLM_PROVIDER must be 'openai' or 'boundless'")
        return normalized

    @field_validator("research_provider")
    @classmethod
    def _normalize_research_provider(cls, value: str) -> str:
        normalized = (value or "auto").strip().lower()
        if normalized not in RESEARCH_PROVIDERS:
            raise ValueError("RESEARCH_PROVIDER must be 'one', 'you', or 'auto'")
        return normalized

    @field_validator("sandbox_provider")
    @classmethod
    def _normalize_sandbox_provider(cls, value: str) -> str:
        normalized = (value or "auto").strip().lower()
        if normalized not in SANDBOX_PROVIDERS:
            raise ValueError("SANDBOX_PROVIDER must be 'one', 'daytona', or 'auto'")
        return normalized

    @property
    def you_key(self) -> Optional[str]:
        key = self.you_api_key or self.ydc_api_key
        return key or None

    @property
    def one_auth_configured(self) -> bool:
        """True when One can authenticate (secret, explicit CLI flag, or local CLI config)."""
        if self.one_secret:
            return True
        if self.one_cli_auth is True:
            return True
        if self.one_cli_auth is False:
            return False
        from self_improving_outreach.tools.one_cli import local_one_config_present

        return local_one_config_present()

    @property
    def one_you_ready(self) -> bool:
        return bool(self.one_you_connection_key) and self.one_auth_configured

    @property
    def one_daytona_ready(self) -> bool:
        return bool(self.one_daytona_connection_key) and self.one_auth_configured

    @property
    def effective_research_provider(self) -> str:
        """Resolved research path: ``one``, ``you``, or ``mock``."""
        requested = self.research_provider
        if requested == "you":
            return "you" if self.you_key else "mock"
        if requested == "one":
            if self.one_you_ready:
                return "one"
            return "you" if self.you_key else "mock"
        if self.one_you_ready:
            return "one"
        if self.you_key:
            return "you"
        return "mock"

    @property
    def effective_sandbox_provider(self) -> str:
        """Resolved sandbox path: ``one``, ``daytona``, or ``none``."""
        requested = self.sandbox_provider
        if requested == "daytona":
            return "daytona" if self.daytona_api_key else "none"
        if requested == "one":
            if self.one_daytona_ready:
                return "one"
            return "daytona" if self.daytona_api_key else "none"
        if self.one_daytona_ready:
            return "one"
        if self.daytona_api_key:
            return "daytona"
        return "none"

    @property
    def research_live(self) -> bool:
        return self.effective_research_provider in {"one", "you"}

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
        return not (self.has_llm_credentials and self.research_live)

    @property
    def use_crewai(self) -> bool:
        return (not self.is_mock) and self.has_llm_credentials

    @property
    def should_learn_on_draft(self) -> bool:
        """Draft→Learner is opt-in for live; mock + SIMULATE_OUTCOMES still demos it."""
        if self.learn_on_draft or self.mock_learn_outcomes:
            return True
        return bool(self.simulate_outcomes and self.is_mock)

    @property
    def clickup_configured(self) -> bool:
        return bool(self.clickup_api_token)


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
        "research_provider": "mock" if settings.is_mock else settings.effective_research_provider,
        "sandbox_provider": settings.effective_sandbox_provider,
        "you_com_configured": bool(settings.you_key),
        "one_configured": settings.one_auth_configured,
        "one_you_configured": bool(settings.one_you_connection_key),
        "one_daytona_configured": bool(settings.one_daytona_connection_key),
        "clickhouse_configured": bool(settings.clickhouse_host),
        "daytona_configured": bool(settings.daytona_api_key),
        "daytona_sandbox_runs": settings.daytona_sandbox_runs,
        "livekit_configured": bool(settings.livekit_api_key),
        "livekit_feedback_auto": settings.livekit_feedback_auto,
        "simulate_outcomes": settings.simulate_outcomes,
        "learn_on_draft": settings.learn_on_draft or settings.mock_learn_outcomes,
        "should_learn_on_draft": settings.should_learn_on_draft,
        "clickup_configured": settings.clickup_configured,
        "clickup_list_id": settings.clickup_list_id,
        "crewai": settings.use_crewai,
        "sample_queue": str(sample_queue_path()),
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
