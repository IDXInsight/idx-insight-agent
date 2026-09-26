"""Financial context retrieval: Sectors data → evidence → metric values.

Every number produced here is backed by evidence ids pointing at a concrete
tool call. Data problems are recorded as gaps, conflicts or recovery actions in
state rather than silently patched.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from idx_insight.agent.state import AgentState, Conflict, RecoveryAction
from idx_insight.analytics.metrics import METRICS, MetricSpec
from idx_insight.analytics.numbers import normalize_ratio, pct_change, safe_div
from idx_insight.analytics.periods import prior_year_period, quarter_label
from idx_insight.models import MetricValue
from idx_insight.sectors.schemas import CompanyReport, QuarterlyFinancial
from idx_insight.sectors.service import SectorsService

N_QUARTERS = 5  # latest quarter + the same quarter one year earlier
CONFLICT_TOLERANCE = 0.01  # 1 percentage point
BANKING_SUB_SECTOR = "banks"


@dataclass
class _CompanyData:
    report: CompanyReport | None = None
    report_call: str | None = None
    report_loaded: bool = False
    quarters: list[QuarterlyFinancial] | None = None
    quarter_calls: dict[str, str] = field(default_factory=dict)  # quarter date -> call id
    quarters_loaded: bool = False
    values: dict[str, list[MetricValue]] = field(default_factory=dict)


def _get_path(obj: object, path: str) -> float | None:
    for part in path.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj  # type: ignore[return-value]


class FinancialContext:
    def __init__(self, service: SectorsService, state: AgentState, max_requeries: int) -> None:
        self.service = service
        self.state = state
        self.max_requeries = max_requeries
        self._companies: dict[str, _CompanyData] = {}
        self._evidence_index: dict[tuple, str] = {}
        self._requeried: set[tuple[str, str]] = set()

    # -- loading ---------------------------------------------------------------

    def _data(self, symbol: str) -> _CompanyData:
        return self._companies.setdefault(symbol, _CompanyData())

    def report(self, symbol: str) -> CompanyReport | None:
        data = self._data(symbol)
        if data.report_loaded:
            return data.report
        data.report_loaded = True
        result = self.service.company_report(symbol, ("overview", "financials"))
        if result.ok:
            data.report, data.report_call = result.data, result.call_id
        else:
            self._record_failure(symbol, "company report", result.status, result.error)
        return data.report

    def quarters(self, symbol: str) -> list[QuarterlyFinancial] | None:
        data = self._data(symbol)
        if data.quarters_loaded:
            return data.quarters
        data.quarters_loaded = True
        result = self.service.quarterly_financials(symbol, n_quarters=N_QUARTERS)
        if result.ok:
            data.quarters = sorted(result.data or [], key=lambda q: q.date)
            data.quarter_calls = {q.date: result.call_id for q in data.quarters}
            if not data.quarters:
                self.state.add_gap("empty_result", f"Tidak ada data kuartalan untuk {symbol}.", symbol)
        else:
            self._record_failure(symbol, "quarterly financials", result.status, result.error)
        return data.quarters

    def _record_failure(self, symbol: str, what: str, status: str, error: str | None) -> None:
        if status == "not_found":
            self.state.add_gap("unknown_company", f"{symbol} tidak ditemukan di Sectors.", symbol)
            return
        trigger = "budget_exhausted" if status == "budget_exhausted" else "tool_error"
        self.state.recovery.append(RecoveryAction(
            trigger=trigger, target=f"{what} {symbol}",
            action="Retry terbatas oleh SectorsService" if trigger == "tool_error"
            else "Tidak memanggil tool lagi",
            outcome="Data ditandai tidak tersedia",
        ))
        self.state.add_gap(trigger, f"{what.capitalize()} {symbol} tidak dapat diambil ({status}).",
                           symbol)

    def sub_sector(self, symbol: str) -> str | None:
        report = self.report(symbol)
        return report.overview.sub_sector if report and report.overview else None

    def company_name(self, symbol: str) -> str | None:
        report = self.report(symbol)
        return report.company_name if report else None

    # -- evidence --------------------------------------------------------------

    def _evidence(self, *, call_id: str, tool: str, symbol: str, period: str, field_: str,
                  value: float | None, unit: str, source_ref: str, note: str | None = None) -> str:
        key = (call_id, symbol, period, field_)
        if key not in self._evidence_index:
            ev = self.state.add_evidence(
                call_id=call_id, tool=tool, symbol=symbol, period=period, field=field_,
                value=value, unit=unit, source_ref=source_ref, note=note,
            )
            self._evidence_index[key] = ev.evidence_id
        return self._evidence_index[key]

    # -- metrics ---------------------------------------------------------------

    def metric_values(self, symbol: str, metric: str) -> list[MetricValue]:
        data = self._data(symbol)
        if metric in data.values:
            return data.values[metric]
        spec = METRICS[metric]
        values: list[MetricValue] = []
        if spec.banking_only:
            sub = self.sub_sector(symbol)
            if sub is not None and sub != BANKING_SUB_SECTOR:
                self.state.add_gap(
                    "not_applicable",
                    f"{spec.label} hanya berlaku untuk emiten perbankan; {symbol} ({sub}) dilewati.",
                    symbol,
                )
                data.values[metric] = values
                return values
        if spec.source == "report_ratio":
            values = self._report_ratio(symbol, spec)
        elif spec.source == "quarterly_growth":
            values = self._quarterly_growth(symbol, spec)
        else:
            values = self._quarterly_ratio(symbol, spec)
        if not values and (data.report is not None or data.quarters):
            detail = (f"{spec.label} {symbol} tidak dapat dihitung: kuartal pembanding tahun "
                      "sebelumnya tidak tersedia." if spec.source == "quarterly_growth"
                      else f"{spec.label} tidak tersedia di data Sectors untuk {symbol}.")
            self.state.add_gap("missing_metric", detail, symbol)
        data.values[metric] = values
        return values

    def _report_ratio(self, symbol: str, spec: MetricSpec) -> list[MetricValue]:
        report = self.report(symbol)
        data = self._data(symbol)
        if report is None or report.financials is None or data.report_call is None:
            return []
        out = []
        for entry in report.financials.historical_financial_ratio:
            raw = _get_path(entry, str(spec.path))
            value, converted = normalize_ratio(raw)
            if value is None:
                continue
            period = str(entry.year)
            note = None
            if converted:
                note = f"dinormalisasi dari persen ({raw}) ke rasio"
                msg = (f"Rasio {symbol} dari company report tercatat dalam satuan persen "
                       "dan dinormalisasi ke pecahan sebelum dibandingkan.")
                normalizations = self.state.analytics.setdefault("unit_normalizations", [])
                if msg not in normalizations:
                    normalizations.append(msg)
            ev = self._evidence(
                call_id=data.report_call, tool="fetch-company-report", symbol=symbol,
                period=period, field_=str(spec.path), value=value, unit="ratio",
                source_ref=f"fetch-company-report {symbol} historical_financial_ratio[{period}].{spec.path}",
                note=note,
            )
            out.append(MetricValue(symbol=symbol, metric=spec.name, period=period, value=value,
                                   unit="ratio", evidence_ids=[ev], note=note))
        return out

    def _quarter_value(self, symbol: str, row: QuarterlyFinancial, path: str) -> tuple[float | None, str]:
        data = self._data(symbol)
        value = _get_path(row, path)
        ev = self._evidence(
            call_id=data.quarter_calls[row.date], tool="fetch-quarterly-financials", symbol=symbol,
            period=row.date, field_=path, value=value, unit="IDR",
            source_ref=f"fetch-quarterly-financials {symbol} {row.date} {path}",
        )
        return value, ev

    def _check_incomplete(self, symbol: str, rows: list[QuarterlyFinancial], path: str) -> None:
        if not path.startswith("financials_sector_metrics"):
            return
        for row in rows:
            if row.financials_sector_metrics is None:
                self.state.add_gap(
                    "incomplete_response",
                    f"Laporan {symbol} {quarter_label(row.date)} tidak memuat "
                    "financials_sector_metrics; metrik terkait tidak dihitung untuk periode itu.",
                    symbol,
                )

    def _quarterly_growth(self, symbol: str, spec: MetricSpec) -> list[MetricValue]:
        rows = self.quarters(symbol)
        if not rows:
            return []
        path = str(spec.path)
        self._check_incomplete(symbol, rows, path)
        # Bounded recovery: the default window may not reach the prior-year quarter.
        prior = prior_year_period(rows[-1].date)
        if not any(r.date == prior for r in rows) and self.ensure_period(symbol, prior):
            rows = self.quarters(symbol) or rows
        by_date = {r.date: r for r in rows}
        out = []
        for row in rows:
            prev = by_date.get(prior_year_period(row.date))
            if prev is None:
                continue
            cur_v, cur_ev = self._quarter_value(symbol, row, path)
            prev_v, prev_ev = self._quarter_value(symbol, prev, path)
            change = pct_change(cur_v, prev_v)
            if change is None:
                continue
            out.append(MetricValue(
                symbol=symbol, metric=spec.name, period=row.date, value=change, unit="pct_change",
                evidence_ids=[cur_ev, prev_ev], derived=True,
                inputs={"current": cur_ev, "previous": prev_ev},
            ))
        if spec.name == "earnings_growth_yoy" and out:
            self._cross_check_reported_growth(symbol, out[-1])
        return out

    def _quarterly_ratio(self, symbol: str, spec: MetricSpec) -> list[MetricValue]:
        rows = self.quarters(symbol)
        if not rows:
            return []
        num_path, den_path = spec.path  # type: ignore[misc]
        self._check_incomplete(symbol, rows, num_path)
        out = []
        for row in rows:
            num, num_ev = self._quarter_value(symbol, row, num_path)
            den, den_ev = self._quarter_value(symbol, row, den_path)
            value = safe_div(num, den)
            if value is None:
                continue
            out.append(MetricValue(
                symbol=symbol, metric=spec.name, period=row.date, value=value, unit="ratio",
                evidence_ids=[num_ev, den_ev], derived=True,
                inputs={"numerator": num_ev, "denominator": den_ev},
            ))
        return out

    def _cross_check_reported_growth(self, symbol: str, computed: MetricValue) -> None:
        """Compare our YoY earnings growth with the figure in the company report."""
        report = self.report(symbol)
        data = self._data(symbol)
        reported = report.financials.yoy_quarter_earnings_growth if report and report.financials else None
        if reported is None or data.report_call is None:
            return
        ev = self._evidence(
            call_id=data.report_call, tool="fetch-company-report", symbol=symbol,
            period=computed.period, field_="financials.yoy_quarter_earnings_growth",
            value=reported, unit="pct_change",
            source_ref=f"fetch-company-report {symbol} financials.yoy_quarter_earnings_growth",
            note="periode diasumsikan kuartal terakhir yang tersedia",
        )
        if abs(reported - computed.value) > CONFLICT_TOLERANCE:
            self.state.conflicts.append(Conflict(
                symbol=symbol, metric="earnings_growth_yoy", period=computed.period,
                values={"calculated": computed.value, ev: reported},
                detail=(f"Pertumbuhan laba YoY {symbol} {quarter_label(computed.period)}: "
                        f"dihitung {computed.value * 100:.1f}% vs laporan {reported * 100:.1f}%"),
            ))
            self.state.recovery.append(RecoveryAction(
                trigger="conflicting_data", target=f"earnings_growth_yoy {symbol}",
                action="Tidak memilih salah satu nilai; klaim terkait ditahan validator",
                outcome="Kedua nilai ditampilkan sebagai kesenjangan data",
            ))

    def ensure_period(self, symbol: str, period: str) -> bool:
        """Bounded re-query for a specific quarter the default window did not return."""
        rows = self.quarters(symbol) or []
        if any(r.date == period for r in rows) or len(period) == 4:
            return any(r.date == period for r in rows)
        if (symbol, period) in self._requeried or self.state.requeries_used >= self.max_requeries:
            return False
        self._requeried.add((symbol, period))
        self.state.requeries_used += 1
        result = self.service.quarterly_financials(symbol, report_date=period)
        found = bool(result.ok and result.data)
        self.state.recovery.append(RecoveryAction(
            trigger="missing_data", target=f"{symbol} {period}",
            action="Re-query fetch-quarterly-financials dengan report_date",
            outcome="Periode ditemukan" if found else "Periode tidak tersedia",
        ))
        if found:
            data = self._data(symbol)
            new_rows = [r for r in result.data if r.date not in data.quarter_calls]
            data.quarter_calls.update({r.date: result.call_id for r in new_rows})
            data.quarters = sorted(rows + new_rows, key=lambda q: q.date)
            data.values.clear()
        return found
