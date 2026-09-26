"""Planner / Router.

The LLM may propose a plan; a deterministic validator accepts it only if every
step is allowed for the intent, required steps are present, the canonical order
is respected and the plan ends with validation then synthesis. Otherwise the
rule-based plan is used. Either way the chosen plan is recorded in state.
"""

from __future__ import annotations

from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import PLAN_SYSTEM, PlanProposal
from idx_insight.agent.state import AgentState, Plan, PlanStep

CANONICAL_ORDER = [
    "retrieve_financial_context",
    "company_trends",
    "compare_peers",
    "discover_events",
    "rank_relevance",
    "second_hop_context",
    "validate_evidence",
    "synthesize",
]

ALLOWED: dict[str, set[str]] = {
    "discovery": {"discover_events", "rank_relevance", "second_hop_context",
                  "validate_evidence", "synthesize"},
    "peer_comparison": {"retrieve_financial_context", "compare_peers",
                        "validate_evidence", "synthesize"},
    "company_context": {"retrieve_financial_context", "company_trends", "discover_events",
                        "rank_relevance", "validate_evidence", "synthesize"},
}

REQUIRED: dict[str, set[str]] = {
    "discovery": {"discover_events", "rank_relevance"},
    "peer_comparison": {"retrieve_financial_context", "compare_peers"},
    "company_context": {"retrieve_financial_context", "company_trends"},
}

_REASONS = {
    "discover_events": "Kumpulkan filing dan aksi korporasi dalam cakupan dan jendela waktu",
    "rank_relevance": "Normalisasi, deduplikasi, dan nilai relevansi peristiwa dengan aturan deterministik",
    "second_hop_context": "Ambil konteks keuangan untuk peristiwa yang cukup material",
    "retrieve_financial_context": "Ambil data keuangan dan rasio dari Sectors",
    "compare_peers": "Selaraskan periode lalu bandingkan metrik antar emiten",
    "company_trends": "Hitung tren kinerja emiten",
    "validate_evidence": "Periksa setiap klaim terhadap bukti",
    "synthesize": "Susun ringkasan faktual dari klaim tervalidasi",
}


def rule_plan(state: AgentState) -> list[str]:
    assert state.intent is not None
    intent = state.intent
    if intent.name == "discovery":
        steps = ["discover_events", "rank_relevance"]
        if not intent.skip_second_hop:
            steps.append("second_hop_context")
    elif intent.name == "peer_comparison":
        steps = ["retrieve_financial_context", "compare_peers"]
    else:
        steps = ["retrieve_financial_context", "company_trends", "discover_events",
                 "rank_relevance"]
    return steps + ["validate_evidence", "synthesize"]


def required_steps(intent: str, skip_second_hop: bool = False) -> set[str]:
    """Steps a plan must contain. Discovery must investigate why events matter
    (second-hop) unless the user explicitly asked for a plain list; which events
    get researched is still decided per event in the second-hop step."""
    required = set(REQUIRED.get(intent, set()))
    if intent == "discovery" and not skip_second_hop:
        required.add("second_hop_context")
    return required


def check_plan(intent: str, steps: list[str], *, skip_second_hop: bool = False) -> str | None:
    """Return a rejection reason, or None when the plan is acceptable."""
    if intent not in ALLOWED:
        return f"intent {intent} has no executable plan"
    extra = [s for s in steps if s not in ALLOWED[intent]]
    if extra:
        return f"steps not allowed for {intent}: {extra}"
    if skip_second_hop and "second_hop_context" in steps:
        return "user asked for a plain list; second_hop_context not allowed"
    missing = required_steps(intent, skip_second_hop) - set(steps)
    if missing:
        return f"required steps missing: {sorted(missing)}"
    if len(set(steps)) != len(steps):
        return "duplicate steps"
    if steps[-2:] != ["validate_evidence", "synthesize"]:
        return "plan must end with validate_evidence, synthesize"
    positions = [CANONICAL_ORDER.index(s) for s in steps]
    if positions != sorted(positions):
        return "steps out of order"
    return None


def build_plan(state: AgentState, llm: AgentLLM) -> Plan:
    assert state.intent is not None
    intent = state.intent.name
    rejected: str | None = None

    if llm.enabled:
        proposal = llm.decide(
            "plan",
            system=PLAN_SYSTEM,
            user=(
                f"Intent: {intent}\n"
                f"Allowed steps (canonical order): "
                f"{[s for s in CANONICAL_ORDER if s in ALLOWED.get(intent, set())]}\n"
                f"Required steps: {sorted(required_steps(intent, state.intent.skip_second_hop))}\n"
                f"Companies: {state.entities.symbols}\nSector: {state.entities.sub_sector}\n"
                f"User asked for plain list only: {state.intent.skip_second_hop}\n"
                f"Query: {state.query}"
            ),
            schema=PlanProposal,
        )
        if proposal is not None:
            rejected = check_plan(intent, list(proposal.steps),
                                  skip_second_hop=state.intent.skip_second_hop)
            if rejected is None:
                return Plan(
                    steps=[PlanStep(name=s, reason=_REASONS[s]) for s in proposal.steps],
                    source="llm",
                )

    steps = rule_plan(state)
    return Plan(
        steps=[PlanStep(name=s, reason=_REASONS[s]) for s in steps],  # type: ignore[arg-type]
        source="rules",
        rejected_llm_plan=rejected,
    )
