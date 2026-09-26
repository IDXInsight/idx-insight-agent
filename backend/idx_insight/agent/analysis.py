"""Analysis steps that turn metric values and events into evidence-backed claims.

Claims are proposals: the Evidence Validator decides which may be stated.
"""

from __future__ import annotations

from idx_insight.agent.financials import FinancialContext
from idx_insight.agent.i18n import t
from idx_insight.agent.state import AgentState
from idx_insight.analytics.metrics import EVENT_CONTEXT_METRICS, METRICS
from idx_insight.analytics.numbers import fmt_idr, fmt_pct, fmt_pp
from idx_insight.analytics.peers import compare_peers
from idx_insight.analytics.periods import align_latest_common, prior_year_period, quarter_label
from idx_insight.models import MetricValue


def _value_claim(state: AgentState, mv: MetricValue, section: str, **meta) -> None:
    lang = state.language
    text = t(lang, "claim.value", label=METRICS[mv.metric].label_in(lang), sym=mv.symbol,
             period=quarter_label(mv.period), value=fmt_pct(mv.value, lang))
    if mv.metric.endswith("_growth_yoy") and {"current", "previous"} <= set(mv.inputs):
        cur = state.evidence[mv.inputs["current"]].value
        prev = state.evidence[mv.inputs["previous"]].value
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            text += t(lang, "claim.growth_inputs", cur=fmt_idr(cur, lang), prev=fmt_idr(prev, lang),
                      prev_period=quarter_label(prior_year_period(mv.period)))
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
    lang = state.language
    requested = state.timeframe.financial_period if state.timeframe else None
    peer_results = state.analytics.setdefault("peer_comparison", {})
    for metric in metrics:
        label = METRICS[metric].label_in(lang)
        series = {sym: _series(ctx, sym, metric, requested) for sym in symbols}
        if requested:
            for sym, vals in series.items():
                if not vals:
                    state.add_gap("unavailable_period", t(lang, "gap.unavailable_period", label=label,
                                                          sym=sym, period=quarter_label(requested)),
                                  sym)
        alignment = align_latest_common({s: list(v) for s, v in series.items()})
        chosen = {s: series[s][p] for s, p in alignment.per_symbol.items() if p}
        if alignment.ahead:
            state.assumptions.append(t(lang, "assumption.common_period", label=label,
                                       period=quarter_label(alignment.period),
                                       ahead=", ".join(alignment.ahead)))
        for mv in chosen.values():
            _value_claim(state, mv, "peer")

        conflicted = sorted({c.symbol for c in state.conflicts if c.metric == metric} & set(chosen))
        if conflicted:
            state.assumptions.append(t(lang, "assumption.conflicted_excluded", label=label,
                                       syms=", ".join(conflicted)))
            chosen = {s: mv for s, mv in chosen.items() if s not in conflicted}
        comp = compare_peers(metric, alignment.period, {s: mv.value for s, mv in chosen.items()})
        peer_results[metric] = {
            **comp.model_dump(),
            "aligned": alignment.aligned,
            "periods": {s: mv.period for s, mv in chosen.items()},
            "missing": alignment.missing,
        }
        if not comp.sufficient:
            state.add_gap("insufficient_evidence", t(lang, "gap.too_few_peers", label=label))
            continue
        period_label = (quarter_label(alignment.period) if alignment.period
                        else t(lang, "period.mixed"))
        text = t(lang, "claim.comparison", label=label, period=period_label,
                 hi=comp.highest, hi_v=fmt_pct(chosen[comp.highest].value, lang),
                 lo=comp.lowest, lo_v=fmt_pct(chosen[comp.lowest].value, lang),
                 range=fmt_pp(comp.range, lang), median=fmt_pct(comp.median, lang))
        if comp.outliers:
            text += t(lang, "claim.comparison_outliers", syms=", ".join(comp.outliers))
        state.add_claim(
            kind="comparison", statement=text, symbols=list(chosen), metric=metric,
            period=alignment.period, value=comp.range,
            evidence_ids=[e for mv in chosen.values() for e in mv.evidence_ids],
            meta={"section": "peer", "periods": {s: mv.period for s, mv in chosen.items()},
                  "highest": comp.highest, "lowest": comp.lowest, "outliers": comp.outliers},
        )


def company_trends(state: AgentState, ctx: FinancialContext, symbol: str,
                   metrics: list[str]) -> None:
    lang = state.language
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
            statement=t(lang, "claim.trend", label=METRICS[metric].label_in(lang), sym=symbol,
                        p1=latest.period, p0=prev.period, v1=fmt_pct(latest.value, lang),
                        v0=fmt_pct(prev.value, lang), delta=fmt_pp(delta, lang)),
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
