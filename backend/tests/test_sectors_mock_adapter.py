import pytest

from idx_insight.config import Settings
from idx_insight.sectors import (
    MockSectorsAdapter,
    SectorsNotFoundError,
    SectorsUnavailableError,
    build_adapter,
)


@pytest.fixture
def adapter():
    return MockSectorsAdapter()


def test_company_listing_by_subsector(adapter):
    banks = {c.symbol for c in adapter.list_companies("banks")}
    assert {"BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK"} <= banks
    assert "TLKM.JK" not in banks
    assert adapter.list_companies("unknown-subsector") == []


def test_quarterly_financials_follow_documented_shape(adapter):
    rows = adapter.get_quarterly_financials("BBCA", n_quarters=2)
    assert [r.date for r in rows] == ["2026-06-30", "2026-03-31"]
    q1 = rows[1]
    # Values taken from the official documentation example.
    assert q1.earnings == 14695475000000
    assert q1.financials_sector_metrics.total_deposit == 1276408911000000


def test_accepts_jk_suffix_and_lowercase(adapter):
    assert adapter.get_quarterly_financials("bbca.jk", n_quarters=1)[0].symbol == "BBCA.JK"


def test_unavailable_period_returns_empty(adapter):
    assert adapter.get_quarterly_financials("BBTN", report_date="2026-06-30") == []


def test_incomplete_report_has_no_sector_metrics(adapter):
    latest = adapter.get_quarterly_financials("BRIS", n_quarters=1)[0]
    assert latest.financials_sector_metrics is None


def test_quarterly_dates_shape(adapter):
    dates = adapter.get_quarterly_financial_dates("BBTN")
    assert dates["2026"] == [("2026-03-31", "q1")]


def test_unknown_symbol_raises_not_found(adapter):
    with pytest.raises(SectorsNotFoundError):
        adapter.get_company_report("XXXX")


def test_company_report_sections_are_respected(adapter):
    report = adapter.get_company_report("BBNI", sections=("overview",))
    assert report.overview.sub_sector == "banks"
    assert report.financials is None


def test_empty_corporate_actions(adapter):
    body = adapter.get_corporate_actions("BTPS").corporate_actions
    assert body.agm is None and body.dividend is None


def test_filings_filters_and_pagination(adapter):
    page = adapter.get_filings(sub_sector="banks", start="2026-09-12", end="2026-09-26", limit=2)
    assert page.pagination.showing == 2
    assert page.pagination.has_next is True
    assert all(r.sub_sector == "banks" for r in page.results)
    assert page.results[0].timestamp >= page.results[1].timestamp


def test_filings_limit_is_bounded(adapter):
    with pytest.raises(ValueError):
        adapter.get_filings(limit=31)


def test_injected_transient_failure_then_recovers():
    adapter = MockSectorsAdapter(failures={"get_corporate_actions:BBNI": 1})
    with pytest.raises(SectorsUnavailableError):
        adapter.get_corporate_actions("BBNI")
    assert adapter.get_corporate_actions("BBNI").symbol == "BBNI.JK"


def test_build_adapter_real_mode_is_not_implemented():
    with pytest.raises(NotImplementedError):
        build_adapter(Settings(sectors_data_mode="real"))


def test_injected_malformed_payload_raises_validation_error():
    from pydantic import ValidationError

    adapter = MockSectorsAdapter(failures={"get_filings:*": "malformed"})
    with pytest.raises(ValidationError):
        adapter.get_filings(sub_sector="banks")
