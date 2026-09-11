import os

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.config import (
    DEFAULT_BOUNDLESS_BASE_URL,
    Settings,
    public_settings_view,
)
from self_improving_outreach.llm import apply_llm_runtime_env, crewai_model_name


def test_boundless_provider_enables_crewai_when_not_mock():
    settings = Settings(
        mock_mode=False,
        llm_provider="boundless",
        boundless_api_key="bai-test",
    )
    assert settings.effective_llm_provider == "boundless"
    assert settings.use_crewai is True
    assert settings.llm_base_url == DEFAULT_BOUNDLESS_BASE_URL
    assert settings.llm_api_key == "bai-test"
    assert settings.llm_model == "gpt-4o-mini"
    assert crewai_model_name(settings) == "openai/gpt-4o-mini"


def test_openai_falls_back_to_boundless_when_only_boundless_key():
    settings = Settings(mock_mode=False, llm_provider="openai", boundless_api_key="bai-test")
    assert settings.effective_llm_provider == "boundless"
    assert settings.use_crewai is True
    assert settings.llm_api_key == "bai-test"


def test_openai_preferred_when_both_keys():
    settings = Settings(
        mock_mode=False,
        openai_api_key="sk-oai",
        boundless_api_key="bai-test",
    )
    assert settings.effective_llm_provider == "openai"
    assert settings.llm_base_url is None
    assert settings.llm_api_key == "sk-oai"


def test_explicit_boundless_overrides_openai_key():
    settings = Settings(
        mock_mode=False,
        llm_provider="boundless",
        openai_api_key="sk-oai",
        boundless_api_key="bai-test",
        boundless_base_url="https://api.inference.boundless.network/v1",
        boundless_model="glm-5.2",
    )
    assert settings.effective_llm_provider == "boundless"
    assert settings.llm_api_key == "bai-test"
    assert settings.llm_model == "glm-5.2"
    assert settings.llm_base_url == "https://api.inference.boundless.network/v1"


def test_mock_mode_ignores_boundless_key():
    settings = Settings(mock_mode=True, llm_provider="boundless", boundless_api_key="bai-test")
    assert settings.is_mock is True
    assert settings.use_crewai is False


def test_invalid_llm_provider_rejected():
    with pytest.raises(ValidationError):
        Settings(llm_provider="anthropic")


def test_apply_boundless_runtime_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    settings = Settings(mock_mode=False, llm_provider="boundless", boundless_api_key="bai-test")
    apply_llm_runtime_env(settings)
    assert os.environ["OPENAI_API_KEY"] == "bai-test"
    assert os.environ["OPENAI_BASE_URL"] == DEFAULT_BOUNDLESS_BASE_URL
    assert os.environ["OPENAI_API_BASE"] == DEFAULT_BOUNDLESS_BASE_URL


def test_public_settings_view_and_show_config_hide_secrets():
    settings = Settings(
        mock_mode=True,
        llm_provider="boundless",
        boundless_api_key="sk-secret-boundless",
        openai_api_key="sk-secret-openai",
        livekit_api_secret="lk-secret",
    )
    view = public_settings_view(settings)
    dumped = str(view)
    assert "sk-secret-boundless" not in dumped
    assert "sk-secret-openai" not in dumped
    assert "lk-secret" not in dumped
    assert view["boundless_configured"] is True
    assert view["openai_configured"] is True
    assert view["llm_provider"] == "boundless"
    assert view["livekit_feedback_auto"] is False

    runner = CliRunner()
    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0, result.stdout
    assert "sk-secret" not in result.stdout
    assert "Cubiczan" in result.stdout
    assert "llm_provider" in result.stdout


def test_show_config_hides_env_secrets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BOUNDLESS_API_KEY", "sk-secret-boundless")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-openai")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "lk-secret")
    monkeypatch.setenv("LLM_PROVIDER", "boundless")
    from self_improving_outreach.config import reset_settings_cache

    reset_settings_cache()
    runner = CliRunner()
    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0, result.stdout
    assert "sk-secret-boundless" not in result.stdout
    assert "sk-secret-openai" not in result.stdout
    assert "lk-secret" not in result.stdout
    assert "boundless_configured" in result.stdout
