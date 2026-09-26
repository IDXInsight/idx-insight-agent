"""InsightAgent — custom orchestration of one research request.

Flow: resolve entities → resolve intent → resolve timeframe → recovery gates →
plan → execute plan steps (discovery → relevance → selective second-hop, or
financial retrieval → deterministic analytics) → evidence validation and
sufficiency → synthesis.

The runtime LLM is optional and reached only through ``AgentLLM``; with no
provider every decision uses the deterministic policies.

Each step is a small method; decisions are written to ``AgentState`` and a
concise, user-safe trace (never chain-of-thought).
"""

from __future__ import annotations

from datetime import date

from idx_insight.agent.analysis import (
    company_trends,
    event_claims,
    peer_comparison,
    second_hop_context,
)
from idx_insight.agent.discovery import DiscoveryAgent
from idx_insight.agent.entities import EntityResolver
from idx_insight.agent.financials import FinancialContext
from idx_insight.agent.intent import requested_metrics, resolve_intent
from idx_insight.agent.llm_gateway import AgentLLM
from idx_insight.agent.planner import build_plan
from idx_insight.agent.relevance import decide_second_hop, rank_events
from idx_insight.agent.state import AgentState, Briefing, RecoveryAction
from idx_insight.agent.synthesis import BOUNDARY_NOTE, synthesize
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
        self.settings = agent.settings
        self.llm = AgentLLM(agent.llm, state, temperature=agent.settings.llm_temperature,
                            max_output_tokens=agent.settings.llm_max_output_tokens)
        self.service = SectorsService(agent.adapter, max_calls=agent.settings.max_tool_calls)
        self.entities = EntityResolver(self.service)
        self.financials = FinancialContext(self.service, state, agent.settings.max_requeries)
        self.discovery = DiscoveryAgent(self.service, state, agent.settings.max_requeries)
        self.events: list[Event] = []
        self.second_hop_symbols: list[str] = []

    # -- resolution --------------------------------------------------------------

    def resolve(self) -> None:
        s = self.state
        s.entities = self.entities.resolve(s)
        s.add_trace("Entities resolved",
                    f"emiten: {', '.join(s.entities.symbols) or '-'}; "
                    f"sektor: {s.entities.sub_sector or '-'}")
        s.intent = resolve_intent(s.query, s.entities, self.llm)
        s.add_trace("Intent resolved", f"{s.intent.name} ({s.intent.source}, {s.intent.confidence})")
        if s.intent.advice_requested:
            s.add_trace("Advice request detected", "dijawab dalam batas riset faktual", "warning")
        s.timeframe = resolve_timeframe(s.query, s.as_of, s.intent.name)
        s.add_trace("Timeframe resolved", s.timeframe.label,
                    "warning" if s.timeframe.assumed else "ok")
        if s.timeframe.assumed:
            s.recovery.append(RecoveryAction(
                trigger="ambiguous_timeframe", target="timeframe",
                action="Memakai jendela default yang terdokumentasi",
                outcome=s.timeframe.label,
            ))

    def clarification(self) -> str | None:
        """Recovery gates that must stop the run before any data is fetched."""
        s = self.state
        assert s.intent is not None
        if s.entities.ambiguous:
            for a in s.entities.ambiguous:
                s.recovery.append(RecoveryAction(
                    trigger="ambiguous_company", target=a.text,
                    action="Meminta klarifikasi, tidak menebak", outcome="needs_clarification",
                ))
            options = "; ".join(f"'{a.text}' → {' atau '.join(a.candidates)}"
                                for a in s.entities.ambiguous)
            return f"Emiten mana yang Anda maksud? {options}"
        for token in s.entities.unknown:
            s.recovery.append(RecoveryAction(
                trigger="unknown_company", target=token,
                action="Diverifikasi ke Sectors (fetch-company-report)",
                outcome="Tidak ditemukan; dikeluarkan dari cakupan",
            ))
            s.add_gap("unknown_company", f"Kode {token} tidak ditemukan di Sectors.", token)
        for token in s.entities.unverified:
            s.recovery.append(RecoveryAction(
                trigger="unknown_company", target=token,
                action="Verifikasi gagal atau melebihi batas verifikasi",
                outcome="Dikeluarkan dari cakupan; tidak diasumsikan valid",
            ))
            s.add_gap("unverified_company", f"Kode {token} tidak dapat diverifikasi.", token)
        for label in s.intent.unsupported_metrics:
            s.recovery.append(RecoveryAction(
                trigger="unsupported_metric", target=label,
                action="Tidak diestimasi; hanya metrik yang terdokumentasi di Sectors dipakai",
                outcome="Dilaporkan sebagai kesenjangan data",
            ))
            s.add_gap("unsupported_metric",
                      f"{label} tidak tersedia sebagai field terdokumentasi di Sectors.")
        if s.intent.unsupported_metrics and not (s.intent.metrics or s.intent.metric_bundles):
            s.assumptions.append("Metrik yang diminta tidak tersedia; ditampilkan bundle "
                                 "profitabilitas sebagai konteks pengganti.")
        if s.intent.name == "clarify":
            return ("Mohon sebutkan emiten (mis. BBCA), sektor (mis. perbankan), atau jenis "
                    "analisis yang Anda inginkan.")
        if s.intent.name == "discovery" and not (s.entities.symbols or s.entities.sub_sector):
            return "Untuk memantau disclosure, sebutkan sektor atau daftar emiten (watchlist)."
        if s.intent.name in ("peer_comparison", "company_context") and not (
            s.entities.symbols or s.entities.sub_sector
        ):
            return "Emiten yang disebut tidak ditemukan. Mohon periksa kode sahamnya."
        return None

    # -- plan steps --------------------------------------------------------------

    def _sector_scope(self) -> list[tuple[str, str | None]] | None:
        s = self.state
        slug = s.entities.sub_sector
        if slug is None:
            return []
        if not self.entities.verify_sub_sector(slug):
            s.add_gap("unknown_sector", f"Sub-sektor '{slug}' tidak dikenali oleh Sectors.")
            return None
        members = self.entities.sector_members(slug)
        if members is None:
            s.add_gap("tool_error", f"Daftar emiten sub-sektor {slug} tidak dapat diambil.")
            return None
        return [(m.symbol, m.company_name) for m in members]

    def step_discover_events(self) -> None:
        s = self.state
        explicit = [(c.symbol, c.company_name) for c in s.entities.companies]
        sector = self._sector_scope() if not explicit else []
        members = explicit or sector or []
        symbols = self.discovery.scope(members)
        if not symbols:
            s.add_trace("Discovery selected", "cakupan kosong", "error")
            return
        use_sector = s.entities.sub_sector if not explicit else None
        self.events = self.discovery.collect(symbols, use_sector)
        s.add_trace("Discovery selected",
                    f"{len(symbols)} emiten; {len(self.events)} peristiwa mentah "
                    f"(filing {s.timeframe.filings_start}–{s.timeframe.filings_end}, "
                    f"agenda {s.timeframe.start}–{s.timeframe.end})")

    def step_rank_relevance(self) -> None:
        s = self.state
        relevant = rank_events(s, self.events)
        event_claims(s)
        s.add_trace("Relevant events detected",
                    f"{len(relevant)} relevan dari {len(s.discovered_events)} unik; "
                    f"{len(s.duplicate_events)} duplikat dihapus")

    def step_second_hop_context(self) -> None:
        s = self.state
        self.second_hop_symbols = decide_second_hop(
            s, self.service.budget_remaining, self.settings.max_second_hop, self.llm)
        if not self.second_hop_symbols:
            s.add_trace("Second-hop analysis", "tidak ada peristiwa yang membutuhkan riset lanjutan",
                        "skipped")
            return
        source = next((d.source for d in s.second_hop), "rules")
        s.add_trace(f"Second-hop analysis selected ({source})", ", ".join(self.second_hop_symbols))
        second_hop_context(s, self.financials, self.second_hop_symbols)
        s.add_trace("Financial context retrieved", f"{len(s.evidence)} bukti tercatat")

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
        for sym in symbols:
            self.financials.report(sym)
        s.add_trace("Sectors data retrieved", f"company report {len(symbols)} emiten")

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
            f"{len(report.accepted)} klaim diterima, {len(report.rejected)} ditolak; "
            f"kecukupan bukti: {report.assessment.sufficiency}",
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
            sub_sector: str | None = None) -> AgentState:
        state = AgentState(query=query, as_of=as_of or date.today(),
                           watchlist=[w.upper() for w in (watchlist or [])],
                           requested_sub_sector=sub_sector)
        run = _Run(self, state)
        run.resolve()

        question = run.clarification()
        if question:
            state.status = "needs_clarification"
            state.briefing = Briefing(title="Klarifikasi diperlukan", summary=question,
                                      boundary_note=BOUNDARY_NOTE, clarification_question=question)
            state.add_trace("Clarification requested", question, "warning")
            state.tool_calls = list(run.service.calls)
            return state

        state.plan = build_plan(state, run.llm)
        detail = " → ".join(state.plan.names)
        if state.plan.rejected_llm_plan:
            detail += f" (usulan LLM ditolak: {state.plan.rejected_llm_plan})"
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
                action="Tidak menyusun temuan tanpa bukti",
                outcome="Kesenjangan data ditampilkan ke pengguna",
            ))
            return "insufficient_evidence"
        return "partial" if sufficiency == "partial" else "completed"
