"""Normalised LLM errors. Providers map their failures onto these classes.

Messages must never contain credentials; providers pass only status codes and
provider error text through ``scrub``.
"""

from __future__ import annotations


class LLMError(Exception):
    kind = "error"
    retryable = False


class LLMConfigurationError(LLMError):
    """Missing API key, missing model, or unknown provider."""

    kind = "configuration"


class LLMAuthenticationError(LLMError):
    kind = "authentication"


class LLMRateLimitError(LLMError):
    kind = "rate_limit"
    retryable = True


class LLMTimeoutError(LLMError):
    kind = "timeout"
    retryable = True


class LLMUnavailableError(LLMError):
    """Provider overloaded, 5xx, or network failure."""

    kind = "unavailable"
    retryable = True


class LLMInvalidRequestError(LLMError):
    kind = "invalid_request"


class LLMResponseError(LLMError):
    """The provider answered, but the payload is unusable (blocked, empty, malformed)."""

    kind = "malformed_response"


class LLMStructuredOutputError(LLMError):
    """The reply does not validate against the requested schema."""

    kind = "invalid_structured_output"


def scrub(text: str, *secrets: str | None, limit: int = 300) -> str:
    """Remove secrets from provider-supplied text and cap its length."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text[:limit]
