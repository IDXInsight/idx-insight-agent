import pytest
from pydantic import ValidationError

from idx_insight.config import Settings


def test_defaults_are_safe_without_environment():
    settings = Settings.from_env({})
    assert settings.sectors_data_mode == "mock"
    assert settings.llm_provider == "offline"
    assert settings.sectors_api_key is None


def test_reads_environment_values():
    settings = Settings.from_env(
        {"LLM_PROVIDER": "anthropic", "AGENT_MAX_TOOL_CALLS": "12", "SECTORS_API_KEY": "secret"}
    )
    assert settings.llm_provider == "anthropic"
    assert settings.max_tool_calls == 12
    # Secret values must not leak through repr/str.
    assert "secret" not in repr(settings)


def test_rejects_unknown_data_mode():
    with pytest.raises(ValidationError):
        Settings.from_env({"SECTORS_DATA_MODE": "production"})
