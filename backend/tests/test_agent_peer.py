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


def test_ratio_series_with_mixed_units_is_left_out(run, monkeypatch):
    # Seen on real data: one series mixing values above and below the percent threshold.
    from idx_insight.sectors import mock_data

    ratios = dict(mock_data._RATIOS)
    ratios["BBRI"] = {2024: (0.031, 0.195, 0.078, 1.16, 0.65, 0.89, 0.26),
                      2025: (0.029, 0.180, 0.074, 1.89, 0.64, 0.92, 0.25)}
    monkeypatch.setattr(mock_data, "_RATIOS", ratios)
    state = run(PEER_Q)
    cir = comparison(state, "cost_to_income_ratio")
    assert "BBRI" not in cir["values"] and "BBCA" in cir["values"]
    gaps = [g for g in state.data_gaps if g.kind == "malformed_data" and g.symbol == "BBRI"]
    assert gaps and "1.89" in gaps[0].detail
    assert comparison(state, "roe")["values"]["BBRI"] == pytest.approx(0.180)


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
    state = run("Bandingkan BOPO BBCA dan BBRI")
    assert any(g.kind == "unsupported_metric" for g in state.data_gaps)
    assert not any("bopo" in (c.metric or "") for c in state.claims)


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


def test_npl_ratio_uses_one_screener_call_for_all_banks(run):
    state = run("Bandingkan NPL BBCA, BBRI, BMRI dan BBNI")
    npl = comparison(state, "npl_ratio")
    assert npl["sufficient"] and npl["period"] == "2025"
    assert npl["highest"] == "BBRI" and npl["lowest"] == "BMRI"
    assert npl["values"]["BBRI"] == pytest.approx(42.9 / 1430)
    screener = [c for c in state.tool_calls if c.tool == "company-screener"]
    assert len(screener) == 1
    assert screener[0].args["fields"] == ["non_performing_loan[2025]", "gross_loan[2025]"]
    # No paid company reports are needed for NPL alone.
    assert not any(c.tool == "fetch-company-report" for c in state.tool_calls)
    claim = next(c for c in state.claims if c.metric == "npl_ratio" and c.symbols == ["BBRI"])
    assert set(claim.input_evidence) == {"numerator", "denominator"}


def test_npl_missing_for_a_company_is_a_gap(run):
    state = run("Bandingkan NPL BBCA dan BTPS")
    assert any(g.kind == "missing_metric" and g.symbol == "BTPS" for g in state.data_gaps)
    assert not comparison(state, "npl_ratio")["sufficient"]


def test_asset_quality_bundle_maps_to_npl(run):
    state = run("Bandingkan kualitas aset BBCA dan BBRI")
    assert "npl_ratio" in state.analytics["peer_comparison"]


def test_banking_check_accepts_display_names_from_real_reports():
    # Found in the first real-data evaluation: reports say "Banks", lists say "banks".
    from idx_insight.agent.financials import sub_sector_slug

    assert sub_sector_slug("Banks") == "banks"
    assert sub_sector_slug(" Oil, Gas & Coal ") == "oil-gas-coal"
    assert sub_sector_slug("banks") == "banks"
