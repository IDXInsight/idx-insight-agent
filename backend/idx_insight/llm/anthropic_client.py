"""Anthropic (Claude) implementation of ``LLMClient``.

Requires the optional ``anthropic`` package and credentials resolved by the SDK
(e.g. ``ANTHROPIC_API_KEY``). Failures, refusals and truncations return ``None``
so the agent falls back to deterministic behaviour.
"""

from __future__ import annotations

import logging
from typing import Any

from idx_insight.llm.base import LLMClient, M

logger = logging.getLogger(__name__)


class AnthropicLLM(LLMClient):
    name = "anthropic"

    def __init__(self, model: str, client: Any | None = None, max_tokens: int = 16000) -> None:
        import anthropic  # optional dependency: pip install "idx-insight-agent[llm]"

        self._anthropic = anthropic
        self._client = client or anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    @property
    def available(self) -> bool:
        return True

    def _call(self, fn, **kwargs):
        errors = self._anthropic
        try:
            response = fn(
                model=self.model,
                max_tokens=self.max_tokens,
                **kwargs,
            )
        except errors.RateLimitError:
            logger.warning("LLM rate limited; using deterministic fallback")
            return None
        except errors.APIStatusError as exc:
            logger.warning("LLM API error %s; using deterministic fallback", exc.status_code)
            return None
        except errors.APIConnectionError:
            logger.warning("LLM unreachable; using deterministic fallback")
            return None
        if response.stop_reason in ("refusal", "max_tokens"):
            logger.warning("LLM stop_reason=%s; using deterministic fallback", response.stop_reason)
            return None
        return response

    def structured(self, *, system: str, user: str, schema: type[M]) -> M | None:
        response = self._call(
            self._client.messages.parse,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        return None if response is None else response.parsed_output

    def generate(self, *, system: str, user: str) -> str | None:
        response = self._call(
            self._client.messages.create,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if response is None:
            return None
        text = "".join(block.text for block in response.content if block.type == "text")
        return text.strip() or None
