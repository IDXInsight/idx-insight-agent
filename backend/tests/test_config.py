import pytest
from pydantic import ValidationError

from idx_insight.config import Settings


def test_defaults_are_safe_without_environment():
    settings = Settings.from_env({})
    assert settings.sectors_data_mode == "mock"
    assert settings.llm_provider == "none" and settings.llm_model is None
    assert settings.sectors_api_key is None


def test_reads_environment_values():
    settings = Settings.from_env(
        {"LLM_PROVIDER": "groq", "LLM_MODEL": "openai/gpt-oss-120b", "GROQ_API_KEY": "gsk-secret",
         "AGENT_MAX_TOOL_CALLS": "12", "SECTORS_API_KEY": "secret", "LLM_TIMEOUT_SECONDS": "5"}
    )
    assert settings.llm_provider == "groq" and settings.llm_model == "openai/gpt-oss-120b"
    assert settings.llm_timeout_seconds == 5
    assert "gsk-secret" not in repr(settings)
    assert settings.max_tool_calls == 12
    # Secret values must not leak through repr/str.
    assert "secret" not in repr(settings)


def test_rejects_unknown_data_mode():
    with pytest.raises(ValidationError):
        Settings.from_env({"SECTORS_DATA_MODE": "production"})
