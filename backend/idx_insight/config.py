"""Runtime configuration loaded from environment variables.

Secrets are never hard-coded; they are read from the environment only.
"""

from __future__ import annotations

import os
from typing import Literal, Mapping

from pydantic import BaseModel, Field, SecretStr

DataMode = Literal["mock", "real"]
LLMProvider = Literal["offline", "anthropic"]


class Settings(BaseModel):
    sectors_data_mode: DataMode = "mock"
    sectors_api_key: SecretStr | None = None
    llm_provider: LLMProvider = "offline"
    llm_model: str = "claude-opus-5"
    max_tool_calls: int = Field(default=30, ge=1, le=200)
    max_second_hop: int = Field(default=3, ge=0, le=10)
    max_requeries: int = Field(default=2, ge=0, le=5)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env

        def get(name: str) -> str | None:
            value = env.get(name)
            return value if value not in (None, "") else None

        values: dict[str, object] = {
            "sectors_data_mode": get("SECTORS_DATA_MODE"),
            "sectors_api_key": get("SECTORS_API_KEY"),
            "llm_provider": get("LLM_PROVIDER"),
            "llm_model": get("LLM_MODEL"),
            "max_tool_calls": get("AGENT_MAX_TOOL_CALLS"),
            "max_second_hop": get("AGENT_MAX_SECOND_HOP"),
            "max_requeries": get("AGENT_MAX_REQUERIES"),
        }
        return cls(**{k: v for k, v in values.items() if v is not None})
