"""The evaluation cases must all pass in deterministic (rules-only, mock) mode."""

import pytest

from evals.run_eval import check, run_cases
from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.sectors import MockSectorsAdapter


@pytest.fixture(scope="module")
def results():
    return run_cases(InsightAgent(MockSectorsAdapter()))


def test_all_eval_cases_pass_in_rules_only_mode(results):
    failed = {r.case_id: r.failures for r in results if not r.passed}
    assert not failed, failed
    assert len(results) >= 15


def test_eval_checks_detect_failures(run):
    state = run("Bandingkan ROE BBCA dan BBRI")
    failures = check(state, {"intent": "discovery", "language": "en",
                             "peer_metrics": ["casa_ratio"], "gap_kinds": ["malformed_data"]})
    assert len(failures) == 4
