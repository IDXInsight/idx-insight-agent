"""LLM layer: types, structured output, providers (via fake HTTP), mock, factory, gateway.

No test here needs an API key, quota or network access.
"""

import json

import httpx
import pytest
from conftest import gateway
from pydantic import BaseModel, ValidationError

from idx_insight.agent.prompts import IntentProposal, PlanProposal
from idx_insight.config import Settings
from idx_insight.llm import build_llm_provider
from idx_insight.llm.errors import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMResponseError,
    LLMStructuredOutputError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from idx_insight.llm.gemini import GeminiProvider
from idx_insight.llm.groq import GroqProvider
from idx_insight.llm.mock import MockLLMProvider
from idx_insight.llm.structured import json_schema_for, parse_structured
from idx_insight.llm.types import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolDefinition,
)

KEY = "test-key-123456"
TOOL = LLMToolDefinition(name="pick", description="pick one",
                         parameters={"type": "object", "properties": {"id": {"type": "string"}},
                                     "required": ["id"], "additionalProperties": False})


def request(purpose="test", **kwargs) -> LLMRequest:
    return LLMRequest(purpose=purpose, messages=[LLMMessage(role="system", content="sys"),
                                                LLMMessage(role="user", content="hi")], **kwargs)


class Recorder:
    """httpx transport that records the request and replies with a canned response."""

    def __init__(self, status=200, body=None, exc=None):
        self.status, self.body, self.exc = status, body, exc
        self.request: httpx.Request | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.request = req
        if self.exc:
            raise self.exc
        if isinstance(self.body, str):
            return httpx.Response(self.status, text=self.body)
        return httpx.Response(self.status, json=self.body)

    @property
    def sent(self) -> dict:
        return json.loads(self.request.content)


def gemini(transport: Recorder) -> GeminiProvider:
    return GeminiProvider(api_key=KEY, model="gemini-test",
                          client=httpx.Client(transport=httpx.MockTransport(transport)))


def groq(transport: Recorder) -> GroqProvider:
    return GroqProvider(api_key=KEY, model="openai/gpt-oss-120b",
                        client=httpx.Client(transport=httpx.MockTransport(transport)))


# --- types & structured output ---------------------------------------------------


def test_request_rejects_schema_and_tools_together():
    with pytest.raises(ValidationError):
        request(response_schema={"type": "object"}, tools=[TOOL])


def test_json_schema_is_strict_mode_compatible():
    schema = json_schema_for(PlanProposal)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"steps", "rationale"}
    assert "$defs" not in json.dumps(schema) and "title" not in schema
    intent = json_schema_for(IntentProposal)
    assert "default" not in json.dumps(intent)
    assert set(intent["required"]) == {"intent", "skip_second_hop", "rationale"}


def _reply(text, finish="stop"):
    return LLMResponse(provider="p", model="m", text=text, finish_reason=finish)


def test_parse_structured_accepts_valid_json_and_code_fences():
    ok = parse_structured(_reply('```json\n{"intent": "discovery", "rationale": "r"}\n```'),
                          IntentProposal)
    assert ok.intent == "discovery"


@pytest.mark.parametrize("text, finish, message", [
    (None, "stop", "empty"),
    ("not json", "stop", "not valid JSON"),
    ("[1, 2]", "stop", "not an object"),
    ('{"intent": "buy", "rationale": "r"}', "stop", "does not match schema"),
    ('{"intent": "discovery"', "length", "truncated"),
])
def test_parse_structured_rejects_malformed_output(text, finish, message):
    with pytest.raises(LLMStructuredOutputError, match=message):
        parse_structured(_reply(text, finish), IntentProposal)


# --- Gemini ------------------------------------------------------------------------


GEMINI_OK = {
    "candidates": [{"content": {"role": "model", "parts": [
        {"text": "thinking...", "thought": True}, {"text": '{"a": 1}'}]},
        "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 5, "totalTokenCount": 16},
}


def test_gemini_request_shape_and_normalisation():
    rec = Recorder(body=GEMINI_OK)
    response = gemini(rec).generate(request(response_schema={"type": "object"}, temperature=0.1,
                                            max_output_tokens=256))
    assert rec.request.url.path == "/v1beta/models/gemini-test:generateContent"
    assert rec.request.headers["x-goog-api-key"] == KEY
    body = rec.sent
    assert body["systemInstruction"] == {"parts": [{"text": "sys"}]}
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hi"}]}]
    assert body["generationConfig"] == {
        "temperature": 0.1, "maxOutputTokens": 256,
        "responseFormat": {"text": {"mimeType": "APPLICATION_JSON", "schema": {"type": "object"}}},
    }
    assert response.text == '{"a": 1}'  # thought parts are dropped
    assert response.finish_reason == "stop"
    assert response.usage.input_tokens == 11 and response.usage.total_tokens == 16


def test_gemini_function_calls_are_normalised():
    rec = Recorder(body={"candidates": [{"content": {"parts": [
        {"functionCall": {"id": "c1", "name": "pick", "args": {"id": "x"}}}]},
        "finishReason": "STOP"}]})
    response = gemini(rec).generate(request(tools=[TOOL]))
    decl = rec.sent["tools"][0]["functionDeclarations"][0]
    assert decl["name"] == "pick" and decl["parametersJsonSchema"] == TOOL.parameters
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].name == "pick" and response.tool_calls[0].arguments == {"id": "x"}


@pytest.mark.parametrize("body, message", [
    ({"promptFeedback": {"blockReason": "SAFETY"}}, "blocked"),
    ({"candidates": []}, "no candidates"),
    ({"candidates": [{"finishReason": "SAFETY"}]}, "SAFETY"),
    ({"candidates": [{"finishReason": "MALFORMED_FUNCTION_CALL"}]}, "malformed function"),
])
def test_gemini_unusable_payloads(body, message):
    with pytest.raises(LLMResponseError, match=message):
        gemini(Recorder(body=body)).generate(request())


# --- Groq --------------------------------------------------------------------------


def test_groq_request_shape_and_normalisation():
    rec = Recorder(body={"choices": [{"message": {"role": "assistant", "content": '{"a": 1}'},
                                      "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}})
    response = groq(rec).generate(request(response_schema={"type": "object"},
                                          max_output_tokens=128, temperature=0.0))
    assert str(rec.request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert rec.request.headers["authorization"] == f"Bearer {KEY}"
    body = rec.sent
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["max_completion_tokens"] == 128 and body["temperature"] == 0.0
    assert body["response_format"] == {"type": "json_schema", "json_schema": {
        "name": "response", "strict": True, "schema": {"type": "object"}}}
    assert response.text == '{"a": 1}' and response.usage.output_tokens == 4


def test_groq_tool_calls_are_normalised():
    rec = Recorder(body={"choices": [{"message": {"tool_calls": [
        {"id": "call_1", "type": "function",
         "function": {"name": "pick", "arguments": "{\"id\": \"x\"}"}}]},
        "finish_reason": "tool_calls"}]})
    response = groq(rec).generate(request(tools=[TOOL]))
    assert rec.sent["tools"] == [{"type": "function", "function": {
        "name": "pick", "description": "pick one", "parameters": TOOL.parameters}}]
    assert response.tool_calls[0].arguments == {"id": "x"}
    assert response.finish_reason == "tool_calls"


def test_groq_tool_arguments_that_are_not_json_are_rejected():
    rec = Recorder(body={"choices": [{"message": {"tool_calls": [
        {"id": "c", "function": {"name": "pick", "arguments": "{id: x"}}]},
        "finish_reason": "tool_calls"}]})
    with pytest.raises(LLMResponseError, match="not JSON"):
        groq(rec).generate(request(tools=[TOOL]))


# --- HTTP error normalisation (shared transport) -----------------------------------


@pytest.mark.parametrize("status, error", [
    (401, LLMAuthenticationError), (403, LLMAuthenticationError), (429, LLMRateLimitError),
    (400, LLMInvalidRequestError), (498, LLMUnavailableError), (503, LLMUnavailableError),
    (504, LLMTimeoutError),
])
@pytest.mark.parametrize("make", [gemini, groq])
def test_http_errors_are_normalised(make, status, error):
    body = {"error": {"message": f"bad key {KEY}", "type": "invalid_request_error"}}
    with pytest.raises(error) as info:
        make(Recorder(status=status, body=body)).generate(request())
    assert KEY not in str(info.value)  # provider text is scrubbed


@pytest.mark.parametrize("make", [gemini, groq])
def test_timeout_and_network_errors(make):
    with pytest.raises(LLMTimeoutError):
        make(Recorder(exc=httpx.ReadTimeout("slow"))).generate(request())
    with pytest.raises(LLMUnavailableError):
        make(Recorder(exc=httpx.ConnectError("down"))).generate(request())


@pytest.mark.parametrize("make", [gemini, groq])
def test_non_json_body_is_malformed(make):
    with pytest.raises(LLMResponseError):
        make(Recorder(body="<html>oops</html>")).generate(request())


# --- factory & configuration -------------------------------------------------------


def test_factory_none_means_rules_only():
    assert build_llm_provider(Settings()) is None


@pytest.mark.parametrize("provider, key_field, cls", [
    ("gemini", "gemini_api_key", GeminiProvider), ("groq", "groq_api_key", GroqProvider)])
def test_factory_selects_configured_provider(provider, key_field, cls):
    llm = build_llm_provider(Settings(llm_provider=provider, llm_model="m", **{key_field: "k"}))
    assert isinstance(llm, cls) and llm.model == "m"


@pytest.mark.parametrize("settings, message", [
    (Settings(llm_provider="gemini", gemini_api_key="k"), "LLM_MODEL"),
    (Settings(llm_provider="groq", llm_model="m"), "GROQ_API_KEY"),
    (Settings(llm_provider="gemini", llm_model="m", groq_api_key="k"), "GEMINI_API_KEY"),
])
def test_factory_rejects_incomplete_configuration(settings, message):
    # No silent fallback to another provider's key or quota.
    with pytest.raises(LLMConfigurationError, match=message):
        build_llm_provider(settings)


# --- mock provider -----------------------------------------------------------------


def test_mock_provider_scripts_sequences_and_errors():
    mock = MockLLMProvider({"plan": [MockLLMProvider.text("a"), LLMRateLimitError("slow down")]})
    assert mock.generate(request("plan")).text == "a"
    with pytest.raises(LLMRateLimitError):
        mock.generate(request("plan"))
    with pytest.raises(LLMUnavailableError, match="no scripted reply"):
        mock.generate(request("other"))
    assert mock.purposes() == ["plan", "plan", "other"]


# --- agent gateway -----------------------------------------------------------------


class Pick(BaseModel):
    id: str


def test_gateway_records_usage_without_content():
    reply = MockLLMProvider.structured(IntentProposal(intent="discovery", rationale="secret plan"))
    reply.usage = None
    llm = gateway(MockLLMProvider({"intent": reply}))
    assert llm.decide("intent", system="s", user="u", schema=IntentProposal).intent == "discovery"
    record = llm.state.llm_calls[0]
    assert (record.purpose, record.provider, record.model, record.status) == (
        "intent", "mock", "mock-model", "ok")
    assert "secret plan" not in record.model_dump_json()


def test_gateway_validates_tool_calls():
    ok = gateway(MockLLMProvider({"t": MockLLMProvider.tool_calls(("pick", {"id": "x"}))}))
    calls = ok.call_tools("t", system="s", user="u", tools=[TOOL], args_schema={"pick": Pick})
    assert calls[0][0] == "pick" and calls[0][1].id == "x"

    unknown = gateway(MockLLMProvider({"t": MockLLMProvider.tool_calls(("drop_table", {}))}))
    assert unknown.call_tools("t", system="s", user="u", tools=[TOOL],
                              args_schema={"pick": Pick}) is None
    assert unknown.state.llm_calls[0].status == "invalid_structured_output"

    bad_args = gateway(MockLLMProvider({"t": MockLLMProvider.tool_calls(("pick", {"id": 3}))}))
    assert bad_args.call_tools("t", system="s", user="u", tools=[TOOL],
                               args_schema={"pick": Pick}) is None


def test_gateway_rejects_empty_text_and_caps_calls():
    llm = gateway(MockLLMProvider({"s": MockLLMProvider.text("   ")}))
    assert llm.write("s", system="s", user="u") is None
    for _ in range(10):
        llm.write("s", system="s", user="u")
    assert len(llm.state.llm_calls) == 4  # MAX_LLM_CALLS per request
    assert not llm.enabled
