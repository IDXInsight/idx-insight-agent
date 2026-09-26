import json
from datetime import date

import pytest
from conftest import AS_OF

from idx_insight.agent.state import AgentState, Conflict, Intent, Timeframe
from idx_insight.agent.synthesis import guard_narrative
from idx_insight.agent.validator import EvidenceValidator
from idx_insight.llm.mock import MockLLMProvider

# --- validator (unit) ----------------------------------------------------------


@pytest.fixture
def state():
    s = AgentState(query="q", as_of=AS_OF, intent=Intent(name="peer_comparison", confidence="high"))
    s.timeframe = Timeframe(start=date(2026, 9, 28), end=date(2026, 10, 4), label="w",
                            direction="forward", filings_start=date(2026, 9, 12),
                            filings_end=AS_OF)
    s.add_evidence(call_id="call-001", tool="fetch-company-report", symbol="BBCA", period="2025",
                   field="profitability.roe", value=0.235, unit="ratio", source_ref="r")
    s.add_evidence(call_id="call-002", tool="fetch-company-report", symbol="BBRI", period="2025",
                   field="profitability.roe", value=0.18, unit="ratio", source_ref="r")
    s.add_evidence(call_id="call-003", tool="fetch-quarterly-financials", symbol="BBCA",
                   period="2026-06-30", field="earnings", value=None, unit="IDR", source_ref="r")
    return s


def codes(state, claim):
    report = EvidenceValidator(state).validate()
    return {i.code for i in report.issues if i.claim_id == claim.claim_id}


def test_valid_metric_claim_passes(state):
    claim = state.add_claim(kind="metric", statement="ROE BBCA 2025", symbols=["BBCA"],
                            metric="roe", period="2025", evidence_ids=["ev-001"])
    assert codes(state, claim) == set()
    assert state.validation.status == "passed"


def test_missing_source(state):
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="roe",
                            period="2025", evidence_ids=["ev-999"])
    assert codes(state, claim) == {"missing_source"}
    assert state.validation.status == "failed"


def test_wrong_company(state):
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="roe",
                            period="2025", evidence_ids=["ev-002"])
    assert "wrong_company" in codes(state, claim)


def test_wrong_period(state):
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="roe",
                            period="2024", evidence_ids=["ev-001"])
    assert "wrong_period" in codes(state, claim)


def test_unsupported_metric(state):
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="npl",
                            period="2025", evidence_ids=["ev-001"])
    assert "unsupported_metric" in codes(state, claim)


def test_calculation_without_inputs(state):
    claim = state.add_claim(kind="calculation", statement="x", symbols=["BBCA"],
                            metric="earnings_growth_yoy", period="2026-06-30",
                            evidence_ids=["ev-003"], required_inputs=["current", "previous"],
                            input_evidence={"current": "ev-003"})
    assert codes(state, claim) == {"calculation_without_inputs"}


def test_comparison_needs_two_companies_and_one_period(state):
    single = state.add_claim(kind="comparison", statement="x", symbols=["BBCA"], metric="roe",
                             period="2025", evidence_ids=["ev-001"],
                             meta={"periods": {"BBCA": "2025"}})
    mixed = state.add_claim(kind="comparison", statement="y", symbols=["BBCA", "BBRI"],
                            metric="roe", period=None, evidence_ids=["ev-001", "ev-002"],
                            meta={"periods": {"BBCA": "2025", "BBRI": "2024"}})
    report = EvidenceValidator(state).validate()
    by_claim = {}
    for i in report.issues:
        by_claim.setdefault(i.claim_id, set()).add(i.code)
    assert "insufficient_evidence" in by_claim[single.claim_id]
    assert "wrong_period" in by_claim[mixed.claim_id]


def test_contradictory_values(state):
    state.conflicts.append(Conflict(symbol="BBCA", metric="roe", period="2025",
                                    values={"a": 0.2, "b": 0.3}, detail="conflict"))
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="roe",
                            period="2025", evidence_ids=["ev-001"])
    assert codes(state, claim) == {"contradictory_values"}


def test_stale_data_is_a_warning_not_a_rejection(state):
    state.add_evidence(call_id="call-004", tool="fetch-company-report", symbol="BBCA",
                       period="2023", field="profitability.roe", value=0.2, unit="ratio",
                       source_ref="r")
    claim = state.add_claim(kind="metric", statement="x", symbols=["BBCA"], metric="roe",
                            period="2023", evidence_ids=["ev-004"])
    report = EvidenceValidator(state).validate()
    assert claim.claim_id in report.accepted
    assert [i.code for i in report.issues] == ["stale_data"]


def test_event_outside_window_is_rejected(state):
    state.add_evidence(call_id="call-005", tool="fetch-corporate-actions", symbol="BBCA",
                       period="2026-12-02", field="corporate_actions.dividend_ex",
                       value="2026-12-02", unit="date", source_ref="r")
    claim = state.add_claim(kind="event", statement="x", symbols=["BBCA"], period="2026-12-02",
                            evidence_ids=["ev-004"])
    assert "wrong_period" in codes(state, claim)


# --- synthesis guard -------------------------------------------------------------

FACTS = ["ROE BBCA 2025: 23.5%", "ROE BBRI 2025: 18.0%"]


def test_guard_accepts_grounded_narrative():
    text = "ROE BBCA 2025 sebesar 23.5%, lebih tinggi dari BBRI (18.0%). Ini bukan rekomendasi beli."
    assert guard_narrative(text, FACTS) is None


def test_guard_rejects_advice_language():
    assert "advice" in guard_narrative("Sebaiknya investor beli BBCA.", FACTS)


def test_guard_rejects_ungrounded_numbers():
    assert "ungrounded" in guard_narrative("ROE BBCA mencapai 25.1% pada 2025.", FACTS)


# --- agent-level behaviour ----------------------------------------------------------


def test_grounded_llm_narrative_is_used(run):
    llm = MockLLMProvider(
        {"synthesis": MockLLMProvider.text("Profitabilitas BBCA menonjol di antara peer.")})
    state = run("Bandingkan ROE BBCA dan BBRI", llm=llm)
    assert state.briefing.synthesis_mode == "llm"
    assert state.briefing.narrative.startswith("Profitabilitas")


def test_ungrounded_llm_narrative_falls_back_to_template(run):
    llm = MockLLMProvider({"synthesis": MockLLMProvider.text("ROE BBCA 31.2%, sebaiknya dibeli.")})
    state = run("Bandingkan ROE BBCA dan BBRI", llm=llm)
    assert state.briefing.synthesis_mode == "template"
    assert state.briefing.narrative is None
    assert any(t.stage == "LLM narrative rejected" for t in state.trace)


def test_llm_only_sees_validated_facts(run):
    llm = MockLLMProvider()  # records requests; unscripted replies fall back to templates
    run("Bandingkan BBCA dan BMRI dari sisi pertumbuhan", llm=llm)
    prompt = next(r for r in llm.requests if r.purpose == "synthesis").messages[-1].content
    # BMRI growth is contradictory and must not reach the LLM as a fact.
    facts_block = prompt.split("Kesenjangan data:")[0]
    assert "Pertumbuhan laba YoY BMRI" not in facts_block


def test_advice_request_gets_boundary_note(run):
    state = run("Apakah BBCA layak dibeli?")
    assert "tidak memberi rekomendasi" in state.briefing.boundary_note
    text = json.dumps(state.briefing.model_dump(), ensure_ascii=False).lower()
    assert "sebaiknya" not in text


def test_trace_is_concise_and_state_is_serializable(run):
    state = run("Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?")
    stages = [t.stage for t in state.trace]
    assert stages[:3] == ["Entities resolved", "Intent resolved", "Timeframe resolved"]
    assert "Evidence validated" in stages and stages[-1] == "Response synthesized"
    restored = AgentState.model_validate_json(state.model_dump_json())
    assert restored.relevant_events == state.relevant_events
    assert restored.tool_calls == state.tool_calls
