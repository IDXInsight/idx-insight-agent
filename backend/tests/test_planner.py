from conftest import AS_OF, gateway

from idx_insight.agent.planner import build_plan, check_plan
from idx_insight.agent.prompts import PlanProposal
from idx_insight.agent.state import AgentState, Intent
from idx_insight.llm.mock import MockLLMProvider


def state_for(intent: str, **intent_kw) -> AgentState:
    return AgentState(query="q", as_of=AS_OF,
                      intent=Intent(name=intent, confidence="high", **intent_kw))


def test_rule_plans_differ_by_intent():
    discovery = build_plan(state_for("discovery"), gateway())
    peer = build_plan(state_for("peer_comparison"), gateway())
    company = build_plan(state_for("company_context"), gateway())
    assert discovery.names == ["discover_events", "rank_relevance", "second_hop_context",
                               "validate_evidence", "synthesize"]
    assert peer.names == ["retrieve_financial_context", "compare_peers", "validate_evidence",
                          "synthesize"]
    assert "discover_events" in company.names and "company_trends" in company.names
    assert discovery.source == "rules"


def test_list_only_discovery_plan_has_no_second_hop():
    plan = build_plan(state_for("discovery", skip_second_hop=True), gateway())
    assert "second_hop_context" not in plan.names


def test_valid_llm_plan_is_accepted():
    steps = ["discover_events", "rank_relevance", "validate_evidence", "synthesize"]
    provider = MockLLMProvider(
        {"plan": MockLLMProvider.structured(PlanProposal(steps=steps, rationale="list only"))})
    plan = build_plan(state_for("discovery", skip_second_hop=True), gateway(provider))
    assert plan.source == "llm" and plan.names == steps


def test_llm_cannot_drop_second_hop_unless_user_asked_for_a_list():
    # Found in live testing: the model skipped second-hop on a normal discovery query.
    steps = ["discover_events", "rank_relevance", "validate_evidence", "synthesize"]
    provider = MockLLMProvider(
        {"plan": MockLLMProvider.structured(PlanProposal(steps=steps, rationale="shorter"))})
    plan = build_plan(state_for("discovery"), gateway(provider))
    assert plan.source == "rules"
    assert "second_hop_context" in plan.names
    assert "second_hop_context" in plan.rejected_llm_plan


def test_list_only_request_rejects_second_hop_in_llm_plan():
    steps = ["discover_events", "rank_relevance", "second_hop_context", "validate_evidence",
             "synthesize"]
    assert "plain list" in check_plan("discovery", steps, skip_second_hop=True)


def test_llm_plan_with_disallowed_step_falls_back_to_rules():
    steps = ["discover_events", "rank_relevance", "compare_peers", "validate_evidence", "synthesize"]
    provider = MockLLMProvider(
        {"plan": MockLLMProvider.structured(PlanProposal(steps=steps, rationale="x"))})
    plan = build_plan(state_for("discovery"), gateway(provider))
    assert plan.source == "rules"
    assert "not allowed" in plan.rejected_llm_plan


def test_plan_checks():
    assert "required" in check_plan("peer_comparison", ["compare_peers", "validate_evidence",
                                                         "synthesize"])
    assert "order" in check_plan("discovery", ["rank_relevance", "discover_events",
                                               "second_hop_context", "validate_evidence",
                                               "synthesize"])
    assert "end with" in check_plan("discovery", ["discover_events", "rank_relevance",
                                                  "second_hop_context", "synthesize"])
    assert check_plan("clarify", ["synthesize"]) is not None
    assert check_plan("peer_comparison", ["retrieve_financial_context", "compare_peers",
                                          "validate_evidence", "synthesize"]) is None
