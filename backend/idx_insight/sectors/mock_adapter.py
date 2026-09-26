"""Deterministic in-memory implementation of ``SectorsAdapter``.

Failures can be injected per ``"<method>:<SYMBOL or *>"`` key to exercise the
agent's recovery paths:

    MockSectorsAdapter(failures={"get_corporate_actions:BBNI": 1})         # fails once
    MockSectorsAdapter(failures={"get_filings:*": "always"})                # always fails
"""

from __future__ import annotations

import copy
from typing import Mapping, Sequence

from idx_insight.sectors import mock_data
from idx_insight.sectors.adapter import (
    SectorsAdapter,
    SectorsNotFoundError,
    SectorsUnavailableError,
)
from idx_insight.sectors.schemas import (
    CompanyRef,
    CompanyReport,
    CorporateActions,
    FilingsPage,
    QuarterlyFinancial,
    QuarterlyFinancialDates,
    bare_symbol,
)

_MAX_FILINGS_LIMIT = 30  # documented bound for /v2/filings/ ``limit``

_QUARTER_LABELS = {"03-31": "q1", "06-30": "q2", "09-30": "q3", "12-31": "q4"}


class MockSectorsAdapter(SectorsAdapter):
    name = "mock"

    def __init__(self, failures: Mapping[str, int | str] | None = None) -> None:
        self._failures: dict[str, int | str] = dict(failures or {})

    # -- failure injection -----------------------------------------------------

    def _maybe_fail(self, method: str, symbol: str | None = None) -> None:
        for key in (f"{method}:{symbol}" if symbol else None, f"{method}:*"):
            if key is None or key not in self._failures:
                continue
            remaining = self._failures[key]
            if remaining == "always":
                raise SectorsUnavailableError(f"mock outage for {key}")
            if isinstance(remaining, int) and remaining > 0:
                self._failures[key] = remaining - 1
                raise SectorsUnavailableError(f"mock transient failure for {key}")

    @staticmethod
    def _known(symbol: str) -> str:
        bare = bare_symbol(symbol)
        if bare not in mock_data.COMPANIES:
            raise SectorsNotFoundError(f"unknown symbol {symbol!r}")
        return bare

    # -- SectorsAdapter --------------------------------------------------------

    def list_subsectors(self) -> list[str]:
        self._maybe_fail("list_subsectors")
        return sorted(mock_data.SUBSECTORS)

    def list_companies(self, sub_sector: str) -> list[CompanyRef]:
        self._maybe_fail("list_companies", sub_sector)
        return [
            CompanyRef(symbol=f"{sym}.JK", **info)
            for sym, info in sorted(mock_data.COMPANIES.items())
            if info["sub_sector"] == sub_sector
        ]

    def get_company_report(
        self, symbol: str, sections: Sequence[str] = ("overview", "financials")
    ) -> CompanyReport:
        bare = self._known(symbol)
        self._maybe_fail("get_company_report", bare)
        raw = mock_data.company_report(bare)
        body = {k: v for k, v in raw.items() if k in ("symbol", "company_name") or k in sections}
        return CompanyReport.model_validate(copy.deepcopy(body))

    def get_quarterly_financials(
        self, symbol: str, n_quarters: int | None = None, report_date: str | None = None
    ) -> list[QuarterlyFinancial]:
        bare = self._known(symbol)
        self._maybe_fail("get_quarterly_financials", bare)
        rows = sorted(mock_data.quarterly_financials(bare), key=lambda r: r["date"], reverse=True)
        if report_date is not None:
            rows = [r for r in rows if r["date"] == report_date]
        elif n_quarters is not None:
            rows = rows[:n_quarters]
        return [QuarterlyFinancial.model_validate(copy.deepcopy(r)) for r in rows]

    def get_quarterly_financial_dates(self, symbol: str) -> QuarterlyFinancialDates:
        bare = self._known(symbol)
        self._maybe_fail("get_quarterly_financial_dates", bare)
        dates: QuarterlyFinancialDates = {}
        for row in sorted(mock_data.quarterly_financials(bare), key=lambda r: r["date"]):
            date = row["date"]
            dates.setdefault(date[:4], []).append((date, _QUARTER_LABELS[date[5:]]))
        return dates

    def get_corporate_actions(self, symbol: str) -> CorporateActions:
        bare = self._known(symbol)
        self._maybe_fail("get_corporate_actions", bare)
        body = copy.deepcopy(mock_data.CORPORATE_ACTIONS.get(bare, {}))
        return CorporateActions.model_validate({"symbol": f"{bare}.JK", "corporate_actions": body})

    def get_filings(
        self,
        *,
        symbol: str | None = None,
        sub_sector: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> FilingsPage:
        if not 1 <= limit <= _MAX_FILINGS_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_FILINGS_LIMIT}")
        bare = self._known(symbol) if symbol else None
        self._maybe_fail("get_filings", bare or sub_sector)

        def keep(row: dict) -> bool:
            day = row["timestamp"][:10]
            return (
                (bare is None or bare_symbol(row["symbol"]) == bare)
                and (sub_sector is None or row["sub_sector"] == sub_sector)
                and (start is None or day >= start)
                and (end is None or day <= end)
            )

        matched = sorted(
            (r for r in mock_data.FILINGS if keep(r)), key=lambda r: r["timestamp"], reverse=True
        )
        page = matched[offset : offset + limit]
        has_next = offset + limit < len(matched)
        return FilingsPage.model_validate(
            {
                "results": copy.deepcopy(page),
                "pagination": {
                    "total_count": len(matched),
                    "showing": len(page),
                    "limit": limit,
                    "offset": offset,
                    "has_next": has_next,
                    "has_previous": offset > 0,
                    "next_offset": offset + limit if has_next else None,
                    "previous_offset": max(offset - limit, 0) if offset > 0 else None,
                },
            }
        )
