"""Sectors data access layer: Agent → SectorsService → SectorsAdapter."""

from idx_insight.config import Settings
from idx_insight.sectors.adapter import (
    SectorsAdapter,
    SectorsError,
    SectorsNotFoundError,
    SectorsUnavailableError,
)
from idx_insight.sectors.credits import CreditLedger, Ledger, StoreCreditLedger
from idx_insight.sectors.http_client import SectorsHttpClient, StoreResponseCache
from idx_insight.sectors.mock_adapter import MockSectorsAdapter
from idx_insight.sectors.rest_adapter import RestSectorsAdapter
from idx_insight.sectors.service import SectorsService, ToolCallRecord, ToolResult
from idx_insight.storage import KeyValueStore


def build_adapter(settings: Settings, store: KeyValueStore | None = None) -> SectorsAdapter:
    """Mock data for tests and local development; the real REST API otherwise.

    With a shared ``store`` (Redis on Vercel) the credit ledger and the response cache
    live there; without one they are files under ``SECTORS_LOCAL_DIR``.
    """
    if settings.sectors_data_mode == "mock":
        return MockSectorsAdapter()
    if store is None and settings.vercel:
        raise SectorsError("real data on Vercel needs Redis (UPSTASH_REDIS_REST_URL/TOKEN) "
                           "for the credit ledger; refusing to run without it")
    key = settings.sectors_api_key.get_secret_value() if settings.sectors_api_key else ""
    ledger: Ledger
    if store is not None:
        prefix = settings.storage_prefix
        ledger = StoreCreditLedger(store, max_per_day=settings.sectors_max_credits_per_day,
                                   max_total=settings.sectors_max_credits_total, prefix=prefix)
        client = SectorsHttpClient(api_key=key, ledger=ledger,
                                   cache=StoreResponseCache(store, prefix),
                                   cache_mode=settings.sectors_cache_mode)
    else:
        local = settings.sectors_local_dir
        ledger = CreditLedger(local / "ledger.json",
                              max_per_day=settings.sectors_max_credits_per_day,
                              max_total=settings.sectors_max_credits_total)
        client = SectorsHttpClient(api_key=key, ledger=ledger, cache_dir=local / "cache",
                                   cache_mode=settings.sectors_cache_mode)
    return RestSectorsAdapter(client)


__all__ = [
    "MockSectorsAdapter",
    "SectorsAdapter",
    "SectorsError",
    "SectorsNotFoundError",
    "SectorsService",
    "SectorsUnavailableError",
    "ToolCallRecord",
    "ToolResult",
    "build_adapter",
]
