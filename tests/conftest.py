import pytest

from self_improving_outreach.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    monkeypatch.delenv("BOUNDLESS_API_KEY", raising=False)
    monkeypatch.delenv("BOUNDLESS_BASE_URL", raising=False)
    monkeypatch.delenv("BOUNDLESS_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_FEEDBACK_AUTO", raising=False)
    monkeypatch.delenv("LIVEKIT_TRANSCRIPT_PATH", raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()
