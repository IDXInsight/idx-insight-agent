"""InsightAgent — custom orchestration of one research request.

Flow: detect language → resolve entities → resolve intent → resolve timeframe →
recovery gates → plan → execute plan steps (discovery → relevance → selective
second-hop, or financial retrieval → deterministic analytics) → evidence
validation and sufficiency → synthesis.

The runtime LLM is optional and reached only through ``AgentLLM``; with no
provider every decision uses the deterministic policies.

Each step is a small method; decisions are written to ``AgentState`` and a
concise, user-safe trace (never chain-of-thought). Trace stage names are stable
English identifiers; details are in the user's language.
"""

from __future__ import annotations

from datetime import date

from idx_insight.agent.analysis import (
    company_trends,
    event_claims,
    peer_comparison,
    second_hop_context,
)
from idx_insight.agent.discovery import (
    MAX_SCOPE_COMPANIES,
    SECTOR_DISCOVERY_LIMIT,
    DiscoveryAgent,
)
from idx_insight.agent.entities import EntityResolver
from idx_insight.agent.financials import FinancialContext
from idx_insight.agent.i18n import t
from idx_insight.agent.intent import requested_metrics, resolve_intent
from idx_insight.agent.language import Language, detect_language
from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.planner import build_plan
from idx_insight.agent.relevance import decide_second_hop, rank_events
from idx_insight.agent.state import AgentState, Briefing, RecoveryAction
from idx_insight.agent.synthesis import synthesize
from idx_insight.agent.timeframe import resolve_timeframe
from idx_insight.agent.validator import EvidenceValidator
from idx_insight.config import Settings
from idx_insight.llm.base import LLMProvider
from idx_insight.models import Event
from idx_insight.sectors.adapter import SectorsAdapter
from idx_insight.sectors.service import SectorsService


class _Run:
    """Per-request execution context (fresh service, cache and state)."""

    def __init__(self, agent: InsightAgent, state: AgentState) -> None:
        self.state = state
        self.lang = state.language
        self.settings = agent.settings
        self.llm = AgentLLM(agent.llm, state, temperature=agent.settings.llm_temperature,
                            max_output_tokens=agent.settings.llm_max_output_tokens)
        self.service = SectorsService(agent.adapter, max_calls=agent.settings.max_tool_calls)
        self.entities = EntityResolver(self.service)
        self.financials = FinancialContext(self.service, state, agent.settings.max_requeries)
        self.discovery = DiscoveryAgent(self.service, state, agent.settings.max_requeries)
        self.events: list[Event] = []
        self.second_hop_symbols: list[str] = []

    def recovery(self, trigger: str, target: str, action_key: str, outcome: str) -> None:
        self.state.recovery.append(RecoveryAction(
            trigger=trigger, target=target, action=t(self.lang, action_key),  # type: ignore[arg-type]
            outcome=outcome,
        ))

    # -- resolution --------------------------------------------------------------

    def resolve(self) -> None:
        s, lang = self.state, self.lang
        s.entities = self.entities.resolve(s)
        s.add_trace("Entities resolved", t(lang, "trace.entities",
                                           companies=", ".join(s.entities.symbols) or "-",
                                           sector=s.entities.sub_sector or "-"))
        s.intent = resolve_intent(s.query, s.entities, self.llm)
        s.add_trace("Intent resolved", t(lang, "trace.intent", name=s.intent.name,
                                         source=s.intent.source, confidence=s.intent.confidence))
        if s.intent.advice_requested:
            s.add_trace("Advice request detected", t(lang, "trace.advice"), "warning")
        s.timeframe = resolve_timeframe(s.query, s.as_of, s.intent.name, lang)
        s.add_trace("Timeframe resolved", s.timeframe.label,
                    "warning" if s.timeframe.assumed else "ok")
        if s.timeframe.assumed:
            self.recovery("ambiguous_timeframe", "timeframe", "recovery.timeframe.action",
                          s.timeframe.label)

    def clarification(self) -> str | None:
        """Recovery gates that must stop the run before any data is fetched."""
        s, lang = self.state, self.lang
        assert s.intent is not None
        if s.entities.ambiguous:
            for a in s.entities.ambiguous:
                self.recovery("ambiguous_company", a.text, "recovery.ambiguous.action",
                              "needs_clarification")
            options = "; ".join(
                t(lang, "question.option", text=a.text,
                  candidates=t(lang, "word.or").join(a.candidates))
                for a in s.entities.ambiguous)
            return t(lang, "question.which_company", options=options)
        for token in s.entities.unknown:
            self.recovery("unknown_company", token, "recovery.unknown.action",
                          t(lang, "recovery.unknown.outcome"))
            s.add_gap("unknown_company", t(lang, "gap.unknown_company", sym=token), token)
        for token in s.entities.unverified:
            self.recovery("unknown_company", token, "recovery.unverified.action",
                          t(lang, "recovery.unverified.outcome"))
            s.add_gap("unverified_company", t(lang, "gap.unverified_company", sym=token), token)
        for label in s.intent.unsupported_metrics:
            self.recovery("unsupported_metric", label, "recovery.unsupported.action",
                          t(lang, "recovery.unsupported.outcome"))
            s.add_gap("unsupported_metric", t(lang, "gap.unsupported_metric", label=label))
        if s.intent.unsupported_metrics and not (s.intent.metrics or s.intent.metric_bundles):
            s.assumptions.append(t(lang, "assumption.substitute_bundle"))
        if s.intent.name == "clarify":
            return t(lang, "question.clarify")
        if s.intent.name == "discovery" and not (s.entities.symbols or s.entities.sub_sector):
            return t(lang, "question.discovery_scope")
        if s.intent.name in ("peer_comparison", "company_context") and not (
            s.entities.symbols or s.entities.sub_sector
        ):
            return t(lang, "question.not_found")
        return None

    # -- plan steps --------------------------------------------------------------

    def _sector_scope(self, limit: int = MAX_SCOPE_COMPANIES) -> list[tuple[str, str | None]] | None:
        s = self.state
        slug = s.entities.sub_sector
        if slug is None:
            return []
        if not self.entities.verify_sub_sector(slug):
            s.add_gap("unknown_sector", t(self.lang, "gap.unknown_sector", slug=slug))
            return None
        members = self.entities.sector_members(slug, limit)
        if members is None:
            s.add_gap("tool_error", t(self.lang, "gap.sector_members", slug=slug))
            return None
        # Known sub-sector → later company reports can skip the paid overview section.
        self.financials.known_sub_sectors.update({m.symbol: slug for m in members})
        return [(m.symbol, m.company_name) for m in members]

    def step_discover_events(self) -> None:
        s = self.state
        explicit = [(c.symbol, c.company_name) for c in s.entities.companies]
        # Discovery covers the whole sector: company list, calendar and filings each cost
        # one call regardless of size. Per-company work (second-hop) is capped later.
        sector = self._sector_scope(SECTOR_DISCOVERY_LIMIT) if not explicit else []
        members = explicit or sector or []
        symbols = self.discovery.scope(members, cap=None if sector else MAX_SCOPE_COMPANIES)
        if not symbols:
            s.add_trace("Discovery selected", t(self.lang, "trace.empty_scope"), "error")
            return
        use_sector = s.entities.sub_sector if not explicit else None
        self.events = self.discovery.collect(symbols, use_sector)
        tf = s.timeframe
        assert tf is not None
        s.add_trace("Discovery selected", t(self.lang, "trace.discovery", n=len(symbols),
                                            events=len(self.events), fs=tf.filings_start,
                                            fe=tf.filings_end, s=tf.start, e=tf.end))

    def step_rank_relevance(self) -> None:
        s = self.state
        relevant = rank_events(s, self.events)
        event_claims(s)
        s.add_trace("Relevant events detected", t(self.lang, "trace.relevant", n=len(relevant),
                                                  unique=len(s.discovered_events),
                                                  dups=len(s.duplicate_events)))

    def step_second_hop_context(self) -> None:
        s = self.state
        self.second_hop_symbols = decide_second_hop(
            s, self.service.budget_remaining, self.settings.max_second_hop, self.llm)
        if not self.second_hop_symbols:
            s.add_trace("Second-hop analysis", t(self.lang, "trace.no_second_hop"), "skipped")
            return
        sources = sorted({d.source for d in s.second_hop if d.decision == "research"})
        s.add_trace(f"Second-hop analysis selected ({'+'.join(sources)})",
                    ", ".join(self.second_hop_symbols))
        second_hop_context(s, self.financials, self.second_hop_symbols)
        s.add_trace("Financial context retrieved", t(self.lang, "trace.evidence_count",
                                                     n=len(s.evidence)))

    def _analysis_symbols(self) -> list[str]:
        s = self.state
        if s.entities.symbols:
            return s.entities.symbols
        scope = self._sector_scope() or []
        return self.discovery.scope(scope)

    def step_retrieve_financial_context(self) -> None:
        s = self.state
        symbols = self._analysis_symbols()
        s.analytics["analysis_symbols"] = symbols
        # Data is fetched lazily per metric, so only what the question needs is paid for.
        s.add_trace("Analysis scope resolved", t(self.lang, "trace.scope", n=len(symbols)))

    def step_compare_peers(self) -> None:
        s = self.state
        assert s.intent is not None
        metrics = requested_metrics(s.intent)
        peer_comparison(s, self.financials, s.analytics["analysis_symbols"], metrics)
        s.add_trace("Peer metrics calculated", ", ".join(metrics))

    def step_company_trends(self) -> None:
        s = self.state
        assert s.intent is not None
        metrics = requested_metrics(s.intent)
        for m in ("earnings_growth_yoy", "revenue_growth_yoy"):
            if m not in metrics:
                metrics.append(m)
        for sym in s.analytics["analysis_symbols"]:
            company_trends(s, self.financials, sym, metrics)
        s.add_trace("Company trends calculated", ", ".join(metrics))

    def step_validate_evidence(self) -> None:
        report = EvidenceValidator(self.state).validate()
        self.state.add_trace(
            "Evidence validated",
            t(self.lang, "trace.validated", accepted=len(report.accepted),
              rejected=len(report.rejected), suff=report.assessment.sufficiency),
            "ok" if report.assessment.sufficiency == "sufficient" else "warning",
        )

    def step_synthesize(self) -> None:
        s = self.state
        s.briefing = synthesize(s, self.llm)
        s.add_trace("Response synthesized", s.briefing.synthesis_mode)


class InsightAgent:
    def __init__(self, adapter: SectorsAdapter, llm: LLMProvider | None = None,
                 settings: Settings | None = None) -> None:
        self.adapter = adapter
        self.llm = llm  # None → rules-only mode
        self.settings = settings or Settings()

    def run(self, query: str, *, as_of: date | None = None, watchlist: list[str] | None = None,
            sub_sector: str | None = None, language: Language | None = None) -> AgentState:
        state = AgentState(query=query, as_of=as_of or date.today(),
                           language=language or detect_language(query),
                           watchlist=[w.upper() for w in (watchlist or [])],
                           requested_sub_sector=sub_sector)
        run = _Run(self, state)
        run.resolve()

        question = run.clarification()
        if question:
            state.status = "needs_clarification"
            state.briefing = Briefing(title=t(state.language, "clarification.title"),
                                      summary=question,
                                      boundary_note=t(state.language, "briefing.boundary"),
                                      clarification_question=question)
            state.add_trace("Clarification requested", question, "warning")
            state.tool_calls = list(run.service.calls)
            return state

        state.plan = build_plan(state, run.llm)
        detail = " → ".join(state.plan.names)
        if state.plan.rejected_llm_plan:
            detail += t(state.language, "trace.plan_rejected", reason=state.plan.rejected_llm_plan)
        state.add_trace(f"Plan selected ({state.plan.source})", detail)

        for step in state.plan.steps:
            getattr(run, f"step_{step.name}")()

        state.tool_calls = list(run.service.calls)
        state.status = self._status(state)
        return state

    @staticmethod
    def _status(state: AgentState) -> str:
        sufficiency = state.validation.assessment.sufficiency
        if sufficiency == "insufficient":
            state.recovery.append(RecoveryAction(
                trigger="insufficient_evidence", target="briefing",
                action=t(state.language, "recovery.insufficient.action"),
                outcome=t(state.language, "recovery.insufficient.outcome"),
            ))
            return "insufficient_evidence"
        return "partial" if sufficiency == "partial" else "completed"
