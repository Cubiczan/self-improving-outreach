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
    assert settings.llm_model == "glm-5.2"
    assert settings.llm_base_url == "https://api.inference.boundless.network/v1"
    assert "boundlessapi.com" not in settings.llm_base_url
    assert crewai_model_name(settings) == "openai/glm-5.2"


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
        boundless_model="dsv4",
    )
    assert settings.effective_llm_provider == "boundless"
    assert settings.llm_api_key == "bai-test"
    assert settings.llm_model == "dsv4"
    assert settings.llm_base_url == DEFAULT_BOUNDLESS_BASE_URL
    assert DEFAULT_BOUNDLESS_BASE_URL == "https://api.inference.boundless.network/v1"


def test_mock_mode_ignores_boundless_key():
    settings = Settings(mock_mode=True, llm_provider="boundless", boundless_api_key="bai-test")
    assert settings.is_mock is True
    assert settings.use_crewai is False


def test_invalid_llm_provider_rejected():
    with pytest.raises(ValidationError):
        Settings(llm_provider="anthropic")


def test_one_daytona_create_defaults_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ONE_DAYTONA_DOCKERFILE", "FROM ubuntu:22.04")
    monkeypatch.setenv("ONE_DAYTONA_SNAPSHOT", "daytonaio/sandbox:latest")
    settings = Settings(one_cli_auth=False)
    assert settings.one_daytona_dockerfile == "FROM ubuntu:22.04"
    assert settings.one_daytona_snapshot == "daytonaio/sandbox:latest"


def test_invalid_research_and_sandbox_providers_rejected():
    with pytest.raises(ValidationError):
        Settings(research_provider="bing")
    with pytest.raises(ValidationError):
        Settings(sandbox_provider="aws")


def test_auto_research_prefers_one_then_you():
    one = Settings(
        one_secret="sk-test",
        one_you_connection_key="live::you::default::test",
        you_api_key="ydc",
        one_cli_auth=False,
    )
    assert one.effective_research_provider == "one"
    assert one.one_you_ready is True
    you = Settings(you_api_key="ydc", one_cli_auth=False)
    assert you.effective_research_provider == "you"
    none = Settings(one_cli_auth=False)
    assert none.effective_research_provider == "mock"


def test_one_counts_as_live_research_for_auto_mock():
    settings = Settings(
        mock_mode=None,
        openai_api_key="sk-oai",
        one_secret="sk-test",
        one_you_connection_key="live::you::default::test",
        one_cli_auth=False,
    )
    assert settings.research_live is True
    assert settings.is_mock is False


def test_research_provider_one_falls_back_without_connection():
    settings = Settings(
        research_provider="one",
        you_api_key="ydc",
        one_cli_auth=False,
    )
    assert settings.effective_research_provider == "you"


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
        one_secret="sk-secret-one",
        one_you_connection_key="live::you::default::secret-conn",
        one_daytona_connection_key="live::daytona::default::secret-conn",
        one_cli_auth=False,
    )
    view = public_settings_view(settings)
    dumped = str(view)
    assert "sk-secret-boundless" not in dumped
    assert "sk-secret-openai" not in dumped
    assert "lk-secret" not in dumped
    assert "sk-secret-one" not in dumped
    assert "secret-conn" not in dumped
    assert view["one_configured"] is True
    assert view["one_you_configured"] is True
    assert view["research_provider"] in {"one", "mock", "you"}
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
    monkeypatch.setenv("ONE_SECRET", "sk-secret-one")
    monkeypatch.setenv("ONE_YOU_CONNECTION_KEY", "live::you::default::secret-conn")
    from self_improving_outreach.config import reset_settings_cache

    reset_settings_cache()
    runner = CliRunner()
    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0, result.stdout
    assert "sk-secret-boundless" not in result.stdout
    assert "sk-secret-openai" not in result.stdout
    assert "lk-secret" not in result.stdout
    assert "sk-secret-one" not in result.stdout
    assert "secret-conn" not in result.stdout
    assert "boundless_configured" in result.stdout
    assert "research_provider" in result.stdout
