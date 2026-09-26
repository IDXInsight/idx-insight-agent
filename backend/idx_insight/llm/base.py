"""Runtime LLM provider interface.

The Agent Brain depends on this interface and the types in ``llm.types`` only.
A deployment may run with no provider at all: the agent then uses its
deterministic policies for every decision.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from idx_insight.llm.types import LLMRequest, LLMResponse


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return a normalised response or raise an ``LLMError`` subclass."""
