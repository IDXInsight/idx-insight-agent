"""Shared recovery bookkeeping for failed Sectors calls.

Retries happen (bounded) inside ``SectorsService``; by the time a failure
reaches the agent the decision is to continue without that datum and say so.
"""

from __future__ import annotations

from idx_insight.agent.state import AgentState, RecoveryAction

_GAP_KIND = {
    "not_found": "unknown_company",
    "malformed": "malformed_data",
    "budget_exhausted": "budget_exhausted",
}

_ACTION = {
    "not_found": "Tidak mencoba ulang; kode tidak ada di Sectors",
    "malformed": "Tidak mencoba ulang; respons tidak sesuai skema terdokumentasi",
    "budget_exhausted": "Tidak memanggil tool lagi (batas tool call)",
}


def record_tool_failure(state: AgentState, what: str, status: str,
                        symbol: str | None = None) -> None:
    kind = _GAP_KIND.get(status, "tool_error")
    state.recovery.append(RecoveryAction(
        trigger=kind,  # type: ignore[arg-type]
        target=what,
        action=_ACTION.get(status, "Retry terbatas oleh SectorsService"),
        outcome="Dilanjutkan tanpa data ini",
    ))
    state.add_gap(kind, f"Data {what} tidak dapat diambil ({status}).", symbol)
