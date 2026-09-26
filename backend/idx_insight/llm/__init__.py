"""Provider-agnostic runtime LLM layer.

Agent Brain → ``LLMProvider`` interface (``llm.base`` + ``llm.types``) →
provider implementation (Gemini, Groq, or the test mock).
"""

from idx_insight.config import Settings
from idx_insight.llm.base import LLMProvider
from idx_insight.llm.errors import LLMConfigurationError


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Provider selected by ``LLM_PROVIDER``; ``None`` means rules-only mode.

    No silent fallback between providers: a misconfigured provider raises
    ``LLMConfigurationError`` instead of quietly using another one.
    """
    provider = settings.llm_provider
    if provider == "none":
        return None
    if not settings.llm_model:
        raise LLMConfigurationError(f"LLM_MODEL must be set when LLM_PROVIDER={provider}")
    if provider == "gemini":
        from idx_insight.llm.gemini import GeminiProvider

        key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
        return GeminiProvider(api_key=key, model=settings.llm_model,
                              timeout=settings.llm_timeout_seconds)
    if provider == "groq":
        from idx_insight.llm.groq import GroqProvider

        key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
        return GroqProvider(api_key=key, model=settings.llm_model,
                            timeout=settings.llm_timeout_seconds)
    raise LLMConfigurationError(f"unknown LLM_PROVIDER {provider!r}")


__all__ = ["LLMProvider", "build_llm_provider"]
