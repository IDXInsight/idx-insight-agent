"""Small key-value store shared by the credit ledger, the response caches and the usage guard.

- ``MemoryStore``: one process only (tests and local development).
- ``RedisRestStore``: Redis over the Upstash REST API (``POST`` with a JSON command
  array, ``Authorization: Bearer <token>``, replies ``{"result": ...}`` or
  ``{"error": ...}``; batches through ``/multi-exec``). Vercel functions have no
  persistent disk, so a deployment keeps its ledger, caches and counters here.

The token is sent only in the ``Authorization`` header and never appears in errors or logs.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import httpx

from idx_insight.config import Settings

# (key, amount, ttl in seconds or None to keep the key's current expiry)
Increment = tuple[str, int, int | None]


class StorageError(RuntimeError):
    """The store could not be reached or rejected a command."""


class KeyValueStore(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    def incr(self, items: Sequence[Increment]) -> list[int]:
        """Apply all increments atomically and return the new values in order."""
        ...

    def push(self, key: str, value: str, max_len: int) -> None:
        """Prepend ``value`` to a list and keep only the newest ``max_len`` entries."""
        ...


class MemoryStore:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._data: dict[str, tuple[Any, float | None]] = {}

    def _live(self, key: str) -> Any:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and self._clock() >= expires:
            del self._data[key]
            return None
        return value

    def _expiry(self, key: str, ttl_seconds: int | None) -> float | None:
        if ttl_seconds is not None:
            return self._clock() + ttl_seconds
        entry = self._data.get(key)
        return entry[1] if entry else None

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._live(key)
            return None if value is None else str(value)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        with self._lock:
            self._data[key] = (value, None if ttl_seconds is None else self._clock() + ttl_seconds)

    def incr(self, items: Sequence[Increment]) -> list[int]:
        with self._lock:
            results = []
            for key, amount, ttl in items:
                value = int(self._live(key) or 0) + amount
                self._data[key] = (value, self._expiry(key, ttl))
                results.append(value)
            return results

    def push(self, key: str, value: str, max_len: int) -> None:
        with self._lock:
            items = [value, *(self._live(key) or [])][:max_len]
            self._data[key] = (items, self._expiry(key, None))


class RedisRestStore:
    def __init__(self, url: str, token: str, *, timeout: float = 5.0,
                 client: httpx.Client | None = None) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client = client or httpx.Client()

    def _post(self, path: str, body: list[Any]) -> Any:
        try:
            response = self._client.post(f"{self._url}{path}", json=body, timeout=self._timeout,
                                         headers={"Authorization": f"Bearer {self._token}"})
            payload = response.json()
        except httpx.HTTPError as exc:
            raise StorageError(f"Redis unreachable ({type(exc).__name__})") from None
        except ValueError:
            raise StorageError(f"Redis returned a non-JSON reply (HTTP {response.status_code})") from None
        if isinstance(payload, dict) and "error" in payload:
            raise StorageError(f"Redis HTTP {response.status_code}: {str(payload['error'])[:200]}")
        if response.status_code >= 400:
            raise StorageError(f"Redis HTTP {response.status_code}")
        return payload

    def _command(self, *args: Any) -> Any:
        return self._post("", [str(a) for a in args])["result"]

    def _transaction(self, commands: list[list[Any]]) -> list[Any]:
        replies = self._post("/multi-exec", [[str(a) for a in c] for c in commands])
        if not isinstance(replies, list) or len(replies) != len(commands):
            raise StorageError("Redis transaction returned an unexpected reply")
        for reply in replies:
            if isinstance(reply, dict) and "error" in reply:
                raise StorageError(f"Redis command failed: {str(reply['error'])[:200]}")
        return [reply.get("result") for reply in replies]

    def get(self, key: str) -> str | None:
        value = self._command("GET", key)
        return None if value is None else str(value)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is None:
            self._command("SET", key, value)
        else:
            self._command("SET", key, value, "EX", ttl_seconds)

    def incr(self, items: Sequence[Increment]) -> list[int]:
        commands: list[list[Any]] = []
        positions = []
        for key, amount, ttl in items:
            positions.append(len(commands))
            commands.append(["INCRBY", key, amount])
            if ttl is not None:
                commands.append(["EXPIRE", key, ttl])
        results = self._transaction(commands)
        return [int(results[i]) for i in positions]

    def push(self, key: str, value: str, max_len: int) -> None:
        self._transaction([["LPUSH", key, value], ["LTRIM", key, 0, max_len - 1]])


def build_store(settings: Settings) -> KeyValueStore | None:
    """The shared Redis store when it is configured; ``None`` means local files and memory."""
    if settings.redis_rest_url and settings.redis_rest_token:
        return RedisRestStore(settings.redis_rest_url, settings.redis_rest_token.get_secret_value())
    return None
