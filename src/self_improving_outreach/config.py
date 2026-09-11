"""Environment-driven settings. Missing keys imply mock mode — never required in CI."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def you_key(self) -> Optional[str]:
        key = self.you_api_key or self.ydc_api_key
        return key or None

    @property
    def clickhouse_configured(self) -> bool:
        return bool(self.clickhouse_host and self.clickhouse_password is not None)

    @property
    def is_mock(self) -> bool:
        if self.mock_mode is not None:
            return self.mock_mode
        return not (self.openai_api_key and self.you_key)

    @property
    def use_crewai(self) -> bool:
        return (not self.is_mock) and bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
