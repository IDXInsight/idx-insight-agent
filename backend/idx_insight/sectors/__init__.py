"""Sectors data access layer: Agent → SectorsService → SectorsAdapter."""

from idx_insight.config import Settings
from idx_insight.sectors.adapter import (
    SectorsAdapter,
    SectorsError,
    SectorsNotFoundError,
    SectorsUnavailableError,
)
from idx_insight.sectors.credits import CreditLedger
from idx_insight.sectors.http_client import SectorsHttpClient
from idx_insight.sectors.mock_adapter import MockSectorsAdapter
from idx_insight.sectors.rest_adapter import RestSectorsAdapter
from idx_insight.sectors.service import SectorsService, ToolCallRecord, ToolResult


def build_adapter(settings: Settings) -> SectorsAdapter:
    """Mock data for tests and local development; the real REST API otherwise."""
    if settings.sectors_data_mode == "mock":
        return MockSectorsAdapter()
    local = settings.sectors_local_dir
    ledger = CreditLedger(local / "ledger.json",
                          max_per_day=settings.sectors_max_credits_per_day,
                          max_total=settings.sectors_max_credits_total)
    key = settings.sectors_api_key.get_secret_value() if settings.sectors_api_key else ""
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
