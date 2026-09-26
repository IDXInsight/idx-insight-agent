"""Analysis steps that turn metric values and events into evidence-backed claims.

Claims are proposals: the Evidence Validator decides which may be stated.
"""

from __future__ import annotations

from idx_insight.agent.financials import FinancialContext
from idx_insight.agent.state import AgentState
from idx_insight.analytics.metrics import EVENT_CONTEXT_METRICS, METRICS
from idx_insight.analytics.numbers import fmt_idr, fmt_pct, fmt_pp
from idx_insight.analytics.peers import compare_peers
from idx_insight.analytics.periods import align_latest_common, prior_year_period, quarter_label
from idx_insight.models import MetricValue


def _value_claim(state: AgentState, mv: MetricValue, section: str, prefix: str = "",
                 **meta) -> None:
    spec = METRICS[mv.metric]
    text = f"{prefix}{spec.label} {mv.symbol} {quarter_label(mv.period)}: {fmt_pct(mv.value)}"
    if mv.metric.endswith("_growth_yoy") and {"current", "previous"} <= set(mv.inputs):
        cur = state.evidence[mv.inputs["current"]].value
        prev = state.evidence[mv.inputs["previous"]].value
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            text += (f" ({fmt_idr(cur)} vs {fmt_idr(prev)} pada "
                     f"{quarter_label(prior_year_period(mv.period))})")
    state.add_claim(
        kind="calculation" if mv.derived else "metric",
        statement=text, symbols=[mv.symbol], metric=mv.metric, period=mv.period, value=mv.value,
        evidence_ids=mv.evidence_ids, required_inputs=list(mv.inputs),
        input_evidence=mv.inputs, meta={"section": section, **meta},
    )


def _series(ctx: FinancialContext, symbol: str, metric: str,
            period: str | None) -> dict[str, MetricValue]:
    if period and len(period) > 4 and METRICS[metric].source != "report_ratio":
        ctx.ensure_period(symbol, period)
    values = {mv.period: mv for mv in ctx.metric_values(symbol, metric)}
    if period:
        wanted = period if len(period) == 4 or METRICS[metric].source != "report_ratio" else period[:4]
        values = {p: mv for p, mv in values.items() if p == wanted}
    return values


def peer_comparison(state: AgentState, ctx: FinancialContext, symbols: list[str],
                    metrics: list[str]) -> None:
    requested = state.timeframe.financial_period if state.timeframe else None
    peer_results = state.analytics.setdefault("peer_comparison", {})
    for metric in metrics:
        spec = METRICS[metric]
        series = {sym: _series(ctx, sym, metric, requested) for sym in symbols}
        if requested:
            for sym, vals in series.items():
                if not vals:
                    state.add_gap("unavailable_period",
                                  f"{spec.label} {sym} untuk periode {quarter_label(requested)} "
                                  "tidak tersedia.", sym)
        alignment = align_latest_common({s: list(v) for s, v in series.items()})
        chosen = {s: series[s][p] for s, p in alignment.per_symbol.items() if p}
        if alignment.ahead:
            state.assumptions.append(
                f"{spec.label}: dibandingkan pada periode bersama {quarter_label(alignment.period)}; "
                f"{', '.join(alignment.ahead)} sudah memiliki data lebih baru."
            )
        for mv in chosen.values():
            _value_claim(state, mv, "peer")

        conflicted = sorted({c.symbol for c in state.conflicts if c.metric == metric} & set(chosen))
        if conflicted:
            state.assumptions.append(
                f"{spec.label}: {', '.join(conflicted)} dikeluarkan dari perbandingan karena "
                "nilai antar-sumber bertentangan."
            )
            chosen = {s: mv for s, mv in chosen.items() if s not in conflicted}
        comp = compare_peers(metric, alignment.period, {s: mv.value for s, mv in chosen.items()})
        peer_results[metric] = {
            **comp.model_dump(),
            "aligned": alignment.aligned,
            "periods": {s: mv.period for s, mv in chosen.items()},
            "missing": alignment.missing,
        }
        if not comp.sufficient:
            state.add_gap("insufficient_evidence",
                          f"{spec.label}: kurang dari dua emiten dengan data yang dapat dibandingkan.")
            continue
        label = quarter_label(alignment.period) if alignment.period else "periode berbeda"
        text = (f"{spec.label} ({label}): tertinggi {comp.highest} "
                f"{fmt_pct(chosen[comp.highest].value)}, terendah {comp.lowest} "
                f"{fmt_pct(chosen[comp.lowest].value)}, selisih {fmt_pp(comp.range)}, "
                f"median {fmt_pct(comp.median)}")
        if comp.outliers:
            text += f"; {', '.join(comp.outliers)} menyimpang jauh dari median peer"
        state.add_claim(
            kind="comparison", statement=text, symbols=list(chosen), metric=metric,
            period=alignment.period, value=comp.range,
            evidence_ids=[e for mv in chosen.values() for e in mv.evidence_ids],
            meta={"section": "peer", "periods": {s: mv.period for s, mv in chosen.items()},
                  "highest": comp.highest, "lowest": comp.lowest, "outliers": comp.outliers},
        )


def company_trends(state: AgentState, ctx: FinancialContext, symbol: str,
                   metrics: list[str]) -> None:
    for metric in metrics:
        values = sorted(ctx.metric_values(symbol, metric), key=lambda mv: mv.period)
        if not values:
            continue
        latest = values[-1]
        _value_claim(state, latest, "trend")
        if METRICS[metric].source != "report_ratio" or len(values) < 2:
            continue
        prev = next((mv for mv in values if mv.period == prior_year_period(latest.period)), None)
        if prev is None:
            continue
        delta = latest.value - prev.value
        state.add_claim(
            kind="calculation",
            statement=(f"{METRICS[metric].label} {symbol} {latest.period} vs {prev.period}: "
                       f"{fmt_pct(latest.value)} vs {fmt_pct(prev.value)} ({fmt_pp(delta)})"),
            symbols=[symbol], metric=metric, period=latest.period, value=delta,
            evidence_ids=latest.evidence_ids + prev.evidence_ids,
            required_inputs=["current", "previous"],
            input_evidence={"current": latest.evidence_ids[0], "previous": prev.evidence_ids[0]},
            meta={"section": "trend"},
        )


def second_hop_context(state: AgentState, ctx: FinancialContext, symbols: list[str]) -> None:
    for symbol in symbols:
        event_ids = [d.event_id for d in state.second_hop
                     if d.symbol == symbol and d.decision in ("research", "reuse")]
        for metric in EVENT_CONTEXT_METRICS:
            values = sorted(ctx.metric_values(symbol, metric), key=lambda mv: mv.period)
            if values:
                _value_claim(state, values[-1], "second_hop", context_for=event_ids)


def event_claims(state: AgentState) -> None:
    for ev in state.relevant_events:
        state.add_claim(
            kind="event",
            statement=f"{ev.event_date} · {ev.title}",
            symbols=[ev.symbol], period=ev.event_date, evidence_ids=ev.evidence_ids,
            meta={"section": "events", "event_id": ev.event_id, "score": ev.relevance_score,
                  "reasons": ev.relevance_reasons, "event_type": ev.event_type},
        )
