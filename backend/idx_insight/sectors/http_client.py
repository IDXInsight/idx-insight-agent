"""Low-level Sectors REST client: cache → credit cap → HTTP → ledger.

- ``cache_mode="readwrite"`` (default): serve from the local cache when fresh,
  otherwise call the API and store the raw JSON (the cache doubles as the
  local recording of real responses; it is git-ignored).
- ``cache_mode="replay"``: never call the API; a cache miss is an error. Use it
  to develop and rehearse with real data at zero credit cost.
- ``cache_mode="off"``: always call the API (still capped and recorded).

The cache lives in files locally (``FileResponseCache``) and in Redis on a
deployment (``StoreResponseCache``).

The API key is sent only in the ``Authorization`` header and never written to
the cache, the ledger, logs or error messages.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import httpx

from idx_insight.sectors.adapter import SectorsError, SectorsNotFoundError, SectorsUnavailableError
from idx_insight.sectors.credits import Ledger
from idx_insight.storage import KeyValueStore, StorageError

logger = logging.getLogger("idx_insight.sectors")

BASE_URL = "https://api.sectors.app"
CacheMode = Literal["readwrite", "replay", "off"]

# How long cached responses stay fresh, by path prefix (first match wins).
_TTL: list[tuple[str, timedelta]] = [
    ("/v2/subsectors", timedelta(days=7)),
    ("/v2/company/get_quarterly_financial_dates", timedelta(days=1)),
    ("/v2/filings", timedelta(hours=6)),
    ("/v2/corporate-actions", timedelta(hours=6)),
    ("/v2/company/corporate-actions", timedelta(hours=6)),
    ("", timedelta(hours=24)),
]
_BACKOFF_SECONDS = (1.0, 2.0)  # bounded exponential backoff on HTTP 429


class SectorsAuthError(SectorsError):
    """Invalid or unauthorised API key (401/403)."""


class SectorsBadRequestError(SectorsError):
    """Rejected before lookup (400); free of charge."""


def _ttl(path: str) -> timedelta:
    return next(ttl for prefix, ttl in _TTL if path.startswith(prefix))


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in sorted(params.items()) if v not in (None, "")}


def _cache_key(path: str, params: dict[str, Any]) -> str:
    key = json.dumps({"path": path, "params": params}, sort_keys=True, default=str)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


class FileResponseCache:
    """Raw responses as JSON files (local development; doubles as the local recording)."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _file(self, path: str, params: dict[str, Any]) -> Path:
        folder = path.strip("/").split("/")[1] if "/" in path.strip("/") else "root"
        return self.directory / folder / f"{_cache_key(path, params)}.json"

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        file = self._file(path, params)
        return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else None

    def put(self, path: str, params: dict[str, Any], entry: dict[str, Any]) -> None:
        file = self._file(path, params)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(entry, indent=1), encoding="utf-8")


class StoreResponseCache:
    """Raw responses in the shared store (Redis on Vercel), expiring with their freshness TTL.

    A store failure is treated as a cache miss; the credit ledger still guards the request.
    """

    def __init__(self, store: KeyValueStore, prefix: str = "idx:") -> None:
        self.store = store
        self.prefix = f"{prefix}sectors:"

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        try:
            raw = self.store.get(self.prefix + _cache_key(path, params))
        except StorageError as exc:
            logger.warning("sectors_cache_unavailable error=%s", exc)
            return None
        return json.loads(raw) if raw else None

    def put(self, path: str, params: dict[str, Any], entry: dict[str, Any]) -> None:
        ttl = int(_ttl(path).total_seconds())
        try:
            self.store.set(self.prefix + _cache_key(path, params), json.dumps(entry), ttl)
        except StorageError as exc:
            logger.warning("sectors_cache_unavailable error=%s", exc)


ResponseCache = FileResponseCache | StoreResponseCache


class SectorsHttpClient:
    def __init__(self, *, api_key: str, ledger: Ledger, cache_dir: Path | None = None,
                 cache: ResponseCache | None = None, cache_mode: CacheMode = "readwrite",
                 timeout: float = 20.0, client: httpx.Client | None = None,
                 sleep=time.sleep) -> None:
        if not api_key and cache_mode != "replay":
            raise SectorsAuthError("SECTORS_API_KEY is not set")
        self._api_key = api_key
        self.ledger = ledger
        self.cache = cache if cache is not None else (
            FileResponseCache(cache_dir) if cache_dir is not None else None)
        self.cache_mode = cache_mode
        self.timeout = timeout
        self._client = client or httpx.Client(base_url=BASE_URL)
        self._sleep = sleep

    # -- cache ---------------------------------------------------------------------

    def _read_cache(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        if self.cache is None:
            return None
        entry = self.cache.get(path, params)
        if entry is None:
            return None
        fetched = datetime.fromisoformat(entry["fetched_at"])
        if self.cache_mode == "readwrite" and datetime.now() - fetched > _ttl(path):
            return None
        return entry

    def _write_cache(self, path: str, params: dict[str, Any], status: int, body: Any) -> None:
        if self.cache is None or self.cache_mode == "off":
            return
        self.cache.put(path, params, {"path": path, "params": params, "status": status,
                                      "fetched_at": datetime.now().isoformat(timespec="seconds"),
                                      "body": body})

    # -- request -------------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Return the JSON body of a successful response or raise a ``SectorsError``."""
        params = _clean(params or {})
        if self.cache_mode != "off":
            cached = self._read_cache(path, params)
            if cached is not None:
                return self._result(path, cached["status"], cached["body"])
            if self.cache_mode == "replay":
                raise SectorsUnavailableError(f"replay mode: {path} is not in the local cache")

        reserved = self.ledger.reserve(path, params)
        try:
            response = self._send(path, params)
        except BaseException:
            self.ledger.release(reserved)
            raise
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = None
        credits = self.ledger.settle(path, params, reserved, status, body)
        logger.info("sectors_call path=%s status=%s credits=%s total=%s", path, status, credits,
                    self.ledger.total)
        if status in (200, 404):
            self._write_cache(path, params, status, body)
        return self._result(path, status, body)

    def _send(self, path: str, params: dict[str, Any]) -> httpx.Response:
        response = None
        for delay in (*_BACKOFF_SECONDS, None):
            try:
                response = self._client.get(path, params=params, timeout=self.timeout,
                                            headers={"Authorization": self._api_key})
            except httpx.TimeoutException:
                raise SectorsUnavailableError(f"Sectors timed out after {self.timeout:g}s") from None
            except httpx.HTTPError as exc:
                raise SectorsUnavailableError(f"Sectors unreachable ({type(exc).__name__})") from None
            if response.status_code != 429 or delay is None:
                break
            self.ledger.record(path, params, 429, None)
            self._sleep(delay)
        assert response is not None
        return response

    @staticmethod
    def _result(path: str, status: int, body: Any) -> Any:
        if 200 <= status < 300:
            if body is None:
                raise SectorsError(f"{path} returned a non-JSON body")
            return body
        message = ""
        if isinstance(body, dict):
            message = str(body.get("message") or body.get("detail") or body.get("error") or "")[:200]
        detail = f"{path} HTTP {status}" + (f": {message}" if message else "")
        if status == 404:
            raise SectorsNotFoundError(detail)
        if status in (401, 403):
            raise SectorsAuthError(detail)
        if status == 400:
            raise SectorsBadRequestError(detail)
        if status == 429:
            raise SectorsError(f"{detail} (rate limit after bounded backoff)")
        raise SectorsUnavailableError(detail)
