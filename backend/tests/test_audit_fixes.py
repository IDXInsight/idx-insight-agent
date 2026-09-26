"""Regression tests for issues found in the Phase 0–3 audit."""

from conftest import AS_OF

from idx_insight.agent.entities import MAX_TICKER_VERIFICATIONS, EntityResolver
from idx_insight.agent.state import AgentState
from idx_insight.sectors import MockSectorsAdapter, SectorsService

DISCOVERY_Q = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"


def resolve(query, adapter=None, **kwargs):
    service = SectorsService(adapter or MockSectorsAdapter())
    state = AgentState(query=query, as_of=AS_OF, **kwargs)
    return EntityResolver(service).resolve(state), service


# --- entity verification --------------------------------------------------------


def test_watchlist_tickers_are_verified_not_trusted():
    entities, service = resolve("disclosure minggu depan", watchlist=["BBRI", "ABCD"])
    assert entities.symbols == ["BBRI"]
    assert entities.unknown == ["ABCD"]
    assert [c.status for c in service.calls] == ["not_found"]


def test_ticker_verification_is_bounded_by_attempts():
    entities, service = resolve("Bandingkan ABCD EFGH IJKL MNOP QRST")
    assert len(service.calls) == MAX_TICKER_VERIFICATIONS
    assert entities.unknown == ["ABCD", "EFGH", "IJKL"]
    assert entities.unverified == ["MNOP", "QRST"]


def test_verification_tool_failure_is_not_reported_as_unknown():
    adapter = MockSectorsAdapter(failures={"get_company_report:*": "always"})
    entities, _ = resolve("Bandingkan BBCA dan ASII", adapter=adapter)
    assert entities.unverified == ["ASII"] and entities.unknown == []


def test_verified_ticker_report_is_reused_from_cache(run):
    state = run("Bagaimana kinerja TLKM?")  # TLKM is not in the alias table → verified first
    reports = [c for c in state.tool_calls if c.tool == "fetch-company-report"]
    assert len(reports) == 1


def test_unknown_watchlist_ticker_is_a_gap_not_a_tool_error(run):
    state = run("Disclosure minggu depan", watchlist=["BBRI", "ABCD"])
    kinds = {(g.kind, g.symbol) for g in state.data_gaps}
    assert ("unknown_company", "ABCD") in kinds
    assert not any(g.kind == "tool_error" for g in state.data_gaps)


# --- malformed data & evidence sufficiency ------------------------------------------


def test_malformed_sectors_payload_becomes_a_malformed_gap(run):
    adapter = MockSectorsAdapter(failures={"get_corporate_actions_calendar:*": "malformed"})
    state = run(DISCOVERY_Q, adapter=adapter)
    assert any(g.kind == "malformed_data" for g in state.data_gaps)
    assert state.validation.assessment.malformed
    assert state.status == "partial"


def test_informational_gaps_do_not_downgrade_a_complete_answer(run):
    state = run(DISCOVERY_Q)
    assert any(g.kind == "unsupported_capability" for g in state.data_gaps)
    assert state.validation.assessment.sufficiency == "sufficient"
    assert state.status == "completed"


def test_assessment_separates_conflicting_incomplete_and_unavailable(run):
    state = run("Bandingkan pertumbuhan BBCA, BMRI, BRIS dan BBTN")
    a = state.validation.assessment
    assert a.sufficiency == "partial"
    assert any("BMRI" in c for c in a.conflicting)
    assert any("BRIS" in i for i in a.incomplete)
    assert not a.malformed


def test_insufficient_evidence_is_stated_not_invented(run):
    state = run("Bandingkan ROE BBCA dan BBRI tahun 2023")
    assert state.validation.assessment.sufficiency == "insufficient"
    assert state.status == "insufficient_evidence"
    assert state.briefing.sections == []
