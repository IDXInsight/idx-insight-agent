"""Agent behaviour with a (mock) runtime LLM: decisions, guards and fallbacks."""

from idx_insight.agent.prompts import PlanProposal
from idx_insight.llm.errors import LLMTimeoutError
from idx_insight.llm.mock import MockLLMProvider

DISCOVERY_Q = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"
TOOL = "request_financial_context"


def event_id(state, symbol):
    return next(e.event_id for e in state.relevant_events if e.symbol == symbol)


def test_rules_only_mode_makes_no_llm_calls(run):
    state = run(DISCOVERY_Q)
    assert state.llm_calls == []
    assert {d.source for d in state.second_hop} == {"rules"}


def test_llm_chooses_second_hop_through_a_tool_call(run):
    baseline = run(DISCOVERY_Q)
    bbtn = event_id(baseline, "BBTN")  # score 40: below the rule threshold of 50
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls((TOOL, {"event_id": bbtn}))})
    state = run(DISCOVERY_Q, llm=llm)

    decisions = {(d.symbol, d.decision) for d in state.second_hop}
    assert ("BBTN", "research") in decisions
    assert ("BBNI", "research") not in decisions
    assert {d.source for d in state.second_hop} == {"llm"}
    # The tool offered to the model only lists the relevant candidates.
    request = next(r for r in llm.requests if r.purpose == "second_hop")
    assert request.tools[0].parameters["properties"]["event_id"]["enum"] == [
        e.event_id for e in state.relevant_events]
    # Sectors access still goes through SectorsService, for BBTN only.
    researched = {c.args["symbol"] for c in state.tool_calls if c.tool == "fetch-quarterly-financials"}
    assert researched == {"BBTN"}


def test_llm_choosing_no_tool_means_no_second_hop(run):
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls()})
    state = run(DISCOVERY_Q, llm=llm)
    assert all(d.decision == "skip" and d.source == "llm" for d in state.second_hop)
    assert not any(c.tool == "fetch-quarterly-financials" for c in state.tool_calls)


def test_llm_second_hop_still_obeys_company_cap(run):
    from idx_insight.config import Settings

    baseline = run(DISCOVERY_Q)
    calls = [(TOOL, {"event_id": e.event_id}) for e in baseline.relevant_events]
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls(*calls)})
    state = run(DISCOVERY_Q, llm=llm, settings=Settings(max_second_hop=1))
    assert [d.decision for d in state.second_hop].count("research") == 1
    assert any("Batas second-hop" in d.reason for d in state.second_hop)


def test_unknown_event_id_from_llm_is_ignored(run):
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls((TOOL, {"event_id": "evt-x"}))})
    state = run(DISCOVERY_Q, llm=llm)
    assert any(t.stage == "LLM second-hop request ignored" for t in state.trace)
    assert not any(d.decision == "research" for d in state.second_hop)


def test_malformed_tool_call_falls_back_to_rules(run):
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls((TOOL, {"event": "x"}))})
    state = run(DISCOVERY_Q, llm=llm)
    assert {d.source for d in state.second_hop} == {"rules"}
    assert any(c.purpose == "second_hop" and c.status == "invalid_structured_output"
               for c in state.llm_calls)
    assert any(t.stage == "LLM fallback" for t in state.trace)


def test_llm_plan_is_used_and_provider_timeout_is_survivable(run):
    steps = ["discover_events", "rank_relevance", "validate_evidence", "synthesize"]
    llm = MockLLMProvider({
        "plan": MockLLMProvider.structured(PlanProposal(steps=steps, rationale="list only")),
        "synthesis": LLMTimeoutError("gemini request timed out after 20s"),
    })
    state = run(DISCOVERY_Q, llm=llm)
    assert state.plan.source == "llm" and state.plan.names == steps
    assert state.second_hop == []
    assert state.briefing.synthesis_mode == "template"
    assert [(c.purpose, c.status) for c in state.llm_calls] == [
        ("plan", "ok"), ("synthesis", "timeout")]
    assert state.status == "completed"


def test_llm_calls_per_request_are_bounded(run):
    state = run(DISCOVERY_Q, llm=MockLLMProvider())  # every call fails → rules everywhere
    assert len(state.llm_calls) <= 4
    assert all(c.status == "unavailable" for c in state.llm_calls)
    assert state.briefing is not None
