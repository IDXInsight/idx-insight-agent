"""Evaluation harness: run the agent on fixed cases and check expected behaviour.

    python -m evals.run_eval              # rules-only, mock Sectors (deterministic)
    python -m evals.run_eval --live       # use LLM_PROVIDER / keys from the environment or .env

Sectors data follows SECTORS_DATA_MODE, so the same cases can be re-run once the
real Sectors adapter exists. Checks cover decisions and guardrails, not wording.
Exit code is non-zero when any case fails.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import dataclass, field
from datetime import date

from idx_insight.agent.orchestrator import InsightAgent
from idx_insight.agent.state import AgentState
from idx_insight.agent.synthesis import language_issue
from idx_insight.config import Settings, load_env_file
from idx_insight.llm import build_llm_provider
from idx_insight.sectors import build_adapter

CASES_FILE = pathlib.Path(__file__).with_name("cases.json")
DEFAULT_AS_OF = date(2026, 9, 26)  # the date the mock fixtures are built around


@dataclass
class CaseResult:
    case_id: str
    failures: list[str] = field(default_factory=list)
    llm_calls: int = 0
    llm_failures: int = 0
    tool_calls: int = 0
    narrative: str = "-"  # "llm", "template", or "rejected: <reason>"

    @property
    def passed(self) -> bool:
        return not self.failures


def _briefing_text(state: AgentState) -> str:
    """Generated briefing text (the fixed boundary note is excluded)."""
    b = state.briefing
    if b is None:
        return ""
    parts = [b.summary, *b.data_gaps, *b.assumptions]
    parts += [f.text for s in b.sections for f in s.findings]
    parts += [f.why or "" for s in b.sections for f in s.findings]
    parts += [s.text for s in b.narrative or []]
    return "\n".join(parts)


def check(state: AgentState, expect: dict) -> list[str]:
    failures: list[str] = []

    def fail(message: str) -> None:
        failures.append(message)

    intent = state.intent.name if state.intent else None
    if "intent" in expect and intent != expect["intent"]:
        fail(f"intent {intent} != {expect['intent']}")
    if "language" in expect and state.language != expect["language"]:
        fail(f"language {state.language} != {expect['language']}")
    if "status_in" in expect and state.status not in expect["status_in"]:
        fail(f"status {state.status} not in {expect['status_in']}")
    if "companies" in expect and sorted(state.entities.symbols) != sorted(expect["companies"]):
        fail(f"companies {state.entities.symbols} != {expect['companies']}")
    if "advice_requested" in expect and bool(
            state.intent and state.intent.advice_requested) != expect["advice_requested"]:
        fail("advice_requested mismatch")
    if len(state.relevant_events) < expect.get("min_relevant_events", 0):
        fail(f"only {len(state.relevant_events)} relevant events")
    if len(state.duplicate_events) < expect.get("min_duplicates", 0):
        fail("duplicates not detected")
    research = {d.symbol for d in state.second_hop if d.decision == "research"}
    if missing := set(expect.get("must_research", [])) - research:
        fail(f"second-hop missed {sorted(missing)}")
    if "max_research" in expect and len(research) > expect["max_research"]:
        fail(f"researched {sorted(research)}")
    if allowed := expect.get("events_only_for"):
        if outside := {e.symbol for e in state.relevant_events} - set(allowed):
            fail(f"events outside scope: {sorted(outside)}")
    peers = state.analytics.get("peer_comparison", {})
    if missing := set(expect.get("peer_metrics", [])) - set(peers):
        fail(f"peer metrics missing {sorted(missing)}")
    for metric, period in expect.get("peer_periods", {}).items():
        if peers.get(metric, {}).get("period") != period:
            fail(f"{metric} compared on {peers.get(metric, {}).get('period')}, expected {period}")
    conflicts = {c.symbol for c in state.conflicts}
    if missing := set(expect.get("conflict_symbols", [])) - conflicts:
        fail(f"conflicts not detected for {sorted(missing)}")
    gap_kinds = {g.kind for g in state.data_gaps}
    if missing := set(expect.get("gap_kinds", [])) - gap_kinds:
        fail(f"gaps missing {sorted(missing)}")
    question = state.briefing.clarification_question if state.briefing else None
    for word in expect.get("clarification_mentions", []):
        if not question or word not in question:
            fail(f"clarification does not mention {word}")

    # Guardrails that must hold for every case.
    if issue := language_issue(_briefing_text(state)):
        fail(f"briefing guardrail: {issue}")
    accepted = set(state.validation.accepted)
    for claim in state.claims:
        if claim.claim_id in accepted and not claim.evidence_ids:
            fail(f"accepted claim {claim.claim_id} has no evidence")
    return failures


def _narrative_status(state: AgentState) -> str:
    if state.briefing is None or not state.briefing.sections:
        return "-"
    rejected = next((t.detail for t in state.trace if t.stage == "LLM narrative rejected"), None)
    if rejected:
        return f"rejected: {rejected}"
    return state.briefing.synthesis_mode


def run_cases(agent: InsightAgent, as_of: date = DEFAULT_AS_OF,
              cases_file: pathlib.Path = CASES_FILE, pause: float = 0.0) -> list[CaseResult]:
    results = []
    for i, case in enumerate(json.loads(cases_file.read_text(encoding="utf-8"))):
        if i and pause:
            time.sleep(pause)  # stay within provider rate limits (e.g. free-tier tokens/minute)
        state = agent.run(case["query"], as_of=as_of)
        results.append(CaseResult(
            case_id=case["id"],
            failures=check(state, case.get("expect", {})),
            llm_calls=len(state.llm_calls),
            llm_failures=sum(c.status != "ok" for c in state.llm_calls),
            tool_calls=sum(c.attempts for c in state.tool_calls),
            narrative=_narrative_status(state),
        ))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="use the configured LLM provider")
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    parser.add_argument("--pause", type=float, default=0.0,
                        help="seconds to wait between cases (free-tier rate limits)")
    args = parser.parse_args(argv)

    load_env_file()
    settings = Settings.from_env()
    if not args.live:
        settings = settings.model_copy(update={"llm_provider": "none"})
    agent = InsightAgent(build_adapter(settings), llm=build_llm_provider(settings),
                         settings=settings)
    model = f" ({settings.llm_model})" if settings.llm_provider != "none" else ""
    print(f"Sectors: {settings.sectors_data_mode} | LLM: {settings.llm_provider}{model} "
          f"| as_of: {args.as_of}\n")

    results = run_cases(agent, args.as_of, pause=args.pause)
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"{mark}  {r.case_id:28s} tools={r.tool_calls:2d} llm={r.llm_calls} "
              f"llm_failed={r.llm_failures}  narrative={r.narrative}")
        for failure in r.failures:
            print(f"      - {failure}")
    passed = sum(r.passed for r in results)
    print(f"\n{passed}/{len(results)} cases passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
