"""Real Sectors adapter over the v2 REST API (https://api.sectors.app/v2/).

Shapes verified against live responses on 2026-09-27. All requests go through
``SectorsHttpClient`` (credit caps, ledger, local cache/replay, 429 backoff).
Parameters are chosen for the lowest documented credit cost.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from idx_insight.sectors.adapter import SectorsAdapter, SectorsError
from idx_insight.sectors.http_client import SectorsHttpClient
from idx_insight.sectors.schemas import (
    CompanyRef,
    CompanyReport,
    CorporateActions,
    CorporateActionsCalendar,
    FilingsPage,
    Pagination,
    QuarterlyFinancial,
    QuarterlyFinancialDates,
    bare_symbol,
)

_SYMBOL = re.compile(r"^[A-Z]{4}$")
_SLUG = re.compile(r"^[a-z]+(-[a-z]+)*$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Screener field, optionally with a period: roe[2025], earnings_q[Q2-2026].
_FIELD = re.compile(r"^[a-z][a-z0-9_]*(\[(\d{4}|Q[1-4]-\d{4})\])?$")
# Lower bound that keeps every real value while making the screener return it.
_ANY_VALUE = "-1000000000000000000"
_SCREENER_MAX_LIMIT = 200


def _symbol(value: str) -> str:
    bare = bare_symbol(value.strip())
    if not _SYMBOL.match(bare):
        raise SectorsError(f"invalid IDX symbol {value!r}")  # never sent: a 404 would cost a credit
    return bare


def _sectors_today() -> str:
    """Sectors validates dates against its own (UTC) calendar day."""
    return datetime.now(UTC).date().isoformat()


class RestSectorsAdapter(SectorsAdapter):
    name = "sectors"

    def __init__(self, client: SectorsHttpClient) -> None:
        self.client = client

    def list_subsectors(self) -> list[str]:
        rows = self.client.get("/v2/subsectors/")
        return sorted({row["subsector"] for row in rows if row.get("subsector")})

    def list_companies(self, sub_sector: str, limit: int = 12) -> list[CompanyRef]:
        if not _SLUG.match(sub_sector):
            raise SectorsError(f"invalid sub-sector slug {sub_sector!r}")
        # The screener matches sub-sector names case-insensitively ("banks" = "Banks").
        # UNVERIFIED for multi-word slugs; only single-word sub-sectors are used so far.
        body = self.client.get("/v2/companies/", {
            "where": f"sub_sector = '{sub_sector.replace('-', ' ')}'",
            "order_by": "-market_cap",
            "limit": max(1, min(limit, _SCREENER_MAX_LIMIT)),
        })
        return [CompanyRef(symbol=row["symbol"], company_name=row.get("company_name") or "",
                           sub_sector=sub_sector)
                for row in body.get("results", [])]

    def get_company_report(self, symbol: str,
                           sections: Sequence[str] = ("overview", "financials")) -> CompanyReport:
        body = self.client.get(f"/v2/company/report/{_symbol(symbol)}/",
                               {"sections": ",".join(sections)})
        return CompanyReport.model_validate(body)

    def get_quarterly_financials(self, symbol: str, n_quarters: int | None = None,
                                 report_date: str | None = None) -> list[QuarterlyFinancial]:
        params: dict = {}
        if report_date is not None:
            # Exact match only: an approximate match could silently return another quarter.
            params = {"report_date": report_date, "approx": "false"}
        else:
            params = {"n_quarters": n_quarters or 1}  # 1 credit per quarter returned
        body = self.client.get(f"/v2/financials/quarterly/{_symbol(symbol)}/", params)
        return [QuarterlyFinancial.model_validate(row) for row in body]

    def get_quarterly_financial_dates(self, symbol: str) -> QuarterlyFinancialDates:
        body = self.client.get(f"/v2/company/get_quarterly_financial_dates/{_symbol(symbol)}/")
        return {year: [tuple(pair) for pair in pairs] for year, pairs in body.items()}

    def get_corporate_actions(self, symbol: str) -> CorporateActions:
        body = self.client.get(f"/v2/company/corporate-actions/{_symbol(symbol)}/")
        return CorporateActions.model_validate(body)

    def get_corporate_actions_calendar(
        self, start: str, end: str, types: Sequence[str] = ("agm", "dividend", "stock_split")
    ) -> CorporateActionsCalendar:
        body = self.client.get("/v2/corporate-actions/",
                               {"start": start, "end": end, "type": ",".join(types)})
        return CorporateActionsCalendar.model_validate(body)

    def get_company_metrics(self, symbols: Sequence[str],
                            fields: Sequence[str]) -> dict[str, dict[str, float]]:
        bare = sorted({_symbol(s) for s in symbols})
        for field in fields:
            if not _FIELD.match(field):
                raise SectorsError(f"invalid screener field {field!r}")
        if not bare or not fields:
            return {}
        # Verified 2026-09-27: the screener matches symbols only with the ".JK" suffix,
        # and returns in ``query_values`` the fields used in ``where`` / ``order_by``.
        # The filter also drops companies with a missing value.
        listed = ", ".join(f"'{s}.JK'" for s in bare)
        conditions = " and ".join(f"{f} > {_ANY_VALUE}" for f in fields)
        body = self.client.get("/v2/companies/", {
            "where": f"symbol in [{listed}] and {conditions}",
            "limit": len(bare),
            "include_query_values": "true",
        })
        out: dict[str, dict[str, float]] = {}
        for row in body.get("results", []):
            values = row.get("query_values") or {}
            if all(values.get(f) is not None for f in fields):
                out[bare_symbol(row["symbol"])] = {f: float(values[f]) for f in fields}
        return out

    def get_filings(self, *, symbol: str | None = None, sub_sector: str | None = None,
                    start: str | None = None, end: str | None = None, limit: int = 20,
                    offset: int = 0) -> FilingsPage:
        if not 1 <= limit <= 30:
            raise ValueError("limit must be between 1 and 30")
        today = _sectors_today()
        if end is not None and _DATE.match(end) and end > today:
            end = today  # Sectors rejects future end dates with HTTP 400
        if start is not None and end is not None and start > end:
            # The whole window is in the future: nothing to fetch, no credit spent.
            return FilingsPage(results=[], pagination=Pagination(
                total_count=0, showing=0, limit=limit, offset=offset, has_next=False,
                has_previous=False))
        params = {"start": start, "end": end, "limit": limit, "offset": offset,
                  "symbol": _symbol(symbol) if symbol else None, "sub_sector": sub_sector}
        return FilingsPage.model_validate(self.client.get("/v2/filings/", params))
