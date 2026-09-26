"""SectorsService — the only door from the agent to Sectors data.

Responsibilities:
- tool allowlist (only documented, approved Sectors tools can be called)
- per-request call budget (bounded tool usage)
- bounded retry for transient failures (never blind retry loops)
- response cache (identical calls within a request are served once)
- call log: every call gets a ``call_id`` that evidence items point to
- schema guard: a response that does not match the documented shape is reported
  as ``malformed`` instead of crashing the agent

Errors never propagate as exceptions to the agent; they come back as a failed
``ToolResult`` so the agent can make an explicit recovery decision.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from idx_insight.sectors.adapter import SectorsAdapter, SectorsError, SectorsNotFoundError
from idx_insight.sectors.credits import SectorsCreditCapError
from idx_insight.sectors.schemas import (
    CompanyRef,
    CompanyReport,
    CorporateActions,
    CorporateActionsCalendar,
    FilingsPage,
    QuarterlyFinancial,
    QuarterlyFinancialDates,
)

T = TypeVar("T")

# adapter method -> documented Sectors MCP tool name
TOOL_NAMES: dict[str, str] = {
    "list_subsectors": "get-subsectors",
    "list_companies": "fetch-companies-by-subsector",
    "get_company_report": "fetch-company-report",
    "get_quarterly_financials": "fetch-quarterly-financials",
    "get_quarterly_financial_dates": "fetch-quarterly-financial-dates",
    "get_corporate_actions": "fetch-corporate-actions",
    # Market-wide calendar; REST only (GET /v2/corporate-actions/), no MCP tool listed.
    "get_corporate_actions_calendar": "corporate-actions-calendar",
    "get_filings": "fetch-filings",
}

DEFAULT_ALLOWLIST: frozenset[str] = frozenset(TOOL_NAMES.values())

CallStatus = Literal["ok", "error", "not_found", "not_allowed", "budget_exhausted", "malformed"]


class ToolCallRecord(BaseModel):
    call_id: str
    tool: str
    args: dict[str, Any]
    status: CallStatus
    attempts: int = 0
    error: str | None = None


@dataclass(frozen=True)
class ToolResult(Generic[T]):
    call_id: str
    tool: str
    status: CallStatus
    data: T | None = None
    error: str | None = None
    cached: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class SectorsService:
    def __init__(
        self,
        adapter: SectorsAdapter,
        *,
        max_calls: int = 30,
        max_retries: int = 1,
        allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
    ) -> None:
        self.adapter = adapter
        self.max_calls = max_calls
        self.max_retries = max_retries
        self.allowlist = allowlist
        self.calls: list[ToolCallRecord] = []
        self.cache_hits = 0
        self._cache: dict[str, ToolResult[Any]] = {}

    @property
    def attempts_made(self) -> int:
        """Adapter invocations so far; retries count against the budget too."""
        return sum(c.attempts for c in self.calls)

    @property
    def budget_remaining(self) -> int:
        return max(self.max_calls - self.attempts_made, 0)

    # -- core ------------------------------------------------------------------

    def _invoke(self, method: str, fn: Callable[[], T], args: dict[str, Any]) -> ToolResult[T]:
        tool = TOOL_NAMES[method]
        key = f"{tool}:{json.dumps(args, sort_keys=True, default=str)}"
        if key in self._cache:
            self.cache_hits += 1
            cached = self._cache[key]
            return ToolResult(cached.call_id, tool, cached.status, cached.data, cached.error, True)

        call_id = f"call-{len(self.calls) + 1:03d}"
        record = ToolCallRecord(call_id=call_id, tool=tool, args=args, status="ok")
        self.calls.append(record)

        if tool not in self.allowlist:
            record.status, record.error = "not_allowed", f"tool {tool} is not allowlisted"
            return ToolResult(call_id, tool, record.status, error=record.error)

        last_error: str | None = None
        for _ in range(1 + self.max_retries):
            if self.budget_remaining == 0:
                record.status, record.error = "budget_exhausted", "tool-call budget exhausted"
                return ToolResult(call_id, tool, record.status, error=record.error)
            record.attempts += 1
            try:
                data = fn()
            except SectorsCreditCapError as exc:
                # Refused locally before sending: nothing was spent, do not retry.
                record.attempts -= 1
                record.status, record.error = "budget_exhausted", str(exc)
                return ToolResult(call_id, tool, "budget_exhausted", error=str(exc))
            except SectorsNotFoundError as exc:
                record.status, record.error = "not_found", str(exc)
                result: ToolResult[T] = ToolResult(call_id, tool, "not_found", error=str(exc))
                self._cache[key] = result
                return result
            except ValidationError as exc:
                # Not retried: the same source would return the same shape again.
                first = exc.errors()[0] if exc.errors() else {}
                where = ".".join(str(p) for p in first.get("loc", ()))
                record.status = "malformed"
                record.error = f"response does not match schema at '{where}': {first.get('msg', '')}"
                return ToolResult(call_id, tool, "malformed", error=record.error)
            except SectorsError as exc:
                last_error = str(exc)
                if not exc.retryable:
                    break
                continue
            result = ToolResult(call_id, tool, "ok", data=data)
            self._cache[key] = result
            return result

        record.status, record.error = "error", last_error
        return ToolResult(call_id, tool, "error", error=last_error)

    # -- typed facade ----------------------------------------------------------

    def list_subsectors(self) -> ToolResult[list[str]]:
        return self._invoke("list_subsectors", self.adapter.list_subsectors, {})

    def list_companies(self, sub_sector: str, limit: int = 12) -> ToolResult[list[CompanyRef]]:
        return self._invoke(
            "list_companies",
            lambda: self.adapter.list_companies(sub_sector, limit),
            {"sub_sector": sub_sector, "limit": limit},
        )

    def company_report(
        self, symbol: str, sections: tuple[str, ...] = ("overview", "financials")
    ) -> ToolResult[CompanyReport]:
        return self._invoke(
            "get_company_report",
            lambda: self.adapter.get_company_report(symbol, sections),
            {"symbol": symbol, "sections": list(sections)},
        )

    def quarterly_financials(
        self, symbol: str, n_quarters: int | None = None, report_date: str | None = None
    ) -> ToolResult[list[QuarterlyFinancial]]:
        return self._invoke(
            "get_quarterly_financials",
            lambda: self.adapter.get_quarterly_financials(symbol, n_quarters, report_date),
            {"symbol": symbol, "n_quarters": n_quarters, "report_date": report_date},
        )

    def quarterly_financial_dates(self, symbol: str) -> ToolResult[QuarterlyFinancialDates]:
        return self._invoke(
            "get_quarterly_financial_dates",
            lambda: self.adapter.get_quarterly_financial_dates(symbol),
            {"symbol": symbol},
        )

    def corporate_actions(self, symbol: str) -> ToolResult[CorporateActions]:
        return self._invoke(
            "get_corporate_actions",
            lambda: self.adapter.get_corporate_actions(symbol),
            {"symbol": symbol},
        )

    def corporate_actions_calendar(
        self, start: str, end: str, types: tuple[str, ...] = ("agm", "dividend", "stock_split")
    ) -> ToolResult[CorporateActionsCalendar]:
        return self._invoke(
            "get_corporate_actions_calendar",
            lambda: self.adapter.get_corporate_actions_calendar(start, end, types),
            {"start": start, "end": end, "types": list(types)},
        )

    def filings(
        self,
        *,
        symbol: str | None = None,
        sub_sector: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ToolResult[FilingsPage]:
        args = {"symbol": symbol, "sub_sector": sub_sector, "start": start, "end": end,
                "limit": limit, "offset": offset}
        return self._invoke(
            "get_filings",
            lambda: self.adapter.get_filings(**args),
            args,
        )
