import pytest
from conftest import AS_OF
from fastapi.testclient import TestClient

from idx_insight.api.app import app, get_agent_service, get_settings
from idx_insight.api.service import AgentService
from idx_insight.config import Settings
from idx_insight.llm.mock import MockLLMProvider
from idx_insight.sectors import MockSectorsAdapter

DISCOVERY_Q = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"


@pytest.fixture
def client():
    settings = Settings()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_agent_service] = lambda: AgentService(settings)
    yield TestClient(app)
    app.dependency_overrides.clear()


def post(client, query, **extra):
    return client.post("/v1/agent/query",
                       json={"query": query, "as_of": AS_OF.isoformat(), **extra})


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["data_mode"] == "mock"


def test_capabilities_list_documented_tools_only(client):
    body = client.get("/v1/capabilities").json()
    assert "fetch-filings" in body["sectors_tools"]
    assert "roe" in body["metrics"]
    assert set(body["intents"]) == {"discovery", "peer_comparison", "company_context"}


def test_discovery_query_contract(client):
    response = post(client, DISCOVERY_Q)
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "mock"
    assert body["scope"]["intent"] == "discovery"
    assert body["scope"]["plan"][-1] == "synthesize"
    assert body["events"] and all(e["evidence_ids"] for e in body["events"])
    assert {e["second_hop"] for e in body["events"]} >= {"research", "skip"}
    evidence_ids = {e["evidence_id"] for e in body["evidence"]}
    for claim in body["claims"]:
        assert set(claim["evidence_ids"]) <= evidence_ids
    assert body["trace"][0]["stage"] == "Entities resolved"
    assert body["briefing"]["boundary_note"]


def test_peer_query_returns_comparison(client):
    body = post(client, "Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitability").json()
    assert body["scope"]["intent"] == "peer_comparison"
    assert body["peer_comparison"]["roe"]["highest"] == "BBCA"
    assert body["validation"]["rejected"] >= 1  # BMRI growth conflict


def test_clarification_response(client):
    body = post(client, "Disclosure bank syariah minggu depan").json()
    assert body["status"] == "needs_clarification"
    assert body["scope"]["ambiguous"] == {"bank syariah": ["BRIS", "BTPS"]}
    assert body["tool_calls"] == []


def test_watchlist_is_validated(client):
    assert post(client, DISCOVERY_Q, watchlist=["BBRI.JK"]).status_code == 200
    assert post(client, DISCOVERY_Q, watchlist=["NOT-A-TICKER"]).status_code == 422


def test_query_length_is_validated(client):
    assert post(client, "hi").status_code == 422


def test_llm_provider_is_reported():
    service = AgentService(Settings(), adapter=MockSectorsAdapter(), llm=MockLLMProvider())
    app.dependency_overrides[get_agent_service] = lambda: service
    try:
        body = post(TestClient(app), "Bandingkan ROE BBCA dan BBRI").json()
    finally:
        app.dependency_overrides.clear()
    assert body["llm_provider"] == "mock"


def test_real_mode_is_unavailable_not_faked():
    app.dependency_overrides[get_settings] = lambda: Settings(sectors_data_mode="real")
    try:
        response = post(TestClient(app), DISCOVERY_Q)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "Phase 4" in response.json()["detail"]


def test_response_exposes_evidence_assessment_and_llm_calls(client):
    body = post(client, "Bandingkan pertumbuhan BBCA dan BMRI").json()
    assert body["validation"]["assessment"]["sufficiency"] == "partial"
    assert body["validation"]["assessment"]["conflicting"]
    assert body["llm_calls"] == []  # rules-only mode by default
    assert body["llm_provider"] == "none"


def test_llm_calls_are_reported_without_prompts():
    service = AgentService(Settings(), adapter=MockSectorsAdapter(),
                           llm=MockLLMProvider({"synthesis": MockLLMProvider.structured(
                               {"sentences": [{"text": "Ringkas.", "citations": ["cl-001"]}]})}))
    app.dependency_overrides[get_agent_service] = lambda: service
    try:
        body = post(TestClient(app), "Bandingkan ROE BBCA dan BBRI").json()
    finally:
        app.dependency_overrides.clear()
    calls = {c["purpose"]: c for c in body["llm_calls"]}
    assert calls["synthesis"]["status"] == "ok" and calls["synthesis"]["provider"] == "mock"
    assert set(calls["synthesis"]) == {"purpose", "provider", "model", "status", "latency_ms",
                                       "input_tokens", "output_tokens", "detail"}


@pytest.mark.parametrize("settings, missing", [
    (Settings(llm_provider="groq", llm_model="openai/gpt-oss-120b"), "GROQ_API_KEY"),
    (Settings(llm_provider="gemini", gemini_api_key="AIza-not-a-real-key"), "LLM_MODEL"),
])
def test_misconfigured_llm_returns_503_without_secrets(settings, missing):
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = post(TestClient(app), DISCOVERY_Q)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert missing in response.json()["detail"]
    assert "AIza-not-a-real-key" not in response.text


def test_health_reports_provider_and_model_but_no_keys(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        llm_provider="groq", llm_model="openai/gpt-oss-120b", groq_api_key="gsk-hidden")
    try:
        body = TestClient(app).get("/health").json()
    finally:
        app.dependency_overrides.clear()
    assert body["llm_provider"] == "groq" and body["llm_model"] == "openai/gpt-oss-120b"
    assert "gsk-hidden" not in str(body)
