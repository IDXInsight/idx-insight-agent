"""Explicit, serializable agent state.

Everything the agent decides or retrieves for one request lives here — no hidden
globals. ``AgentState.model_dump()`` is the full record of a run.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from idx_insight.models import Claim, Event, Evidence, MetricValue
from idx_insight.sectors.service import ToolCallRecord

IntentName = Literal["discovery", "peer_comparison", "company_context", "clarify"]

PlanStepName = Literal[
    "discover_events",
    "rank_relevance",
    "second_hop_context",
    "retrieve_financial_context",
    "compare_peers",
    "company_trends",
    "validate_evidence",
    "synthesize",
]

RunStatus = Literal["completed", "partial", "needs_clarification", "insufficient_evidence"]


class Intent(BaseModel):
    name: IntentName
    confidence: Literal["high", "low"]
    source: Literal["rules", "llm"] = "rules"
    advice_requested: bool = False
    metric_bundles: list[str] = []
    metrics: list[str] = []
    unsupported_metrics: list[str] = []
    skip_second_hop: bool = False


class ResolvedCompany(BaseModel):
    symbol: str
    matched_text: str
    method: Literal["ticker", "alias", "sector_member"]
    company_name: str | None = None


class AmbiguousMention(BaseModel):
    text: str
    candidates: list[str]


class Entities(BaseModel):
    companies: list[ResolvedCompany] = []
    ambiguous: list[AmbiguousMention] = []
    unknown: list[str] = []
    sub_sector: str | None = None
    sector_text: str | None = None

    @property
    def symbols(self) -> list[str]:
        return [c.symbol for c in self.companies]


class Timeframe(BaseModel):
    start: date
    end: date
    label: str
    direction: Literal["forward", "backward", "around"]
    assumed: bool = False
    note: str | None = None
    # Filings are historical records; a forward window pairs with a lookback.
    filings_start: date
    filings_end: date
    # Requested financial period ("2025" or "2026-03-31"), if any.
    financial_period: str | None = None


class PlanStep(BaseModel):
    name: PlanStepName
    reason: str


class Plan(BaseModel):
    steps: list[PlanStep]
    source: Literal["rules", "llm"]
    rejected_llm_plan: str | None = None

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.steps]


class SecondHopDecision(BaseModel):
    event_id: str
    symbol: str
    decision: Literal["research", "reuse", "skip"]
    reason: str
    metrics: list[str] = []


class RecoveryAction(BaseModel):
    trigger: Literal[
        "ambiguous_company", "unknown_company", "ambiguous_timeframe", "missing_data",
        "incomplete_response", "tool_error", "empty_result", "conflicting_data",
        "insufficient_evidence", "budget_exhausted", "unsupported_metric",
    ]
    target: str
    action: str
    outcome: str


class DataGap(BaseModel):
    kind: str
    symbol: str | None = None
    detail: str


class Conflict(BaseModel):
    symbol: str
    metric: str
    period: str
    values: dict[str, float]  # evidence_id -> value
    detail: str


class ValidationIssue(BaseModel):
    claim_id: str
    code: Literal[
        "missing_source", "wrong_company", "wrong_period", "unsupported_metric",
        "contradictory_values", "insufficient_evidence", "stale_data",
        "calculation_without_inputs",
    ]
    severity: Literal["error", "warning"]
    detail: str


class ValidationReport(BaseModel):
    status: Literal["passed", "partial", "failed", "not_run"] = "not_run"
    accepted: list[str] = []
    rejected: list[str] = []
    issues: list[ValidationIssue] = []


class TraceStep(BaseModel):
    stage: str
    status: Literal["ok", "warning", "skipped", "error"] = "ok"
    detail: str = ""


class Finding(BaseModel):
    text: str
    claim_ids: list[str]


class BriefingSection(BaseModel):
    heading: str
    findings: list[Finding]


class Briefing(BaseModel):
    title: str
    summary: str
    sections: list[BriefingSection] = []
    data_gaps: list[str] = []
    assumptions: list[str] = []
    boundary_note: str
    narrative: str | None = None
    synthesis_mode: Literal["template", "llm"] = "template"
    clarification_question: str | None = None


class AgentState(BaseModel):
    query: str
    as_of: date
    watchlist: list[str] = []
    requested_sub_sector: str | None = None

    intent: Intent | None = None
    entities: Entities = Field(default_factory=Entities)
    timeframe: Timeframe | None = None
    plan: Plan | None = None

    discovered_events: list[Event] = []
    duplicate_events: list[Event] = []
    relevant_events: list[Event] = []
    selected_events: list[str] = []  # event ids chosen for second-hop
    second_hop: list[SecondHopDecision] = []

    evidence: dict[str, Evidence] = {}
    metric_values: list[MetricValue] = []
    analytics: dict[str, Any] = {}
    conflicts: list[Conflict] = []
    claims: list[Claim] = []
    validation: ValidationReport = Field(default_factory=ValidationReport)

    data_gaps: list[DataGap] = []
    recovery: list[RecoveryAction] = []
    requeries_used: int = 0
    assumptions: list[str] = []

    tool_calls: list[ToolCallRecord] = []
    trace: list[TraceStep] = []
    briefing: Briefing | None = None
    status: RunStatus = "completed"

    # -- helpers ---------------------------------------------------------------

    def add_trace(self, stage: str, detail: str = "", status: str = "ok") -> None:
        self.trace.append(TraceStep(stage=stage, detail=detail, status=status))  # type: ignore[arg-type]

    def add_evidence(self, **fields: Any) -> Evidence:
        ev = Evidence(evidence_id=f"ev-{len(self.evidence) + 1:03d}", **fields)
        self.evidence[ev.evidence_id] = ev
        return ev

    def add_claim(self, **fields: Any) -> Claim:
        claim = Claim(claim_id=f"cl-{len(self.claims) + 1:03d}", **fields)
        self.claims.append(claim)
        return claim

    def add_gap(self, kind: str, detail: str, symbol: str | None = None) -> None:
        if not any(g.kind == kind and g.detail == detail for g in self.data_gaps):
            self.data_gaps.append(DataGap(kind=kind, symbol=symbol, detail=detail))
