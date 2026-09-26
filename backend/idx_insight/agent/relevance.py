"""Relevance Engine and second-hop decisions.

Second-hop selection is hybrid:
- rules guarantee that the most material events (top scores, distinct companies)
  are researched, so the answer never misses the headline event;
- the LLM may add further events through the ``request_financial_context`` tool,
  choosing a reason category from a fixed list (never free text);
- code enforces the per-request company cap and the tool-call budget.
Without an LLM, every event at or above the score threshold is eligible.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from idx_insight.agent.i18n import t
from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.prompts import SECOND_HOP_SYSTEM, second_hop_user_prompt
from idx_insight.agent.state import AgentState, RecoveryAction, SecondHopDecision
from idx_insight.analytics.events import (
    RELEVANT_THRESHOLD,
    SECOND_HOP_THRESHOLD,
    RelevanceContext,
    dedupe,
    event_density,
    score_event,
)
from idx_insight.analytics.metrics import EVENT_CONTEXT_METRICS
from idx_insight.analytics.numbers import fmt_share_pct
from idx_insight.llm.types import LLMToolDefinition
from idx_insight.models import Event

# Estimated Sectors calls to research one company: company report, latest quarter
# and the same quarter one year earlier.
SECOND_HOP_CALL_COST = 3
# Most material events researched regardless of the LLM's choice.
GUARANTEED_SECOND_HOP = 2

ReasonCategory = Literal["dividend_capacity", "ownership_shift", "governance_decision",
                         "corporate_action_context"]
CATEGORIES: tuple[str, ...] = ReasonCategory.__args__  # type: ignore[attr-defined]

_DEFAULT_CATEGORY: dict[str, str] = {
    "dividend_ex": "dividend_capacity",
    "dividend_payment": "dividend_capacity",
    "agm": "governance_decision",
    "ownership_change": "ownership_shift",
    "stock_split": "corporate_action_context",
}


def render_reason(state: AgentState, code: str, params: dict) -> str:
    if "pct" in params:
        params = {**params, "pct": fmt_share_pct(params["pct"], state.language)}
    return t(state.language, f"reason.{code}", **params)


def rank_events(state: AgentState, events: list[Event]) -> list[Event]:
    """Deduplicate, score and keep events at or above the relevance threshold."""
    unique, duplicates = dedupe(events)
    state.duplicate_events = duplicates
    ctx = RelevanceContext(
        watchlist=frozenset(state.watchlist) | frozenset(
            c.symbol for c in state.entities.companies if c.method != "sector_member"),
        density=event_density(unique),
    )
    scored = []
    for ev in unique:
        score, reasons = score_event(ev, ctx)
        rendered = [render_reason(state, code, params) for code, params in reasons]
        scored.append(ev.model_copy(update={"relevance_score": score,
                                            "relevance_reasons": rendered}))
    state.discovered_events = scored
    relevant = [e for e in scored if e.relevance_score >= RELEVANT_THRESHOLD]
    relevant.sort(key=lambda e: (-e.relevance_score, e.event_date, e.symbol))
    state.relevant_events = relevant
    return relevant


class ContextRequest(BaseModel):
    """Arguments of the ``request_financial_context`` tool."""

    model_config = ConfigDict(extra="forbid")
    event_id: str
    category: ReasonCategory


CONTEXT_TOOL = "request_financial_context"


def _guaranteed(state: AgentState) -> list[str]:
    """Top-scoring events above the second-hop threshold, one per company."""
    chosen, companies = [], set()
    for ev in state.relevant_events:  # already sorted by score
        if ev.relevance_score < SECOND_HOP_THRESHOLD or ev.symbol in companies:
            continue
        chosen.append(ev.event_id)
        companies.add(ev.symbol)
        if len(chosen) == GUARANTEED_SECOND_HOP:
            break
    return chosen


def _llm_additions(state: AgentState, llm: AgentLLM,
                   guaranteed: list[str]) -> dict[str, str] | None:
    """Extra events the LLM wants researched → category; None → use the rules."""
    candidates = [ev for ev in state.relevant_events if ev.event_id not in guaranteed]
    if not llm.enabled or not candidates:
        return None
    ids = [ev.event_id for ev in candidates]
    tool = LLMToolDefinition(
        name=CONTEXT_TOOL,
        description="Fetch the latest earnings growth and ROE of the company behind one "
                    "event, when that context is needed to explain why the event matters.",
        parameters={
            "type": "object",
            "properties": {"event_id": {"type": "string", "enum": ids},
                           "category": {"type": "string", "enum": list(CATEGORIES)}},
            "required": ["event_id", "category"],
            "additionalProperties": False,
        },
    )

    def line(ev: Event) -> str:
        return (f"{ev.event_id} | {ev.event_date} | {ev.symbol} | {ev.event_type} | "
                f"{ev.title} | score {ev.relevance_score}")

    by_id = {ev.event_id: ev for ev in state.relevant_events}
    calls = llm.call_tools(
        "second_hop", system=SECOND_HOP_SYSTEM,
        user=second_hop_user_prompt(state.query, [line(by_id[i]) for i in guaranteed],
                                    [line(ev) for ev in candidates]),
        tools=[tool], args_schema={CONTEXT_TOOL: ContextRequest},
    )
    if calls is None:
        return None
    requested: dict[str, str] = {}
    for _, args in calls:
        requested.setdefault(args.event_id, args.category)  # type: ignore[attr-defined]
    invalid = [i for i in requested if i not in ids]
    if invalid:
        state.add_trace("LLM second-hop request ignored",
                        t(state.language, "trace.llm_ignored", n=len(invalid)), "warning")
    return {i: c for i, c in requested.items() if i in ids}


def decide_second_hop(state: AgentState, budget_remaining: int, max_companies: int,
                      llm: AgentLLM) -> list[str]:
    """Decide, per relevant event, whether follow-up financial research is justified.

    Returns the symbols to research; every decision is recorded with its reason,
    source (``rules`` or ``llm``) and reason category.
    """
    lang = state.language
    guaranteed = _guaranteed(state)
    additions = _llm_additions(state, llm, guaranteed)
    llm_decided = additions is not None
    if additions is None:  # rules-only: every other event above the threshold
        additions = {ev.event_id: _DEFAULT_CATEGORY[ev.event_type] for ev in state.relevant_events
                     if ev.relevance_score >= SECOND_HOP_THRESHOLD and ev.event_id not in guaranteed}

    def decide(ev: Event, decision: str, reason: str, source: str,
               category: str | None = None, metrics: list[str] | None = None) -> None:
        state.second_hop.append(SecondHopDecision(
            event_id=ev.event_id, symbol=ev.symbol, decision=decision,  # type: ignore[arg-type]
            reason=reason, source=source, category=category,  # type: ignore[arg-type]
            metrics=metrics or [],
        ))

    researched: list[str] = []
    budget = budget_remaining
    for ev in state.relevant_events:
        if ev.event_id in guaranteed:
            source, category = "rules", _DEFAULT_CATEGORY[ev.event_type]
        elif ev.event_id in additions:
            source, category = ("llm" if llm_decided else "rules"), additions[ev.event_id]
        else:
            if llm_decided:
                decide(ev, "skip", t(lang, "hop.skip.llm"), "llm")
            else:
                decide(ev, "skip", t(lang, "hop.skip.threshold", score=ev.relevance_score,
                                     threshold=SECOND_HOP_THRESHOLD), "rules")
            continue

        if ev.symbol in researched:
            decide(ev, "reuse", t(lang, "hop.reuse"), source, category, EVENT_CONTEXT_METRICS)
        elif len(researched) >= max_companies:
            decide(ev, "skip", t(lang, "hop.skip.cap", cap=max_companies), source, category)
        elif budget < SECOND_HOP_CALL_COST:
            decide(ev, "skip", t(lang, "hop.skip.budget"), source, category)
            state.recovery.append(RecoveryAction(
                trigger="budget_exhausted", target=f"second-hop {ev.symbol}",
                action=t(lang, "hop.budget.action"), outcome=t(lang, "hop.budget.outcome"),
            ))
            state.add_gap("budget_exhausted", t(lang, "gap.budget_second_hop", sym=ev.symbol),
                          ev.symbol)
        else:
            budget -= SECOND_HOP_CALL_COST
            researched.append(ev.symbol)
            state.selected_events.append(ev.event_id)
            decide(ev, "research", t(lang, f"hop.why.{category}"), source, category,
                   EVENT_CONTEXT_METRICS)
    return researched
