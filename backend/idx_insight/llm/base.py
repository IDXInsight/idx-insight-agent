"""LLM runtime interface.

The agent depends only on this interface. A provider returns ``None`` whenever it
cannot give a trustworthy answer (unavailable, API error, refusal, truncation);
the agent then falls back to its deterministic policy — it never blocks on the LLM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


class LLMClient(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def structured(self, *, system: str, user: str, schema: type[M]) -> M | None:
        """Return an instance of ``schema`` or ``None``."""

    @abstractmethod
    def generate(self, *, system: str, user: str) -> str | None:
        """Return free text or ``None``."""


class OfflineLLM(LLMClient):
    """Deterministic no-network runtime: always defers to the rule-based policy."""

    name = "offline"

    @property
    def available(self) -> bool:
        return False

    def structured(self, *, system: str, user: str, schema: type[M]) -> M | None:
        return None

    def generate(self, *, system: str, user: str) -> str | None:
        return None
