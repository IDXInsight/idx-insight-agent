"""Evidence Validator: decides which claims the briefing may state.

Errors reject a claim; warnings keep it but are surfaced to the user.
"""

from __future__ import annotations

from datetime import date, timedelta

from idx_insight.agent.i18n import t
from idx_insight.agent.state import (
    AgentState,
    EvidenceAssessment,
    ValidationIssue,
    ValidationReport,
)
from idx_insight.analytics.metrics import METRICS
from idx_insight.analytics.periods import prior_year_period, quarter_label
from idx_insight.models import Claim

STALE_QUARTER_DAYS = 270  # a quarter older than ~3 reporting cycles
STALE_YEARS = 1  # annual ratios older than last full year

# Data-gap kinds grouped by what they mean for evidence sufficiency. Kinds not
# listed (e.g. "unsupported_capability", "not_applicable") are informational.
GAP_CATEGORIES = {
    "incomplete": {"incomplete_response", "missing_metric", "scope_truncated",
                   "insufficient_evidence"},
    "unavailable": {"tool_error", "budget_exhausted", "unavailable_period", "unknown_company",
                    "unverified_company", "unknown_sector", "empty_result",
                    "unsupported_metric"},
    "malformed": {"malformed_data"},
}


def _is_stale(period: str, as_of: date) -> bool:
    if len(period) == 4:
        return int(period) < as_of.year - STALE_YEARS
    try:
        return date.fromisoformat(period) < as_of - timedelta(days=STALE_QUARTER_DAYS)
    except ValueError:
        return False


class EvidenceValidator:
    def __init__(self, state: AgentState) -> None:
        self.state = state

    def validate(self) -> ValidationReport:
        report = ValidationReport()
        for claim in self.state.claims:
            issues = self._check(claim)
            report.issues.extend(issues)
            if any(i.severity == "error" for i in issues):
                report.rejected.append(claim.claim_id)
            else:
                report.accepted.append(claim.claim_id)
        if not self.state.claims:
            is_discovery = self.state.intent is not None and self.state.intent.name == "discovery"
            report.status = "passed" if is_discovery else "failed"
        elif not report.accepted:
            report.status = "failed"
        elif report.rejected:
            report.status = "partial"
        else:
            report.status = "passed"
        report.assessment = self._assess(report)
        self.state.validation = report
        return report

    def _assess(self, report: ValidationReport) -> EvidenceAssessment:
        s = self.state
        assessment = EvidenceAssessment(
            conflicting=[c.detail for c in s.conflicts],
            **{cat: [g.detail for g in s.data_gaps if g.kind in kinds]
               for cat, kinds in GAP_CATEGORIES.items()},
        )
        nothing_to_report = (s.intent is not None and s.intent.name == "discovery"
                             and not s.discovered_events and not assessment.unavailable
                             and not assessment.malformed)
        if not report.accepted and not nothing_to_report:
            assessment.sufficiency = "insufficient"
        elif (report.rejected or assessment.incomplete or assessment.conflicting
              or assessment.unavailable or assessment.malformed):
            assessment.sufficiency = "partial"
        else:
            assessment.sufficiency = "sufficient"
        return assessment

    def _check(self, claim: Claim) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        lang = self.state.language

        def issue(code: str, detail: str, severity: str = "error") -> None:
            issues.append(ValidationIssue(claim_id=claim.claim_id, code=code,  # type: ignore[arg-type]
                                          severity=severity, detail=detail))  # type: ignore[arg-type]

        evidence = [self.state.evidence.get(e) for e in claim.evidence_ids]
        if not claim.evidence_ids or any(e is None for e in evidence):
            issue("missing_source", t(lang, "issue.missing_source"))
            return issues

        if claim.metric is not None and claim.metric not in METRICS:
            issue("unsupported_metric", t(lang, "issue.unsupported_metric", metric=claim.metric))

        for ev in evidence:
            assert ev is not None
            if ev.symbol is not None and ev.symbol not in claim.symbols:
                issue("wrong_company", t(lang, "issue.wrong_company", ev=ev.evidence_id,
                                         owner=ev.symbol, claimed=", ".join(claim.symbols)))

        if claim.kind == "metric":
            for ev in evidence:
                if ev and ev.period != claim.period:
                    issue("wrong_period", t(lang, "issue.wrong_period_metric", ev=ev.evidence_id,
                                            ev_period=ev.period, period=claim.period))
        elif claim.kind in ("calculation", "trend") and claim.period:
            allowed = {claim.period, prior_year_period(claim.period)}
            for ev in evidence:
                if ev and ev.period not in allowed:
                    issue("wrong_period", t(lang, "issue.wrong_period_calc", ev=ev.evidence_id,
                                            ev_period=ev.period, allowed=sorted(allowed)))
        elif claim.kind == "comparison":
            periods = set((claim.meta.get("periods") or {}).values())
            if claim.period is None or periods != {claim.period}:
                listed = ", ".join(f"{s} {quarter_label(p)}"
                                   for s, p in (claim.meta.get("periods") or {}).items())
                issue("wrong_period", t(lang, "issue.mixed_periods", periods=listed))
            if len(claim.symbols) < 2:
                issue("insufficient_evidence", t(lang, "issue.min_two"))
        elif claim.kind == "event":
            tf = self.state.timeframe
            if tf and claim.period:
                d = date.fromisoformat(claim.period)
                in_window = tf.start <= d <= tf.end or tf.filings_start <= d <= tf.filings_end
                if not in_window:
                    issue("wrong_period", t(lang, "issue.event_outside", date=claim.period))

        if claim.kind == "calculation":
            for name in claim.required_inputs:
                ev_id = claim.input_evidence.get(name)
                ev = self.state.evidence.get(ev_id) if ev_id else None
                if ev is None or ev.value is None:
                    issue("calculation_without_inputs", t(lang, "issue.missing_input", name=name))

        for conflict in self.state.conflicts:
            if conflict.metric == claim.metric and conflict.symbol in claim.symbols and (
                claim.period is None or conflict.period == claim.period
            ):
                issue("contradictory_values", conflict.detail)

        if claim.kind != "event" and claim.period and _is_stale(claim.period, self.state.as_of):
            issue("stale_data", t(lang, "issue.stale", period=quarter_label(claim.period)),
                  severity="warning")
        return issues
