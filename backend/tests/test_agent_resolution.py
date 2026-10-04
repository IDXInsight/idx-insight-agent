from datetime import date

from conftest import AS_OF, gateway

from idx_insight.agent.entities import EntityResolver
from idx_insight.agent.intent import requested_metrics, resolve_intent, rule_intent
from idx_insight.agent.prompts import IntentProposal
from idx_insight.agent.state import AgentState
from idx_insight.agent.timeframe import resolve_timeframe
from idx_insight.llm.errors import LLMRateLimitError
from idx_insight.llm.mock import MockLLMProvider
from idx_insight.sectors import MockSectorsAdapter, SectorsService
from idx_insight.sectors.credits import SectorsCreditCapError


def resolve(query, **kwargs):
    service = SectorsService(MockSectorsAdapter())
    state = AgentState(query=query, as_of=AS_OF, **kwargs)
    return EntityResolver(service).resolve(state), service


# --- entities ----------------------------------------------------------------


def test_tickers_and_aliases_are_resolved():
    entities, _ = resolve("Bandingkan BBCA, bank mandiri dan bni")
    assert set(entities.symbols) == {"BBCA", "BMRI", "BBNI"}
    methods = {c.symbol: c.method for c in entities.companies}
    assert methods["BBCA"] == "ticker" and methods["BMRI"] == "alias"


def test_finance_jargon_is_not_treated_as_ticker():
    entities, service = resolve("Bandingkan CASA dan BOPO BBRI")
    assert entities.symbols == ["BBRI"]
    assert entities.unknown == []
    assert service.calls == []


def test_ambiguous_alias_is_not_guessed():
    entities, _ = resolve("disclosure bank syariah minggu depan")
    assert entities.symbols == []
    assert entities.ambiguous[0].candidates == ["BRIS", "BTPS"]


def test_specific_alias_beats_ambiguous_one():
    entities, _ = resolve("kinerja bank syariah indonesia")
    assert entities.symbols == ["BRIS"] and entities.ambiguous == []


def test_unknown_ticker_is_verified_against_sectors():
    entities, service = resolve("Bandingkan BBCA dan ABCD")
    assert entities.unknown == ["ABCD"]
    assert service.calls[0].tool == "fetch-company-report"
    assert service.calls[0].status == "not_found"


def test_sector_and_watchlist():
    entities, _ = resolve("disclosure sektor perbankan", watchlist=["bbri.jk"])
    assert entities.sub_sector == "banks"
    assert entities.symbols == ["BBRI"]


# --- timeframe ---------------------------------------------------------------


def test_next_week_is_monday_to_sunday_with_filings_lookback():
    tf = resolve_timeframe("minggu depan", AS_OF, "discovery")
    assert (tf.start, tf.end) == (date(2026, 9, 28), date(2026, 10, 4))
    assert tf.direction == "forward" and not tf.assumed
    assert (tf.filings_start, tf.filings_end) == (date(2026, 9, 12), AS_OF)


def test_last_n_days_and_iso_range():
    tf = resolve_timeframe("filing 10 hari terakhir", AS_OF, "discovery")
    assert tf.start == date(2026, 9, 16) and tf.direction == "backward"
    tf = resolve_timeframe("2026-10-01 sampai 2026-10-10", AS_OF, "discovery")
    assert tf.direction == "forward" and tf.end == date(2026, 10, 10)


def test_vague_timeframe_uses_recorded_default():
    tf = resolve_timeframe("disclosure bank baru-baru ini", AS_OF, "discovery")
    assert tf.assumed and "baru-baru ini" in tf.note


def test_financial_period_extraction():
    assert resolve_timeframe("ROE Q1 2026", AS_OF, "peer_comparison").financial_period == "2026-03-31"
    assert resolve_timeframe("ROE tahun 2024", AS_OF, "peer_comparison").financial_period == "2024"


# --- intent ------------------------------------------------------------------


def test_discovery_intent():
    entities, _ = resolve("Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?")
    assert rule_intent("Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?",
                       entities).name == "discovery"


def test_peer_intent_and_metric_bundles_in_user_order():
    q = "Bandingkan BBCA, BBRI, BMRI, dan BBNI dari sisi profitability dan efficiency."
    entities, _ = resolve(q)
    intent = rule_intent(q, entities)
    assert intent.name == "peer_comparison" and intent.confidence == "high"
    assert intent.metric_bundles == ["profitability", "efficiency"]
    assert requested_metrics(intent)[-1] == "cost_to_income_ratio"


def test_peer_intent_detects_cost_to_income_with_spaces():
    q = "Bandingkan BBCA dan BBRI dari sisi cost to income."
    entities, _ = resolve(q)
    intent = rule_intent(q, entities)
    assert intent.name == "peer_comparison"
    assert requested_metrics(intent) == ["cost_to_income_ratio"]


def test_single_company_with_advice_request():
    q = "Apakah BBCA layak dibeli?"
    entities, _ = resolve(q)
    intent = rule_intent(q, entities)
    assert intent.name == "company_context" and intent.advice_requested


def test_unsupported_metric_is_flagged():
    q = "Bandingkan BOPO BBCA dan BBRI"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).unsupported_metrics == ["BOPO"]


def test_list_only_request_skips_second_hop():
    q = "disclosure perbankan minggu depan, daftar saja"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).skip_second_hop


def test_llm_refines_low_confidence_intent():
    q = "BBCA dan BBRI"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).confidence == "low"
    provider = MockLLMProvider(
        {"intent": MockLLMProvider.structured(IntentProposal(intent="discovery", rationale="x"))})
    intent = resolve_intent(q, entities, gateway(provider))
    assert intent.name == "discovery" and intent.source == "llm"


def test_llm_cannot_skip_required_research_without_explicit_plain_list_request():
    q = "BBCA dan BBRI"
    entities, _ = resolve(q)
    provider = MockLLMProvider({"intent": MockLLMProvider.structured(
        IntentProposal(intent="discovery", skip_second_hop=True, rationale="skip it"))})
    intent = resolve_intent(q, entities, gateway(provider))
    assert intent.name == "discovery" and not intent.skip_second_hop


def test_llm_not_consulted_when_rules_are_confident():
    q = "Bandingkan BBCA dan BBRI"
    entities, _ = resolve(q)
    provider = MockLLMProvider(
        {"intent": MockLLMProvider.structured(IntentProposal(intent="discovery", rationale="x"))})
    assert resolve_intent(q, entities, gateway(provider)).name == "peer_comparison"
    assert provider.requests == []


def test_rules_only_mode_keeps_rule_intent():
    q = "BBCA dan BBRI"
    entities, _ = resolve(q)
    assert resolve_intent(q, entities, gateway(None)).source == "rules"


def test_malformed_intent_reply_falls_back_to_rules():
    q = "BBCA dan BBRI"
    entities, _ = resolve(q)
    provider = MockLLMProvider({"intent": MockLLMProvider.structured({"intent": "buy_now"})})
    llm = gateway(provider)
    intent = resolve_intent(q, entities, llm)
    assert intent.source == "rules"
    assert llm.state.llm_calls[0].status == "invalid_structured_output"


def test_provider_error_falls_back_to_rules():
    q = "BBCA dan BBRI"
    entities, _ = resolve(q)
    llm = gateway(MockLLMProvider({"intent": LLMRateLimitError("groq HTTP 429")}))
    assert resolve_intent(q, entities, llm).source == "rules"
    assert llm.state.llm_calls[0].status == "rate_limit"


class _CreditCappedAdapter(MockSectorsAdapter):
    """Every Sectors call is refused by the credit cap before it is sent."""

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if name.startswith("get_") and callable(attr):
            def refuse(*args, **kwargs):
                raise SectorsCreditCapError("daily credit cap reached")
            return refuse
        return attr


def test_credit_cap_is_reported_as_such_not_as_an_unknown_ticker(run):
    state = run("Bagaimana kinerja ADRO?", adapter=_CreditCappedAdapter())
    assert state.status != "needs_clarification"
    assert not [g for g in state.data_gaps if g.kind == "unverified_company"]
    cap = [g for g in state.data_gaps if g.kind == "budget_exhausted"]
    assert len(cap) == 1 and "credit" in cap[0].detail


def test_peer_comparison_survives_when_every_sectors_call_is_refused(run):
    state = run("Bandingkan BBCA dan BBRI dari sisi profitabilitas", adapter=_CreditCappedAdapter())
    assert state.status == "insufficient_evidence"
    assert [g for g in state.data_gaps if g.kind == "budget_exhausted"]
