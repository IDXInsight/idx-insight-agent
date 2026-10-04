"""Agent behaviour with a (mock) runtime LLM: decisions, guards and fallbacks."""

from idx_insight.agent.prompts import PlanProposal
from idx_insight.agent.relevance import GUARANTEED_SECOND_HOP
from idx_insight.config import Settings
from idx_insight.llm.errors import LLMTimeoutError
from idx_insight.llm.mock import MockLLMProvider

DISCOVERY_Q = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"
TOOL = "request_financial_context"


def event_id(state, symbol, event_type=None):
    return next(e.event_id for e in state.relevant_events
                if e.symbol == symbol and (event_type is None or e.event_type == event_type))


def researched(state):
    return {c.args["symbol"] for c in state.tool_calls if c.tool == "fetch-quarterly-financials"}


def test_rules_only_mode_makes_no_llm_calls(run):
    state = run(DISCOVERY_Q)
    assert state.llm_calls == []
    assert {d.source for d in state.second_hop} == {"rules"}


def test_most_material_events_are_guaranteed_even_if_llm_adds_nothing(run):
    # Found in live testing: the model once skipped the top-scoring BBNI event.
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls()})
    state = run(DISCOVERY_Q, llm=llm)
    research = [d for d in state.second_hop if d.decision == "research"]
    assert [d.symbol for d in research] == ["BBNI", "BBRI"][:GUARANTEED_SECOND_HOP]
    assert {d.source for d in research} == {"rules"}
    assert all(d.decision == "skip" and d.source == "llm"
               for d in state.second_hop if d.event_id not in state.selected_events
               and d.decision != "reuse")
    assert researched(state) == {"BBNI", "BBRI"}


def test_llm_adds_second_hop_research_through_a_tool_call(run):
    baseline = run(DISCOVERY_Q)
    bbtn = event_id(baseline, "BBTN")  # score 40: below the rule threshold of 50
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls(
        (TOOL, {"event_id": bbtn, "category": "ownership_shift"}))})
    state = run(DISCOVERY_Q, llm=llm)

    added = next(d for d in state.second_hop if d.symbol == "BBTN")
    assert (added.decision, added.source, added.category) == ("research", "llm", "ownership_shift")
    # Guaranteed events are not offered to the model; the rest are.
    request = next(r for r in llm.requests if r.purpose == "second_hop")
    offered = request.tools[0].parameters["properties"]["event_id"]["enum"]
    assert event_id(state, "BBNI", "ownership_change") not in offered and bbtn in offered
    assert request.tools[0].parameters["properties"]["category"]["enum"] == [
        "dividend_capacity", "ownership_shift", "governance_decision", "corporate_action_context"]
    # Sectors access still goes through SectorsService.
    assert researched(state) == {"BBNI", "BBRI", "BBTN"}


def test_second_hop_prompt_excludes_source_supplied_event_titles(run):
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls()})
    state = run(DISCOVERY_Q, llm=llm)
    prompt = next(r for r in llm.requests if r.purpose == "second_hop").messages[-1].content
    assert all(event.title not in prompt for event in state.relevant_events)


def test_llm_second_hop_still_obeys_company_cap(run):
    baseline = run(DISCOVERY_Q)
    calls = [(TOOL, {"event_id": e.event_id, "category": "ownership_shift"})
             for e in baseline.relevant_events]
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls(*calls)})
    state = run(DISCOVERY_Q, llm=llm, settings=Settings(max_second_hop=1))
    assert [d.decision for d in state.second_hop].count("research") == 1
    assert any("Batas second-hop" in d.reason for d in state.second_hop)


def test_unknown_event_id_from_llm_is_ignored(run):
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls(
        (TOOL, {"event_id": "evt-x", "category": "ownership_shift"}))})
    state = run(DISCOVERY_Q, llm=llm)
    assert any(t.stage == "LLM second-hop request ignored" for t in state.trace)
    assert not any(d.decision == "research" and d.source == "llm" for d in state.second_hop)


def test_malformed_tool_call_falls_back_to_rules(run):
    # Missing the required category (and an extra field) → rejected by the schema.
    llm = MockLLMProvider({"second_hop": MockLLMProvider.tool_calls((TOOL, {"event_id": "x",
                                                                          "why": "trust me"}))})
    state = run(DISCOVERY_Q, llm=llm)
    assert {d.source for d in state.second_hop} == {"rules"}
    assert any(c.purpose == "second_hop" and c.status == "invalid_structured_output"
               for c in state.llm_calls)
    assert any(t.stage == "LLM fallback" for t in state.trace)


def test_llm_plan_is_used_and_provider_timeout_is_survivable(run):
    steps = ["discover_events", "rank_relevance", "second_hop_context", "validate_evidence",
             "synthesize"]
    llm = MockLLMProvider({
        "plan": MockLLMProvider.structured(PlanProposal(steps=steps, rationale="full")),
        "synthesis": LLMTimeoutError("gemini request timed out after 20s"),
    })
    state = run(DISCOVERY_Q, llm=llm)
    assert state.plan.source == "llm" and state.plan.names == steps
    # second_hop is unscripted → provider unavailable → rule-based selection
    assert {d.source for d in state.second_hop} == {"rules"}
    assert state.briefing.synthesis_mode == "template"
    assert [(c.purpose, c.status) for c in state.llm_calls] == [
        ("plan", "ok"), ("second_hop", "unavailable"), ("synthesis", "timeout")]
    assert state.status == "completed"


def test_llm_calls_per_request_are_bounded(run):
    state = run(DISCOVERY_Q, llm=MockLLMProvider())  # every call fails → rules everywhere
    assert len(state.llm_calls) <= 4
    assert all(c.status == "unavailable" for c in state.llm_calls)
    assert state.briefing is not None
