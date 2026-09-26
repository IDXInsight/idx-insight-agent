from datetime import date

import pytest

from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.config import Settings
from idx_insight.llm.base import LLMClient
from idx_insight.sectors import MockSectorsAdapter

AS_OF = date(2026, 9, 26)  # Saturday; "minggu depan" = 2026-09-28 .. 2026-10-04


class ScriptedLLM(LLMClient):
    """Deterministic stand-in for a real LLM: returns scripted outputs, records prompts."""

    name = "scripted"

    def __init__(self, structured: dict | None = None, text: str | None = None) -> None:
        self._structured = structured or {}
        self._text = text
        self.calls: list[tuple[str, str]] = []

    @property
    def available(self) -> bool:
        return True

    def structured(self, *, system, user, schema):
        self.calls.append((schema.__name__, user))
        return self._structured.get(schema.__name__)

    def generate(self, *, system, user):
        self.calls.append(("text", user))
        return self._text


@pytest.fixture
def run():
    """Run the agent against deterministic mock data at a fixed date."""

    def _run(query, *, adapter=None, llm=None, settings=None, **kwargs):
        agent = InsightAgent(adapter or MockSectorsAdapter(), llm=llm,
                             settings=settings or Settings())
        return agent.run(query, as_of=AS_OF, **kwargs)

    return _run
