"""Deterministic mock provider for tests and offline development.

Replies are scripted per request ``purpose``. A script entry is an
``LLMResponse``, an ``LLMError`` (raised), or a list of those consumed in order.
Unscripted purposes raise ``LLMUnavailableError`` so the agent's deterministic
fallback is exercised — the mock never invents an answer.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from idx_insight.llm.base import LLMProvider
from idx_insight.llm.errors import LLMError, LLMUnavailableError
from idx_insight.llm.types import LLMRequest, LLMResponse, LLMToolCall

Scripted = LLMResponse | LLMError


class MockLLMProvider(LLMProvider):
    name = "mock"

    def __init__(self, script: dict[str, Scripted | list[Scripted]] | None = None,
                 model: str = "mock-model") -> None:
        self.model = model
        self._script: dict[str, list[Scripted]] = {
            k: list(v) if isinstance(v, list) else [v] for k, v in (script or {}).items()
        }
        self.requests: list[LLMRequest] = []

    # -- builders for scripts ----------------------------------------------------

    @classmethod
    def structured(cls, value: BaseModel | dict[str, Any]) -> LLMResponse:
        text = value.model_dump_json() if isinstance(value, BaseModel) else json.dumps(value)
        return LLMResponse(provider=cls.name, model="mock-model", text=text, finish_reason="stop")

    @classmethod
    def text(cls, value: str) -> LLMResponse:
        return LLMResponse(provider=cls.name, model="mock-model", text=value, finish_reason="stop")

    @classmethod
    def tool_calls(cls, *calls: tuple[str, dict[str, Any]]) -> LLMResponse:
        return LLMResponse(
            provider=cls.name, model="mock-model", finish_reason="tool_calls",
            tool_calls=[LLMToolCall(id=f"call_{i}", name=n, arguments=a)
                        for i, (n, a) in enumerate(calls)],
        )

    # -- LLMProvider -------------------------------------------------------------

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        queue = self._script.get(request.purpose)
        if not queue:
            raise LLMUnavailableError(f"mock has no scripted reply for '{request.purpose}'")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, LLMError):
            raise item
        return item.model_copy(update={"model": self.model})

    def purposes(self) -> list[str]:
        return [r.purpose for r in self.requests]

