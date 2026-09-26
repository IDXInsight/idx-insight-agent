"""The Agent Brain's single door to the runtime LLM.

- depends only on the provider-neutral interface (``llm.base`` / ``llm.types``)
- validates structured replies and tool calls against explicit schemas
- turns every ``LLMError`` into a recorded, deterministic fallback (``None``)
- records provider, model, latency, status and token usage per call —
  never prompts, replies or credentials
"""

from __future__ import annotations

import logging
import time
from typing import TypeVar

from pydantic import BaseModel

from idx_insight.agent.state import AgentState, LLMCallRecord
from idx_insight.llm.base import LLMProvider
from idx_insight.llm.errors import LLMError, LLMStructuredOutputError
from idx_insight.llm.structured import json_schema_for, parse_structured, validate_payload
from idx_insight.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
)

logger = logging.getLogger("idx_insight.llm")

M = TypeVar("M", bound=BaseModel)

# Upper bound on LLM calls per request (intent, plan, second-hop, synthesis).
MAX_LLM_CALLS = 4


class AgentLLM:
    def __init__(self, provider: LLMProvider | None, state: AgentState, *,
                 temperature: float | None = None, max_output_tokens: int | None = None) -> None:
        self.provider = provider
        self.state = state
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    @property
    def enabled(self) -> bool:
        return self.provider is not None and len(self.state.llm_calls) < MAX_LLM_CALLS

    # -- public decisions ----------------------------------------------------------

    def decide(self, purpose: str, *, system: str, user: str, schema: type[M]) -> M | None:
        """Structured decision validated against ``schema``; None → use the rules."""
        request = self._request(purpose, system, user, response_schema=json_schema_for(schema),
                                schema_name=schema.__name__)
        return self._run(request, lambda response: parse_structured(response, schema))

    def call_tools(self, purpose: str, *, system: str, user: str,
                   tools: list[LLMToolDefinition],
                   args_schema: dict[str, type[BaseModel]]) -> list[tuple[str, BaseModel]] | None:
        """Tool calls validated per tool name; [] means the model chose no tool."""
        request = self._request(purpose, system, user, tools=tools)

        def check(response: LLMResponse) -> list[tuple[str, BaseModel]]:
            return [self._validate_call(call, args_schema) for call in response.tool_calls]

        return self._run(request, check)

    def write(self, purpose: str, *, system: str, user: str) -> str | None:
        request = self._request(purpose, system, user)

        def check(response: LLMResponse) -> str:
            if response.finish_reason == "length" or not (response.text or "").strip():
                raise LLMStructuredOutputError("empty or truncated text reply")
            return response.text.strip()  # type: ignore[union-attr]

        return self._run(request, check)

    # -- internals -------------------------------------------------------------------

    def _request(self, purpose: str, system: str, user: str, **kwargs) -> LLMRequest:
        return LLMRequest(
            purpose=purpose,
            messages=[LLMMessage(role="system", content=system),
                      LLMMessage(role="user", content=user)],
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            **kwargs,
        )

    @staticmethod
    def _validate_call(call: LLMToolCall,
                       args_schema: dict[str, type[BaseModel]]) -> tuple[str, BaseModel]:
        if call.name not in args_schema:
            raise LLMStructuredOutputError(f"model called unknown tool '{call.name}'")
        return call.name, validate_payload(call.arguments, args_schema[call.name])

    def _run(self, request: LLMRequest, check):
        if not self.enabled:
            return None
        assert self.provider is not None
        start = time.perf_counter()
        response: LLMResponse | None = None
        try:
            response = self.provider.generate(request)
            result = check(response)
        except LLMError as exc:
            self._record(request.purpose, start, response, status=exc.kind, detail=str(exc))
            self.state.add_trace("LLM fallback", f"{request.purpose}: {exc.kind}; aturan deterministik "
                                 "dipakai", "warning")
            return None
        self._record(request.purpose, start, response, status="ok")
        return result

    def _record(self, purpose: str, start: float, response: LLMResponse | None, *,
                status: str, detail: str | None = None) -> None:
        assert self.provider is not None
        usage = response.usage if response else None
        record = LLMCallRecord(
            purpose=purpose, provider=self.provider.name, model=self.provider.model,
            status=status, latency_ms=round((time.perf_counter() - start) * 1000, 1),
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            detail=detail,
        )
        self.state.llm_calls.append(record)
        logger.info("llm_call purpose=%s provider=%s model=%s status=%s latency_ms=%s "
                    "input_tokens=%s output_tokens=%s", record.purpose, record.provider,
                    record.model, record.status, record.latency_ms, record.input_tokens,
                    record.output_tokens)
