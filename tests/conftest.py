import pytest

from self_improving_outreach.config import reset_settings_cache


@pytest.fixture(autouse=True)
def _mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    monkeypatch.delenv("YDC_API_KEY", raising=False)
    monkeypatch.delenv("CLICKHOUSE_HOST", raising=False)
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()
