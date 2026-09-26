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


def test_env_file_loads_names_without_overriding_real_environment(tmp_path, monkeypatch):
    from idx_insight.config import load_env_file

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nLLM_PROVIDER=groq\nLLM_MODEL=\"openai/gpt-oss-120b\"\n"
        "GROQ_API_KEY=gsk-from-file\nAGENT_MAX_TOOL_CALLS=9\nnot a pair\n",
        encoding="utf-8",
    )
    # Isolated copy of the environment: nothing the loader writes outlives this test.
    import os

    monkeypatch.setattr(os, "environ", {"AGENT_MAX_TOOL_CALLS": "12"})  # real env wins

    loaded = load_env_file(env_file)
    assert loaded == ["LLM_PROVIDER", "LLM_MODEL", "GROQ_API_KEY"]  # names only
    settings = Settings.from_env()
    assert settings.llm_provider == "groq" and settings.llm_model == "openai/gpt-oss-120b"
    assert settings.max_tool_calls == 12


def test_missing_env_file_is_a_no_op(tmp_path):
    from idx_insight.config import load_env_file

    assert load_env_file(tmp_path / "absent.env") == []
