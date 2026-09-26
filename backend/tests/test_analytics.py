import pytest

from idx_insight.analytics.events import (
    RelevanceContext,
    dedupe,
    event_density,
    score_event,
)
from idx_insight.analytics.numbers import (
    fmt_idr,
    normalize_amount,
    normalize_ratio,
    pct_change,
    robust_outliers,
    safe_div,
    spread,
)
from idx_insight.analytics.peers import compare_peers
from idx_insight.analytics.periods import align_latest_common, prior_year_period, quarter_label
from idx_insight.models import Event


# --- numbers ---------------------------------------------------------------


def test_pct_change_basic_and_missing_inputs():
    assert pct_change(110, 100) == pytest.approx(0.10)
    assert pct_change(None, 100) is None
    assert pct_change(100, 0) is None


def test_pct_change_from_loss_uses_absolute_base():
    assert pct_change(-50, -100) == pytest.approx(0.5)


def test_spread_and_safe_div():
    assert spread(0.235, 0.18) == pytest.approx(0.055)
    assert spread(None, 0.1) is None
    assert safe_div(1, 0) is None
    assert safe_div(985, 1290) == pytest.approx(0.7636, rel=1e-3)


def test_normalize_amount_units():
    assert normalize_amount(1.5, "triliun") == 1.5e12
    assert normalize_amount(250, "billion") == 250e9
    with pytest.raises(ValueError):
        normalize_amount(1, "lakh")


def test_normalize_ratio_detects_percent_units():
    assert normalize_ratio(13.8) == (pytest.approx(0.138), True)
    assert normalize_ratio(0.235) == (0.235, False)
    assert normalize_ratio(None) == (None, False)


def test_robust_outliers_needs_enough_peers():
    assert robust_outliers({"A": 1, "B": 2, "C": 100}) == []
    values = {"A": 0.20, "B": 0.21, "C": 0.22, "D": 0.21, "E": 0.60}
    assert robust_outliers(values) == ["E"]


def test_fmt_idr():
    assert fmt_idr(15.1e12) == "Rp15.1 T"
    assert fmt_idr(218.4e9) == "Rp218.4 M"


# --- periods ---------------------------------------------------------------


def test_quarter_helpers():
    assert quarter_label("2026-06-30") == "Q2 2026"
    assert quarter_label("2025") == "2025"
    assert prior_year_period("2026-06-30") == "2025-06-30"
    assert prior_year_period("2025") == "2024"


def test_alignment_prefers_common_period_over_recency():
    result = align_latest_common(
        {"BBCA": ["2026-03-31", "2026-06-30"], "BBTN": ["2025-12-31", "2026-03-31"]}
    )
    assert result.aligned and result.period == "2026-03-31"
    assert result.ahead == ["BBCA"]


def test_alignment_reports_missing_companies():
    result = align_latest_common({"BBCA": ["2025"], "XXXX": []})
    assert result.period == "2025" and result.missing == ["XXXX"]


def test_alignment_without_common_period_is_flagged():
    result = align_latest_common({"BBCA": ["2025"], "BTPS": ["2024"]})
    assert not result.aligned and result.period is None
    assert result.per_symbol == {"BBCA": "2025", "BTPS": "2024"}
    assert result.lagging == ["BTPS"]


# --- peers -----------------------------------------------------------------


def test_peer_comparison_stats():
    comp = compare_peers("roe", "2025", {"BBCA": 0.235, "BBRI": 0.18, "BMRI": 0.21, "BBNI": 0.138})
    assert comp.sufficient
    assert comp.highest == "BBCA" and comp.lowest == "BBNI"
    assert comp.range == pytest.approx(0.097)
    assert comp.median == pytest.approx(0.195)
    assert comp.ranking == ["BBCA", "BMRI", "BBRI", "BBNI"]


def test_peer_comparison_single_company_is_insufficient():
    assert not compare_peers("roe", "2025", {"BBCA": 0.2}).sufficient


# --- events ----------------------------------------------------------------


def _event(eid, symbol="BMRI", etype="ownership_change", **attrs):
    return Event(
        event_id=eid, symbol=symbol, event_type=etype, event_date="2026-09-22",
        title="t", source_ref="src", attributes=attrs,
    )


def test_dedupe_marks_duplicates():
    unique, dupes = dedupe([_event("a", amount_transaction=1), _event("b", amount_transaction=1),
                            _event("c", amount_transaction=2)])
    assert [e.event_id for e in unique] == ["a", "c"]
    assert dupes[0].duplicate_of == "a"


def test_event_density():
    assert event_density([_event("a"), _event("b"), _event("c", symbol="BBRI")]) == {
        "BMRI": 2, "BBRI": 1}


def test_large_ownership_change_scores_above_threshold():
    ev = _event("a", share_percentage_transaction=1.3, transaction_value=218e9,
                holder_type="institution")
    score, reasons = score_event(ev, RelevanceContext(frozenset(), {}))
    assert score == 40
    assert any("≥1%" in r for r in reasons)


def test_small_insider_trade_scores_low():
    ev = _event("a", share_percentage_transaction=0.0025, transaction_value=2.5e9,
                holder_type="insider")
    score, _ = score_event(ev, RelevanceContext(frozenset(), {}))
    assert score == 20


def test_forward_looking_clustered_watchlist_event():
    ev = Event(event_id="x", symbol="BBRI", event_type="dividend_ex", event_date="2026-10-02",
               title="t", source_ref="s", forward_looking=True)
    score, reasons = score_event(ev, RelevanceContext(frozenset({"BBRI"}), {"BBRI": 2}))
    assert score == 35 + 10 + 10 + 5
    assert len(reasons) == 4
