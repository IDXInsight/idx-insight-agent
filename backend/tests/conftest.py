from datetime import date

import pytest

from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.agent.state import AgentState
from idx_insight.config import Settings
from idx_insight.llm.base import LLMProvider
from idx_insight.sectors import MockSectorsAdapter

AS_OF = date(2026, 9, 26)  # Saturday; "minggu depan" = 2026-09-28 .. 2026-10-04


def gateway(provider: LLMProvider | None = None, state: AgentState | None = None) -> AgentLLM:
    """AgentLLM for unit-testing a single decision function."""
    return AgentLLM(provider, state or AgentState(query="q", as_of=AS_OF))


@pytest.fixture(autouse=True)
def _never_read_developer_env_file(monkeypatch):
    """Tests must not pick up a developer's local .env (and its API keys)."""
    import idx_insight.api.app as app_module

    monkeypatch.setattr(app_module, "load_env_file", lambda *a, **k: [])


@pytest.fixture
def run():
    """Run the agent against deterministic mock data at a fixed date."""

    def _run(query, *, adapter=None, llm=None, settings=None, **kwargs):
        agent = InsightAgent(adapter or MockSectorsAdapter(), llm=llm,
                             settings=settings or Settings())
        return agent.run(query, as_of=AS_OF, **kwargs)

    return _run
