"""Shared HTTP transport for REST-based providers.

Maps transport failures and HTTP status codes onto normalised ``LLMError``s.
Request bodies and headers are never logged or put into error messages.
"""

from __future__ import annotations

from typing import Any

import httpx

from idx_insight.llm.errors import (
    LLMAuthenticationError,
    LLMError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    scrub,
)


def _provider_message(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        return str(error.get("message", "")) if isinstance(error, dict) else str(error)
    except ValueError:
        return ""


def post_json(client: httpx.Client, url: str, *, headers: dict[str, str],
              body: dict[str, Any], timeout: float, provider: str,
              secret: str) -> dict[str, Any]:
    try:
        response = client.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.TimeoutException:
        raise LLMTimeoutError(f"{provider} request timed out after {timeout:g}s") from None
    except httpx.HTTPError as exc:
        raise LLMUnavailableError(f"{provider} unreachable ({type(exc).__name__})") from None

    status = response.status_code
    if status >= 400:
        detail = scrub(_provider_message(response), secret)
        message = f"{provider} HTTP {status}" + (f": {detail}" if detail else "")
        error_cls: type[LLMError]
        if status in (401, 403):
            error_cls = LLMAuthenticationError
        elif status == 429:
            error_cls = LLMRateLimitError
        elif status in (408, 504):
            error_cls = LLMTimeoutError
        elif status >= 500 or status == 498:  # 498: Groq flex-tier capacity exceeded
            error_cls = LLMUnavailableError
        else:
            error_cls = LLMInvalidRequestError
        raise error_cls(message)

    try:
        data = response.json()
    except ValueError:
        raise LLMResponseError(f"{provider} returned a non-JSON body") from None
    if not isinstance(data, dict):
        raise LLMResponseError(f"{provider} returned an unexpected body")
    return data
