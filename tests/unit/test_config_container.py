"""Tests for container timeout configuration validation."""

import pytest

from forge.config import Settings


@pytest.fixture(autouse=True)
def clear_container_env(monkeypatch):
    monkeypatch.delenv("CONTAINER_TIMEOUT", raising=False)
    monkeypatch.delenv("CONTAINER_COMMAND_TIMEOUT", raising=False)
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("CONTAINER_LLM_MODEL", raising=False)
    monkeypatch.delenv("MODEL_CONNECTIONS", raising=False)
    monkeypatch.delenv("MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("MODEL_POLICY", raising=False)


def make_settings(**kwargs) -> Settings:
    kwargs.setdefault("llm_backend", "vertex-ai")
    kwargs.setdefault("llm_model", "gemini-3.5-flash")
    kwargs.setdefault("google_cloud_project", "test-project")
    return Settings(_env_file=None, **kwargs)


class TestContainerTimeoutConfig:
    def test_command_timeout_within_container_timeout_is_valid(self) -> None:
        settings = make_settings(container_timeout=1800, container_command_timeout=600)
        assert settings.container_command_timeout == 600

    def test_command_timeout_equal_to_container_timeout_is_valid(self) -> None:
        settings = make_settings(container_timeout=600, container_command_timeout=600)
        assert settings.container_command_timeout == 600

    def test_command_timeout_exceeding_container_timeout_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not exceed container_timeout"):
            make_settings(container_timeout=1800, container_command_timeout=2000)

    def test_non_positive_command_timeout_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            make_settings(container_command_timeout=0)
