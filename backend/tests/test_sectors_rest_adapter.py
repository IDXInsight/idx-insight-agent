"""Real Sectors REST adapter against a fake transport.

Payloads are synthetic: they follow the response shapes verified on 2026-09-27
but contain made-up values, so no Sectors data is stored in the repository.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from idx_insight.sectors import SectorsService
from idx_insight.sectors.credits import CreditLedger
from idx_insight.sectors.http_client import SectorsHttpClient
from idx_insight.sectors.rest_adapter import RestSectorsAdapter

TODAY = datetime.now(UTC).date()


class Router:
    """Fake Sectors API: path → synthetic JSON; records query parameters."""

    def __init__(self, routes):
        self.routes = routes
        self.seen: list[tuple[str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.seen.append((request.url.path, params))
        status, body = self.routes[request.url.path]
        return httpx.Response(status, json=body)


def adapter_for(tmp_path, routes, **ledger_kw):
    router = Router(routes)
    ledger = CreditLedger(tmp_path / "ledger.json", max_per_day=ledger_kw.get("per_day", 100),
                          max_total=ledger_kw.get("total", 100))
    client = SectorsHttpClient(api_key="k", ledger=ledger, cache_dir=tmp_path / "cache",
                               client=httpx.Client(base_url="https://api.sectors.app",
                                                   transport=httpx.MockTransport(router)))
    return RestSectorsAdapter(client), router, ledger


QUARTER = {"symbol": "ZZZZ.JK", "date": "2026-06-30", "revenue": 10.0, "earnings": 2.0,
           "total_assets": 100.0, "total_equity": 20.0,
           "financials_sector_metrics": {"net_interest_income": 5.0, "gross_loan": 60.0,
                                         "total_deposit": 80.0, "current_account": 30.0}}


def test_subsectors_are_mapped_to_slugs(tmp_path):
    adapter, _, _ = adapter_for(tmp_path, {"/v2/subsectors/": (200, [
        {"sector": "financials", "subsector": "banks"},
        {"sector": "technology", "subsector": "software-it-services"}])})
    assert adapter.list_subsectors() == ["banks", "software-it-services"]


def test_sector_members_use_one_screener_call_ordered_by_market_cap(tmp_path):
    adapter, router, ledger = adapter_for(tmp_path, {"/v2/companies/": (200, {
        "results": [{"symbol": "AAAA.JK", "company_name": "Bank A"},
                    {"symbol": "BBBB.JK", "company_name": "Bank B"}],
        "pagination": {"total_count": 2}})})
    companies = adapter.list_companies("banks", limit=12)
    assert [c.symbol for c in companies] == ["AAAA.JK", "BBBB.JK"]
    path, params = router.seen[0]
    assert params == {"where": "sub_sector = 'banks'", "order_by": "-market_cap", "limit": "12"}
    assert ledger.total == 1


def test_company_report_requests_only_the_sections_needed(tmp_path):
    adapter, router, ledger = adapter_for(tmp_path, {"/v2/company/report/ZZZZ/": (200, {
        "symbol": "ZZZZ.JK", "company_name": "Z",
        "financials": {"historical_financial_ratio": [
            {"year": "2025", "profitability": {"roe": 0.1}}]}})})
    report = adapter.get_company_report("zzzz.jk", ("financials",))
    assert report.financials.historical_financial_ratio[0].year == 2025  # "2025" → int
    assert router.seen[0][1] == {"sections": "financials"} and ledger.total == 1


def test_quarterly_financials_cost_one_credit_per_quarter(tmp_path):
    adapter, router, ledger = adapter_for(tmp_path, {
        "/v2/financials/quarterly/ZZZZ/": (200, [QUARTER])})
    rows = adapter.get_quarterly_financials("ZZZZ")
    assert rows[0].financials_sector_metrics.total_deposit == 80.0
    assert router.seen[0][1] == {"n_quarters": "1"}
    adapter.get_quarterly_financials("ZZZZ", report_date="2025-06-30")
    assert router.seen[1][1] == {"report_date": "2025-06-30", "approx": "false"}
    assert ledger.total == 2


def test_calendar_requests_only_the_types_needed(tmp_path):
    adapter, router, ledger = adapter_for(tmp_path, {"/v2/corporate-actions/": (200, {
        "start": "2026-09-28", "end": "2026-10-04",
        "agm": [{"symbol": "ZZZZ.JK", "agm_date": "2026-09-30", "agm_time": "09:00:00"}],
        "dividend": [], "stock_split": []})})
    calendar = adapter.get_corporate_actions_calendar("2026-09-28", "2026-10-04")
    assert calendar.agm[0].symbol == "ZZZZ.JK"
    assert router.seen[0][1]["type"] == "agm,dividend,stock_split"
    assert ledger.total == 3


def test_filings_end_date_is_clamped_to_sectors_today(tmp_path):
    page = {"results": [], "pagination": {"total_count": 0, "showing": 0, "limit": 30,
                                          "offset": 0, "has_next": False,
                                          "has_previous": False}}
    adapter, router, _ = adapter_for(tmp_path, {"/v2/filings/": (200, page)})
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    adapter.get_filings(sub_sector="banks", start="2026-01-01", end=tomorrow, limit=30)
    assert router.seen[0][1]["end"] == TODAY.isoformat()


def test_future_only_filing_window_costs_nothing(tmp_path):
    adapter, router, ledger = adapter_for(tmp_path, {})
    start = (TODAY + timedelta(days=3)).isoformat()
    page = adapter.get_filings(sub_sector="banks", start=start, end=start, limit=30)
    assert page.results == [] and router.seen == [] and ledger.total == 0


def test_invalid_symbols_are_rejected_before_any_request(tmp_path):
    adapter, router, _ = adapter_for(tmp_path, {})
    with pytest.raises(Exception, match="invalid IDX symbol"):
        adapter.get_company_report("BBCA'; DROP", ("financials",))
    assert router.seen == []


def test_credit_cap_surfaces_as_budget_exhausted_in_the_service(tmp_path):
    adapter, router, _ = adapter_for(tmp_path, {"/v2/corporate-actions/": (200, {})}, per_day=2)
    service = SectorsService(adapter)
    result = service.corporate_actions_calendar("2026-09-28", "2026-10-04")  # needs 3 credits
    assert result.status == "budget_exhausted"
    assert router.seen == [] and service.calls[0].attempts == 0
