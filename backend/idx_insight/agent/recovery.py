"""Shared recovery bookkeeping for failed Sectors calls.

Retries happen (bounded) inside ``SectorsService``; by the time a failure
reaches the agent the decision is to continue without that datum and say so.
"""

from __future__ import annotations

from idx_insight.agent.i18n import t
from idx_insight.agent.state import AgentState, RecoveryAction

_GAP_KIND = {
    "not_found": "unknown_company",
    "malformed": "malformed_data",
    "budget_exhausted": "budget_exhausted",
    "credit_cap": "budget_exhausted",
}

_ACTION_KEY = {
    "not_found": "recovery.action.not_found",
    "malformed": "recovery.action.malformed",
    "budget_exhausted": "recovery.action.budget",
    "credit_cap": "recovery.action.credit_cap",
}


def record_tool_failure(state: AgentState, what: str, status: str,
                        symbol: str | None = None) -> None:
    lang = state.language
    kind = _GAP_KIND.get(status, "tool_error")
    state.recovery.append(RecoveryAction(
        trigger=kind,  # type: ignore[arg-type]
        target=what,
        action=t(lang, _ACTION_KEY.get(status, "recovery.action.retry")),
        outcome=t(lang, "recovery.outcome.continue"),
    ))
    # One plain message for the credit cap, however many calls it stopped.
    detail = (t(lang, "gap.credit_cap") if status == "credit_cap"
              else t(lang, "gap.tool_failure", what=what, status=status))
    state.add_gap(kind, detail, None if status == "credit_cap" else symbol)
