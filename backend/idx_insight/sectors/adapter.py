"""Sectors adapter interface.

The agent never talks to an adapter directly — it goes through
``SectorsService``. Adapters translate one Sectors capability into our schemas.
``MockSectorsAdapter`` is the only implementation until real integration
(Phase 4) adds an MCP/REST adapter implementing the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from idx_insight.sectors.schemas import (
    CompanyRef,
    CompanyReport,
    CorporateActions,
    FilingsPage,
    QuarterlyFinancial,
    QuarterlyFinancialDates,
)


class SectorsError(Exception):
    """Base class for adapter failures."""

    retryable = False


class SectorsNotFoundError(SectorsError):
    """Symbol / resource does not exist."""


class SectorsUnavailableError(SectorsError):
    """Transient failure (timeout, 5xx, rate limit)."""

    retryable = True


class SectorsAdapter(ABC):
    """One method per documented Sectors capability we rely on.

    Method → documented MCP tool:
      list_subsectors            get-subsectors
      list_companies             fetch-companies-by-subsector
      get_company_report         fetch-company-report
      get_quarterly_financials   fetch-quarterly-financials
      get_quarterly_financial_dates  fetch-quarterly-financial-dates
      get_corporate_actions      fetch-corporate-actions
      get_filings                fetch-filings
    """

    name: str = "abstract"

    @abstractmethod
    def list_subsectors(self) -> list[str]: ...

    @abstractmethod
    def list_companies(self, sub_sector: str) -> list[CompanyRef]: ...

    @abstractmethod
    def get_company_report(
        self, symbol: str, sections: Sequence[str] = ("overview", "financials")
    ) -> CompanyReport: ...

    @abstractmethod
    def get_quarterly_financials(
        self, symbol: str, n_quarters: int | None = None, report_date: str | None = None
    ) -> list[QuarterlyFinancial]: ...

    @abstractmethod
    def get_quarterly_financial_dates(self, symbol: str) -> QuarterlyFinancialDates: ...

    @abstractmethod
    def get_corporate_actions(self, symbol: str) -> CorporateActions: ...

    @abstractmethod
    def get_filings(
        self,
        *,
        symbol: str | None = None,
        sub_sector: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> FilingsPage: ...
