"""Runtime configuration loaded from environment variables.

Secrets are never hard-coded; they are read from the environment only and held
as ``SecretStr`` so they do not appear in reprs or logs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

DataMode = Literal["mock", "real"]
LLMProviderName = Literal["none", "gemini", "groq"]

# backend/.sectors_local — git-ignored ledger, cache and recordings of real Sectors data.
DEFAULT_SECTORS_LOCAL_DIR = Path(__file__).resolve().parents[1] / ".sectors_local"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    sectors_data_mode: DataMode = "mock"
    sectors_api_key: SecretStr | None = None
    # Credit guardrails for the real Sectors API (see PHASE.md → credit budget).
    sectors_cache_mode: Literal["readwrite", "replay", "off"] = "readwrite"
    sectors_max_credits_per_day: int = Field(default=60, ge=0)
    sectors_max_credits_total: int = Field(default=700, ge=0)
    sectors_local_dir: Path = DEFAULT_SECTORS_LOCAL_DIR

    # Runtime LLM. "none" runs every decision on the deterministic policies.
    llm_provider: LLMProviderName = "none"
    llm_model: str | None = None  # required for gemini/groq; no built-in default
    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    llm_max_output_tokens: int = Field(default=4096, gt=0, le=65536)

    max_tool_calls: int = Field(default=30, ge=1, le=200)
    max_second_hop: int = Field(default=3, ge=0, le=10)
    max_requeries: int = Field(default=2, ge=0, le=5)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = env.get(name)
            return value if value not in (None, "") else None

        values: dict[str, object] = {
            "sectors_data_mode": get("SECTORS_DATA_MODE"),
            "sectors_api_key": get("SECTORS_API_KEY"),
            "sectors_cache_mode": get("SECTORS_CACHE_MODE"),
            "sectors_max_credits_per_day": get("SECTORS_MAX_CREDITS_PER_DAY"),
            "sectors_max_credits_total": get("SECTORS_MAX_CREDITS_TOTAL"),
            "sectors_local_dir": get("SECTORS_LOCAL_DIR"),
            "llm_provider": get("LLM_PROVIDER"),
            "llm_model": get("LLM_MODEL"),
            "gemini_api_key": get("GEMINI_API_KEY"),
            "groq_api_key": get("GROQ_API_KEY"),
            "llm_timeout_seconds": get("LLM_TIMEOUT_SECONDS"),
            "llm_temperature": get("LLM_TEMPERATURE"),
            "llm_max_output_tokens": get("LLM_MAX_OUTPUT_TOKENS"),
            "max_tool_calls": get("AGENT_MAX_TOOL_CALLS"),
            "max_second_hop": get("AGENT_MAX_SECOND_HOP"),
            "max_requeries": get("AGENT_MAX_REQUERIES"),
        }
        return cls(**{k: v for k, v in values.items() if v is not None})


# Repository root (…/idx-insight-agent/.env); config.py lives in backend/idx_insight/.
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_env_file(path: Path = DEFAULT_ENV_FILE) -> list[str]:
    """Load ``KEY=VALUE`` lines from a local ``.env`` file into ``os.environ``.

    For local development only. Variables already set in the real environment
    (e.g. on Vercel) always win. Missing file → no-op. Returns the names that were
    loaded — never the values.
    """
    if not path.is_file():
        return []
    loaded = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
