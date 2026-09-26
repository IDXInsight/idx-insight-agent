import pytest

PEER_Q = "Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitability dan efficiency."


def comparison(state, metric):
    return state.analytics["peer_comparison"][metric]


def test_peer_comparison_metrics_and_values(run):
    state = run(PEER_Q)
    assert state.intent.name == "peer_comparison"
    roe = comparison(state, "roe")
    assert roe["period"] == "2025"
    assert roe["highest"] == "BBCA" and roe["lowest"] == "BBNI"
    assert roe["range"] == pytest.approx(0.235 - 0.138)
    assert "cost_to_income_ratio" in state.analytics["peer_comparison"]


def test_percent_units_are_normalized(run):
    state = run(PEER_Q)
    assert comparison(state, "roe")["values"]["BBNI"] == pytest.approx(0.138)
    assert any("BBNI" in n for n in state.analytics["unit_normalizations"])
    ev = [e for e in state.evidence.values() if e.symbol == "BBNI" and e.note]
    assert ev and all(e.value < 1 for e in ev)


def test_contradictory_growth_is_held_back(run):
    state = run(PEER_Q)
    assert [c.symbol for c in state.conflicts] == ["BMRI"]
    growth = comparison(state, "earnings_growth_yoy")
    assert "BMRI" not in growth["values"]
    rejected = [c for c in state.claims if c.claim_id in state.validation.rejected]
    assert any(c.symbols == ["BMRI"] and c.metric == "earnings_growth_yoy" for c in rejected)
    assert any(r.trigger == "conflicting_data" for r in state.recovery)


def test_growth_is_calculated_deterministically_with_traceable_inputs(run):
    state = run(PEER_Q)
    growth = comparison(state, "earnings_growth_yoy")
    assert growth["values"]["BBRI"] == pytest.approx((13.2 - 14.8) / 14.8)
    claim = next(c for c in state.claims if c.metric == "earnings_growth_yoy"
                 and c.symbols == ["BBCA"])
    assert claim.kind == "calculation"
    periods = {state.evidence[e].period for e in claim.input_evidence.values()}
    assert periods == {"2026-06-30", "2025-06-30"}


def test_period_alignment_prefers_common_quarter(run):
    state = run("Bandingkan likuiditas BBCA dan BBTN")
    ldr = comparison(state, "ldr_quarterly")
    assert ldr["period"] == "2026-03-31"  # BBTN has not reported Q2 2026
    assert any("BBCA sudah memiliki data lebih baru" in a for a in state.assumptions)


def test_incomplete_report_is_exposed(run):
    state = run("Bandingkan pertumbuhan BBCA dan BRIS")
    assert any(g.kind == "incomplete_response" and g.symbol == "BRIS" for g in state.data_gaps)
    # BRIS's only YoY-comparable quarter is the incomplete one, so NII growth cannot be
    # computed for BRIS and no comparison claim is made.
    nii = comparison(state, "nii_growth_yoy")
    assert "BRIS" not in nii["values"] and not nii["sufficient"]
    assert not any(c.kind == "comparison" and c.metric == "nii_growth_yoy" for c in state.claims)
    # Earnings (complete in every quarter) are still compared.
    assert comparison(state, "earnings_growth_yoy")["sufficient"]


def test_missing_prior_year_quarter_triggers_bounded_requery(run):
    state = run("Bandingkan pertumbuhan BBCA dan BBTN")
    requery = [r for r in state.recovery if r.trigger == "missing_data"]
    assert requery and requery[0].outcome == "Periode tidak tersedia"
    assert state.requeries_used <= 2


def test_stale_common_period_is_warned(run):
    state = run("Bandingkan ROE BBCA dan BTPS")
    roe = comparison(state, "roe")
    assert roe["period"] == "2024"
    stale = [i for i in state.validation.issues if i.code == "stale_data"]
    assert stale and all(i.severity == "warning" for i in stale)


def test_requested_unavailable_period_is_reported(run):
    state = run("Bandingkan ROE BBCA dan BBRI tahun 2023")
    assert any(g.kind == "unavailable_period" for g in state.data_gaps)
    assert state.status == "insufficient_evidence"
    assert state.briefing.summary.startswith("Bukti tidak cukup")


def test_unsupported_metric_is_not_estimated(run):
    state = run("Bandingkan NPL BBCA dan BBRI")
    assert any(g.kind == "unsupported_metric" for g in state.data_gaps)
    assert not any("npl" in (c.metric or "") for c in state.claims)


def test_banking_metric_not_applied_to_non_bank(run):
    state = run("Bandingkan NIM BBCA dan TLKM")
    assert any(g.kind == "not_applicable" and g.symbol == "TLKM" for g in state.data_gaps)


def test_sector_peer_comparison_uses_sector_members(run):
    state = run("Bandingkan ROE sektor perbankan")
    assert set(state.analytics["analysis_symbols"]) >= {"BBCA", "BBRI", "BMRI", "BBNI"}
    assert "TLKM" not in state.analytics["analysis_symbols"]


def test_company_context_run(run):
    state = run("Bagaimana kinerja BBCA?")
    assert state.intent.name == "company_context"
    trend = [c for c in state.claims if c.meta.get("section") == "trend"]
    assert any("vs" in c.statement for c in trend)
    assert state.validation.status in ("passed", "partial")
