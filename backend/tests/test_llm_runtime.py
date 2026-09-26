from types import SimpleNamespace

import pytest

from idx_insight.agent.prompts import IntentProposal
from idx_insight.config import Settings
from idx_insight.llm import OfflineLLM, build_llm

anthropic = pytest.importorskip("anthropic")
from idx_insight.llm.anthropic_client import AnthropicLLM  # noqa: E402


class FakeMessages:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.kwargs = response, exc, None

    def _respond(self, **kwargs):
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.response

    parse = create = _respond


def llm_with(response=None, exc=None):
    messages = FakeMessages(response, exc)
    return AnthropicLLM(model="claude-opus-5", client=SimpleNamespace(messages=messages)), messages


def test_build_llm_defaults_to_offline():
    assert isinstance(build_llm(Settings()), OfflineLLM)


def test_structured_output_is_returned():
    parsed = IntentProposal(intent="discovery", rationale="r")
    llm, messages = llm_with(SimpleNamespace(stop_reason="end_turn", parsed_output=parsed))
    assert llm.structured(system="s", user="u", schema=IntentProposal) == parsed
    assert messages.kwargs["output_format"] is IntentProposal
    assert messages.kwargs["model"] == "claude-opus-5"


def test_refusal_falls_back_to_none():
    llm, _ = llm_with(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    assert llm.structured(system="s", user="u", schema=IntentProposal) is None


def test_truncated_text_falls_back_to_none():
    llm, _ = llm_with(SimpleNamespace(stop_reason="max_tokens", content=[]))
    assert llm.generate(system="s", user="u") is None


def test_text_blocks_are_joined():
    content = [SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=" Halo ")]
    llm, _ = llm_with(SimpleNamespace(stop_reason="end_turn", content=content))
    assert llm.generate(system="s", user="u") == "Halo"


def test_connection_error_falls_back_to_none():
    exc = anthropic.APIConnectionError(request=SimpleNamespace(method="POST", url="x"))
    llm, _ = llm_with(exc=exc)
    assert llm.generate(system="s", user="u") is None
