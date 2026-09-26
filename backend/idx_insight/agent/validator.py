"""Evidence Validator: decides which claims the briefing may state.

Errors reject a claim; warnings keep it but are surfaced to the user.
"""

from __future__ import annotations

from datetime import date, timedelta

from idx_insight.agent.state import AgentState, ValidationIssue, ValidationReport
from idx_insight.analytics.metrics import METRICS
from idx_insight.analytics.periods import prior_year_period, quarter_label
from idx_insight.models import Claim

STALE_QUARTER_DAYS = 270  # a quarter older than ~3 reporting cycles
STALE_YEARS = 1  # annual ratios older than last full year


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
            report.status = "failed" if self.state.intent and self.state.intent.name != "discovery" else "passed"
        elif not report.accepted:
            report.status = "failed"
        elif report.rejected:
            report.status = "partial"
        else:
            report.status = "passed"
        self.state.validation = report
        return report

    def _check(self, claim: Claim) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        def issue(code: str, detail: str, severity: str = "error") -> None:
            issues.append(ValidationIssue(claim_id=claim.claim_id, code=code,  # type: ignore[arg-type]
                                          severity=severity, detail=detail))  # type: ignore[arg-type]

        evidence = [self.state.evidence.get(e) for e in claim.evidence_ids]
        if not claim.evidence_ids or any(e is None for e in evidence):
            issue("missing_source", "Klaim tidak memiliki bukti yang dapat ditelusuri")
            return issues

        if claim.metric is not None and claim.metric not in METRICS:
            issue("unsupported_metric", f"Metrik {claim.metric} tidak didukung data Sectors")

        for ev in evidence:
            assert ev is not None
            if ev.symbol is not None and ev.symbol not in claim.symbols:
                issue("wrong_company", f"Bukti {ev.evidence_id} milik {ev.symbol}, bukan "
                                       f"{', '.join(claim.symbols)}")

        if claim.kind == "metric":
            for ev in evidence:
                if ev and ev.period != claim.period:
                    issue("wrong_period", f"Bukti {ev.evidence_id} periode {ev.period}, "
                                          f"klaim periode {claim.period}")
        elif claim.kind in ("calculation", "trend") and claim.period:
            allowed = {claim.period, prior_year_period(claim.period)}
            for ev in evidence:
                if ev and ev.period not in allowed:
                    issue("wrong_period", f"Bukti {ev.evidence_id} periode {ev.period} di luar "
                                          f"{sorted(allowed)}")
        elif claim.kind == "comparison":
            periods = set((claim.meta.get("periods") or {}).values())
            if claim.period is None or periods != {claim.period}:
                issue("wrong_period", "Perbandingan memakai periode berbeda antar emiten: "
                      + ", ".join(f"{s} {quarter_label(p)}"
                                  for s, p in (claim.meta.get("periods") or {}).items()))
            if len(claim.symbols) < 2:
                issue("insufficient_evidence", "Perbandingan butuh minimal dua emiten")
        elif claim.kind == "event":
            tf = self.state.timeframe
            if tf and claim.period:
                d = date.fromisoformat(claim.period)
                in_window = tf.start <= d <= tf.end or tf.filings_start <= d <= tf.filings_end
                if not in_window:
                    issue("wrong_period", f"Tanggal peristiwa {claim.period} di luar jendela waktu")

        if claim.kind == "calculation":
            for name in claim.required_inputs:
                ev_id = claim.input_evidence.get(name)
                ev = self.state.evidence.get(ev_id) if ev_id else None
                if ev is None or ev.value is None:
                    issue("calculation_without_inputs",
                          f"Input '{name}' untuk perhitungan tidak memiliki bukti bernilai")

        for conflict in self.state.conflicts:
            if conflict.metric == claim.metric and conflict.symbol in claim.symbols and (
                claim.period is None or conflict.period == claim.period
            ):
                issue("contradictory_values", conflict.detail)

        if claim.kind != "event" and claim.period and _is_stale(claim.period, self.state.as_of):
            issue("stale_data", f"Data periode {quarter_label(claim.period)} sudah lama",
                  severity="warning")
        return issues
