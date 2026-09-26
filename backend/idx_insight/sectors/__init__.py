"""Sectors data access layer: Agent → SectorsService → SectorsAdapter."""

from idx_insight.config import Settings
from idx_insight.sectors.adapter import (
    SectorsAdapter,
    SectorsError,
    SectorsNotFoundError,
    SectorsUnavailableError,
)
from idx_insight.sectors.mock_adapter import MockSectorsAdapter
from idx_insight.sectors.service import SectorsService, ToolCallRecord, ToolResult


def build_adapter(settings: Settings) -> SectorsAdapter:
    if settings.sectors_data_mode == "mock":
        return MockSectorsAdapter()
    # The real MCP/REST adapter belongs to the real-integration phase (see PHASE.md).
    raise NotImplementedError("Real Sectors integration is not implemented yet (Phase 4).")


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
