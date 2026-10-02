"""Sectors credit accounting and hard caps.

Billing rules follow the official v2 API reference ("Billing & Credits"):
- 2xx: the endpoint's stated cost (1 by default; company report = 1 per section,
  quarterly financials = 1 per quarter returned, corporate-actions calendar =
  1 per type, natural-language screener = 3)
- 404 (addressed resource not found): 1 credit
- 400, 401/403, 429 and 5xx: free

Every request is checked against a daily and a total cap *before* it is sent,
using the worst-case cost, and recorded after it returns. Locally the ledger is a
small JSON file so caps survive restarts; a deployment keeps it in Redis
(``StoreCreditLedger``) because Vercel functions have no persistent disk.
"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Any

from idx_insight.sectors.adapter import SectorsError, SectorsUnavailableError
from idx_insight.storage import KeyValueStore, StorageError

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
    """File-backed ledger for local development (one process).

    ``reserve`` holds the worst-case cost of an in-flight request so concurrent
    requests in the same process cannot pass the cap together; ``settle`` replaces
    the hold with the actual cost.
    """

    def __init__(self, path: Path | None, *, max_per_day: int, max_total: int) -> None:
        self.path = path
        self.max_per_day = max_per_day
        self.max_total = max_total
        self._lock = threading.RLock()
        self._held = 0
        self._data: dict[str, Any] = {"total": 0, "days": {}, "requests": []}
        if path is not None and path.is_file():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def total(self) -> int:
        return int(self._data["total"])

    def today(self) -> int:
        return int(self._data["days"].get(date.today().isoformat(), 0))

    def remaining_today(self) -> int:
        return min(self.max_per_day - self.today(), self.max_total - self.total) - self._held

    def check(self, path: str, params: dict[str, Any]) -> None:
        _check_caps(max_cost(path, params), self.today() + self._held, self.total + self._held,
                    self.max_per_day, self.max_total)

    def reserve(self, path: str, params: dict[str, Any]) -> int:
        with self._lock:
            self.check(path, params)
            cost = max_cost(path, params)
            self._held += cost
            return cost

    def release(self, reserved: int) -> None:
        with self._lock:
            self._held -= reserved

    def settle(self, path: str, params: dict[str, Any], reserved: int, status: int, body: Any) -> int:
        with self._lock:
            self._held -= reserved
            return self.record(path, params, status, body)

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


class StoreCreditLedger:
    """Ledger in a shared key-value store (Redis on Vercel), safe across function instances.

    ``reserve`` adds the worst-case cost to the daily and total counters in one atomic
    step and rolls it back when a cap would be exceeded, so two concurrent requests can
    never both pass the last free credits. A store failure refuses the request.
    """

    _LOG_SIZE = 500
    _DAY_TTL = 3 * 24 * 3600

    def __init__(self, store: KeyValueStore, *, max_per_day: int, max_total: int,
                 prefix: str = "idx:") -> None:
        self.store = store
        self.max_per_day = max_per_day
        self.max_total = max_total
        self._total_key = f"{prefix}credits:total"
        self._day_prefix = f"{prefix}credits:day:"
        self._log_key = f"{prefix}credits:log"

    def _day_key(self) -> str:
        return self._day_prefix + date.today().isoformat()

    def _get(self, key: str) -> int:
        try:
            return int(self.store.get(key) or 0)
        except StorageError as exc:
            raise SectorsUnavailableError(f"credit ledger unavailable: {exc}") from None

    def _add(self, amount: int) -> list[int]:
        try:
            return self.store.incr([(self._day_key(), amount, self._DAY_TTL),
                                    (self._total_key, amount, None)])
        except StorageError as exc:
            raise SectorsUnavailableError(f"credit ledger unavailable: {exc}") from None

    @property
    def total(self) -> int:
        return self._get(self._total_key)

    def today(self) -> int:
        return self._get(self._day_key())

    def remaining_today(self) -> int:
        return min(self.max_per_day - self.today(), self.max_total - self.total)

    def reserve(self, path: str, params: dict[str, Any]) -> int:
        cost = max_cost(path, params)
        day, total = self._add(cost)
        try:
            _check_caps(cost, day - cost, total - cost, self.max_per_day, self.max_total)
        except SectorsCreditCapError:
            self._add(-cost)
            raise
        return cost

    def release(self, reserved: int) -> None:
        if reserved:
            self._add(-reserved)

    def settle(self, path: str, params: dict[str, Any], reserved: int, status: int, body: Any) -> int:
        cost = actual_cost(path, params, status, body)
        if cost != reserved:
            self._add(cost - reserved)
        self._log(path, params, status, cost)
        return cost

    def record(self, path: str, params: dict[str, Any], status: int, body: Any) -> int:
        cost = actual_cost(path, params, status, body)
        if cost:
            self._add(cost)
        self._log(path, params, status, cost)
        return cost

    def _log(self, path: str, params: dict[str, Any], status: int, cost: int) -> None:
        entry = {"day": date.today().isoformat(), "path": path, "params": params,
                 "status": status, "credits": cost}
        try:
            self.store.push(self._log_key, json.dumps(entry, default=str), self._LOG_SIZE)
        except StorageError:
            pass  # the counters are authoritative; the log is for inspection only


Ledger = CreditLedger | StoreCreditLedger


def _check_caps(cost: int, today: int, total: int, max_per_day: int, max_total: int) -> None:
    if today + cost > max_per_day:
        raise SectorsCreditCapError(
            f"daily Sectors credit cap reached ({today}/{max_per_day}); "
            f"request would cost up to {cost}")
    if total + cost > max_total:
        raise SectorsCreditCapError(
            f"total Sectors credit cap reached ({total}/{max_total}); "
            f"request would cost up to {cost}")
