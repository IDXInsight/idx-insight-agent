"""LLM runtime."""

from idx_insight.config import Settings
from idx_insight.llm.base import LLMClient, OfflineLLM


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        from idx_insight.llm.anthropic_client import AnthropicLLM

        return AnthropicLLM(model=settings.llm_model)
    return OfflineLLM()


__all__ = ["LLMClient", "OfflineLLM", "build_llm"]
