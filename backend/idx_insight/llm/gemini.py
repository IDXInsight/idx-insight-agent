"""Gemini provider (Google Gemini API, REST ``models.generateContent``).

Reference: https://ai.google.dev/api/generate-content
- auth header ``x-goog-api-key``
- ``systemInstruction`` + ``contents`` (roles ``user`` / ``model``)
- structured output via ``generationConfig.responseFormat.text``
  (``responseSchema`` is deprecated in the reference)
- tools via ``functionDeclarations[].parametersJsonSchema``
"""

from __future__ import annotations

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

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

_FINISH: dict[str, FinishReason] = {"STOP": "stop", "MAX_TOKENS": "length"}
_BLOCKED = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout: float = 20.0,
                 client: httpx.Client | None = None) -> None:
        if not api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not set")
        if not model:
            raise LLMConfigurationError("LLM_MODEL is not set")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = client or httpx.Client()

    def _body(self, request: LLMRequest) -> dict[str, Any]:
        system = "\n\n".join(m.content for m in request.messages if m.role == "system")
        body: dict[str, Any] = {
            "contents": [
                {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
                for m in request.messages if m.role != "system"
            ],
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        config: dict[str, Any] = {}
        if request.temperature is not None:
            config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            config["maxOutputTokens"] = request.max_output_tokens
        if request.response_schema is not None:
            config["responseFormat"] = {
                "text": {"mimeType": "APPLICATION_JSON", "schema": request.response_schema}
            }
        if config:
            body["generationConfig"] = config
        if request.tools:
            body["tools"] = [{"functionDeclarations": [
                {"name": t.name, "description": t.description, "parametersJsonSchema": t.parameters}
                for t in request.tools
            ]}]
        return body

    def generate(self, request: LLMRequest) -> LLMResponse:
        data = post_json(
            self._client, f"{BASE_URL}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self._api_key}, body=self._body(request),
            timeout=self.timeout, provider=self.name, secret=self._api_key,
        )
        return self._normalise(data)

    def _normalise(self, data: dict[str, Any]) -> LLMResponse:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMResponseError(f"gemini blocked the prompt ({block})")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMResponseError("gemini returned no candidates")
        candidate = candidates[0]
        reason = candidate.get("finishReason", "")
        if reason in _BLOCKED:
            raise LLMResponseError(f"gemini stopped generation ({reason})")
        if reason == "MALFORMED_FUNCTION_CALL":
            raise LLMResponseError("gemini produced a malformed function call")

        texts: list[str] = []
        calls: list[LLMToolCall] = []
        for part in (candidate.get("content") or {}).get("parts") or []:
            if part.get("thought"):
                continue  # reasoning summaries are never surfaced
            if "text" in part:
                texts.append(part["text"])
            elif "functionCall" in part:
                call = part["functionCall"]
                args = call.get("args") or {}
                if not isinstance(args, dict) or not call.get("name"):
                    raise LLMResponseError("gemini returned an invalid function call")
                calls.append(LLMToolCall(id=call.get("id"), name=call["name"], arguments=args))

        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            provider=self.name,
            model=self.model,
            text="".join(texts) or None,
            tool_calls=calls,
            finish_reason="tool_calls" if calls else _FINISH.get(reason, "other"),
            usage=LLMUsage(
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
                total_tokens=usage.get("totalTokenCount"),
            ) if usage else None,
        )
