"""Groq provider (Groq Chat Completions REST API).

References: https://console.groq.com/docs/api-reference,
https://console.groq.com/docs/structured-outputs, https://console.groq.com/docs/tool-use
- ``POST /openai/v1/chat/completions`` with a bearer API key
- structured output via ``response_format.json_schema`` with ``strict: true``
  (constrained decoding; only on models Groq lists as supporting it)
- tool calls come back with JSON-encoded ``function.arguments``

Groq's endpoint is OpenAI-compatible; that detail stays inside this module.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from idx_insight.llm.base import LLMProvider
from idx_insight.llm.errors import LLMConfigurationError, LLMResponseError
from idx_insight.llm.http import post_json
from idx_insight.llm.types import (
    FinishReason,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
)

BASE_URL = "https://api.groq.com/openai/v1"

_FINISH: dict[str, FinishReason] = {
    "stop": "stop", "length": "length", "tool_calls": "tool_calls",
    "content_filter": "content_filter",
}


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, *, api_key: str, model: str, timeout: float = 20.0,
                 client: httpx.Client | None = None) -> None:
        if not api_key:
            raise LLMConfigurationError("GROQ_API_KEY is not set")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is not set")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = client or httpx.Client()

    def _body(self, request: LLMRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            body["max_completion_tokens"] = request.max_output_tokens
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": request.schema_name, "strict": True,
                                "schema": request.response_schema},
            }
        if request.tools:
            body["tools"] = [
                {"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.parameters}}
                for t in request.tools
            ]
        return body

    def generate(self, request: LLMRequest) -> LLMResponse:
        data = post_json(
            self._client, f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"}, body=self._body(request),
            timeout=self.timeout, provider=self.name, secret=self._api_key,
        )
        return self._normalise(data)

    def _normalise(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            raise LLMResponseError("groq returned no choices")
        choice = choices[0]
        message = choice.get("message") or {}
        reason = choice.get("finish_reason") or ""
        if reason == "content_filter":
            raise LLMResponseError("groq stopped generation (content_filter)")

        calls: list[LLMToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                args = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                raise LLMResponseError("groq returned tool arguments that are not JSON") from None
            if not isinstance(args, dict) or not function.get("name"):
                raise LLMResponseError("groq returned an invalid tool call")
            calls.append(LLMToolCall(id=call.get("id"), name=function["name"], arguments=args))

        usage = data.get("usage") or {}
        return LLMResponse(
            provider=self.name,
            model=self.model,
            text=message.get("content") or None,
            tool_calls=calls,
            finish_reason=_FINISH.get(reason, "other"),
            usage=LLMUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ) if usage else None,
        )
