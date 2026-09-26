from datetime import date

from idx_insight.config import Settings
from idx_insight.sectors import MockSectorsAdapter

DISCOVERY_Q = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"


def test_discovery_finds_relevant_events_in_scope_and_window(run):
    state = run(DISCOVERY_Q)
    assert state.intent.name == "discovery"
    symbols = {e.symbol for e in state.discovered_events}
    assert "TLKM" not in symbols  # other sector
    tf = state.timeframe
    for ev in state.discovered_events:
        d = date.fromisoformat(ev.event_date)
        assert tf.start <= d <= tf.end or tf.filings_start <= d <= tf.filings_end
    # BBCA's December dividend is outside next week and must not appear.
    assert not any(e.symbol == "BBCA" and e.event_type == "dividend_ex"
                   for e in state.discovered_events)


def test_duplicate_filing_is_removed(run):
    state = run(DISCOVERY_Q)
    assert len(state.duplicate_events) == 1
    dup = state.duplicate_events[0]
    assert dup.symbol == "BMRI" and dup.duplicate_of is not None


def test_relevance_ranking_is_deterministic_and_explained(run):
    first, second = run(DISCOVERY_Q), run(DISCOVERY_Q)
    assert [e.event_id for e in first.relevant_events] == [e.event_id for e in second.relevant_events]
    top = first.relevant_events[0]
    assert top.symbol == "BBNI" and top.event_type == "ownership_change"
    assert all(e.relevance_reasons for e in first.relevant_events)
    # Small insider trade stays below the relevance threshold.
    assert not any(e.symbol == "BMRI" for e in first.relevant_events)


def test_second_hop_decisions_research_reuse_and_skip(run):
    state = run(DISCOVERY_Q)
    decisions = {(d.symbol, d.decision) for d in state.second_hop}
    assert ("BBNI", "research") in decisions
    assert ("BBRI", "reuse") in decisions
    assert ("BBTN", "skip") in decisions
    researched = [d.symbol for d in state.second_hop if d.decision == "research"]
    assert len(researched) == len(set(researched)) <= Settings().max_second_hop
    # Second-hop context claims exist and are validated.
    context = [c for c in state.claims if c.meta.get("section") == "second_hop"]
    assert context and all(c.claim_id in state.validation.accepted for c in context)


def test_list_only_request_skips_second_hop(run):
    state = run("Disclosure perbankan minggu depan, daftar saja")
    assert "second_hop_context" not in state.plan.names
    assert state.second_hop == []
    assert not any(c.tool == "fetch-quarterly-financials" for c in state.tool_calls)


def test_second_hop_respects_tool_budget(run):
    # 4 discovery calls (subsectors, companies, filings, calendar) + 3 per researched company.
    state = run(DISCOVERY_Q, settings=Settings(max_tool_calls=9))
    skips = [d for d in state.second_hop if "anggaran" in d.reason]
    assert skips
    assert any(r.trigger == "budget_exhausted" for r in state.recovery)
    assert sum(c.attempts for c in state.tool_calls) <= 9


def test_reporting_dates_gap_is_explicit(run):
    state = run(DISCOVERY_Q)
    assert any(g.kind == "unsupported_capability" for g in state.data_gaps)


def test_empty_filings_trigger_one_bounded_widening(run):
    state = run("Disclosure BBCA minggu depan")
    widen = [r for r in state.recovery if r.trigger == "empty_result"]
    assert len(widen) == 1
    assert state.requeries_used == 1
    filings_calls = [c for c in state.tool_calls if c.tool == "fetch-filings"]
    assert len(filings_calls) == 2


def test_corporate_action_outage_becomes_gap_not_crash(run):
    adapter = MockSectorsAdapter(failures={"get_corporate_actions_calendar:*": "always"})
    state = run(DISCOVERY_Q, adapter=adapter)
    assert any(r.trigger == "tool_error" and "kalender" in r.target for r in state.recovery)
    assert any(g.kind == "tool_error" for g in state.data_gaps)
    assert not any(e.event_type == "agm" for e in state.discovered_events)
    # Filings are still discovered.
    assert any(e.event_type == "ownership_change" for e in state.discovered_events)
    assert state.status == "partial"


def test_transient_error_is_retried_and_recovers(run):
    adapter = MockSectorsAdapter(failures={"get_corporate_actions_calendar:*": 1})
    state = run(DISCOVERY_Q, adapter=adapter)
    assert any(e.symbol == "BBNI" and e.event_type == "agm" for e in state.discovered_events)
    call = next(c for c in state.tool_calls if c.tool == "corporate-actions-calendar")
    assert call.attempts == 2


def test_sector_scope_uses_one_calendar_call(run):
    state = run(DISCOVERY_Q)
    assert state.analytics["corporate_actions_source"] == "calendar"
    tools = [c.tool for c in state.tool_calls]
    assert tools.count("corporate-actions-calendar") == 1
    assert "fetch-corporate-actions" not in tools


def test_small_watchlist_uses_per_company_lookups(run):
    state = run("Disclosure BBRI dan BBNI minggu depan")
    assert state.analytics["corporate_actions_source"] == "per_company"
    assert [c.tool for c in state.tool_calls].count("fetch-corporate-actions") == 2


def test_quarterly_data_is_fetched_one_quarter_at_a_time(run):
    state = run(DISCOVERY_Q)
    quarterly = [c for c in state.tool_calls if c.tool == "fetch-quarterly-financials"]
    assert all(c.args.get("n_quarters") in (None, 1) for c in quarterly)
    assert {c.args.get("report_date") for c in quarterly} - {None} == {"2025-06-30"}


def test_sector_members_skip_the_paid_overview_section(run):
    state = run(DISCOVERY_Q)
    reports = [c for c in state.tool_calls if c.tool == "fetch-company-report"]
    assert reports and all(c.args["sections"] == ["financials"] for c in reports)


def test_filings_outage_is_reported(run):
    adapter = MockSectorsAdapter(failures={"get_filings:*": "always"})
    state = run(DISCOVERY_Q, adapter=adapter)
    assert not any(e.event_type == "ownership_change" for e in state.discovered_events)
    assert any(g.kind == "tool_error" for g in state.data_gaps)
    # Corporate actions are still discovered.
    assert any(e.event_type == "agm" for e in state.discovered_events)


def test_discovery_without_scope_asks_for_clarification(run):
    state = run("Apa saja disclosure minggu depan?")
    assert state.status == "needs_clarification"
    assert state.tool_calls == []


def test_ambiguous_company_asks_instead_of_guessing(run):
    state = run("Disclosure bank syariah minggu depan")
    assert state.status == "needs_clarification"
    assert "BRIS" in state.briefing.clarification_question
    assert any(r.trigger == "ambiguous_company" for r in state.recovery)
    assert state.tool_calls == []
