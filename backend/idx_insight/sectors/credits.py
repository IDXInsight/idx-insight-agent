"""Sectors credit accounting and hard caps.

Billing rules follow the official v2 API reference ("Billing & Credits"):
- 2xx: the endpoint's stated cost (1 by default; company report = 1 per section,
  quarterly financials = 1 per quarter returned, corporate-actions calendar =
  1 per type, natural-language screener = 3)
- 404 (addressed resource not found): 1 credit
- 400, 401/403, 429 and 5xx: free

Every request is checked against a daily and a total cap *before* it is sent,
using the worst-case cost, and recorded after it returns. The ledger is a small
JSON file so caps survive restarts during development.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Any

from idx_insight.sectors.adapter import SectorsError

_DEFAULT_TYPES = 7  # corporate-actions calendar without ``type``
_DEFAULT_SECTIONS = 8  # company report without ``sections``


class SectorsCreditCapError(SectorsError):
    """Refused locally: the request could exceed the configured credit cap."""


def _count(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, (list, tuple)):
        return len(value)
    return len([v for v in str(value).split(",") if v.strip()])


def max_cost(path: str, params: dict[str, Any]) -> int:
    """Worst-case credits a request can consume if it succeeds."""
    if path.startswith("/v2/company/report/"):
        return _count(params.get("sections"), _DEFAULT_SECTIONS)
    if path.startswith("/v2/financials/quarterly/"):
        if params.get("report_date"):
            return 1
        return int(params.get("n_quarters") or 8)  # unbounded requests are capped by us
    if path.rstrip("/") == "/v2/corporate-actions":
        return _count(params.get("type"), _DEFAULT_TYPES)
    if path.rstrip("/") == "/v2/companies" and params.get("q"):
        return 3
    return 1


def actual_cost(path: str, params: dict[str, Any], status: int, body: Any) -> int:
    if status == 404:
        return 1
    if not 200 <= status < 300:
        return 0
    if path.startswith("/v2/financials/quarterly/") and isinstance(body, list):
        return len(body)
    return max_cost(path, params)


class CreditLedger:
    def __init__(self, path: Path | None, *, max_per_day: int, max_total: int) -> None:
        self.path = path
        self.max_per_day = max_per_day
        self.max_total = max_total
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"total": 0, "days": {}, "requests": []}
        if path is not None and path.is_file():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def total(self) -> int:
        return int(self._data["total"])

    def today(self) -> int:
        return int(self._data["days"].get(date.today().isoformat(), 0))

    def check(self, path: str, params: dict[str, Any]) -> None:
        cost = max_cost(path, params)
        if self.today() + cost > self.max_per_day:
            raise SectorsCreditCapError(
                f"daily Sectors credit cap reached ({self.today()}/{self.max_per_day}); "
                f"request would cost up to {cost}")
        if self.total + cost > self.max_total:
            raise SectorsCreditCapError(
                f"total Sectors credit cap reached ({self.total}/{self.max_total}); "
                f"request would cost up to {cost}")

    def record(self, path: str, params: dict[str, Any], status: int, body: Any) -> int:
        cost = actual_cost(path, params, status, body)
        with self._lock:
            day = date.today().isoformat()
            self._data["total"] = self.total + cost
            self._data["days"][day] = self._data["days"].get(day, 0) + cost
            self._data["requests"].append(
                {"day": day, "path": path, "params": params, "status": status, "credits": cost})
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
        return cost
