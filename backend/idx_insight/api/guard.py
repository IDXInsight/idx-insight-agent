"""Usage limits and the answer cache for a public deployment.

Every agent run spends Sectors credits and LLM quota, so a run is admitted only
within a per-client rate limit, a daily run cap and the credit headroom; beyond the
daily LLM call cap answers fall back to the deterministic rules. Repeated questions
are answered from a cache without a new run. Counters live in the shared store
(Redis on Vercel); locally they live in process memory. A store failure refuses the
run rather than letting it through unmetered.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from idx_insight.api.schemas import QueryRequest
from idx_insight.config import Settings
from idx_insight.storage import KeyValueStore, StorageError

logger = logging.getLogger("idx_insight.api")

LimitCode = Literal["rate_limited", "daily_limit", "storage_unavailable"]
_DAY_TTL = 2 * 24 * 3600


class UsageLimitError(Exception):
    def __init__(self, code: LimitCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class UsageGuard:
    def __init__(self, store: KeyValueStore, settings: Settings,
                 clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.settings = settings
        self._clock = clock
        self._prefix = settings.storage_prefix

    def _day(self) -> str:
        return datetime.fromtimestamp(self._clock(), UTC).date().isoformat()

    def answer_key(self, request: QueryRequest) -> str:
        """Same question, scope, language and day → same answer (data and model fixed)."""
        s = self.settings
        material = {
            "q": " ".join(request.query.lower().split()),
            "watchlist": sorted(request.watchlist),
            "sub_sector": request.sub_sector,
            "language": request.language,
            "as_of": request.as_of.isoformat() if request.as_of else self._day(),
            "data": s.sectors_data_mode,
            "llm": [s.llm_provider, s.llm_model],
        }
        digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:32]
        return f"{self._prefix}answer:{digest}"

    def cached_answer(self, key: str) -> str | None:
        if not self.settings.answer_cache_ttl_seconds:
            return None
        try:
            return self.store.get(key)
        except StorageError as exc:
            logger.warning("answer_cache_unavailable error=%s", exc)
            return None

    def store_answer(self, key: str, payload: str) -> None:
        if not self.settings.answer_cache_ttl_seconds:
            return
        try:
            self.store.set(key, payload, self.settings.answer_cache_ttl_seconds)
        except StorageError as exc:
            logger.warning("answer_cache_unavailable error=%s", exc)

    def admit(self, client_id: str) -> None:
        """Count one agent run for this client and for the day, or refuse it."""
        s = self.settings
        window = int(self._clock() // s.rate_limit_window_seconds)
        client = hashlib.sha256(client_id.encode()).hexdigest()[:16]  # no raw IPs in the store
        client_key = f"{self._prefix}rate:{client}:{window}"
        day_key = f"{self._prefix}runs:{self._day()}"
        try:
            per_client, per_day = self.store.incr([
                (client_key, 1, s.rate_limit_window_seconds),
                (day_key, 1, _DAY_TTL),
            ])
        except StorageError as exc:
            raise UsageLimitError("storage_unavailable", f"usage counters unavailable: {exc}") from None
        if per_client > s.rate_limit_per_ip:
            raise UsageLimitError("rate_limited", "too many questions from this client; try again later")
        if per_day > s.max_queries_per_day:
            raise UsageLimitError("daily_limit", "daily question limit reached")

    def llm_allowed(self) -> bool:
        try:
            used = int(self.store.get(f"{self._prefix}llm:{self._day()}") or 0)
        except StorageError:
            return False  # unmetered LLM use is not allowed; the rules still answer
        return used < self.settings.llm_max_calls_per_day

    def record_llm_calls(self, count: int) -> None:
        if not count:
            return
        try:
            self.store.incr([(f"{self._prefix}llm:{self._day()}", count, _DAY_TTL)])
        except StorageError as exc:
            logger.warning("llm_counter_unavailable error=%s", exc)
