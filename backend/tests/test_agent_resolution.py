from datetime import date

import pytest
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


@pytest.mark.parametrize("query", ["Kamu bisa membandingkan ROE?", "Can you compare ROE?",
                                  "Kamu bisa pantau disclosure di watchlist saya?"])
def test_capability_with_watchlist_stays_about_on_rate_limit(query, run):
    state = run(query, watchlist=["BBCA", "BBRI", "BMRI", "BBNI"],
                llm=MockLLMProvider({"intent": LLMRateLimitError("quota reached")}))
    assert state.intent.name == "about"
    assert state.tool_calls == []
    assert not state.claims


@pytest.mark.parametrize("query", [
    "Bandingkan pertumbuhan laba dan pendapatan BBCA dan BBRI pada Q2 2026",
    "Compare earnings and revenue growth of BBCA and BBRI in Q2 2026",
])
def test_explicit_growth_metrics_do_not_add_unrequested_bundles(query, run):
    state = run(query)
    assert requested_metrics(state.intent) == ["earnings_growth_yoy", "revenue_growth_yoy"]
    assert set(state.analytics["peer_comparison"]) == {"earnings_growth_yoy", "revenue_growth_yoy"}


def test_named_company_polite_research_request_is_preserved(run):
    state = run("Can you compare BBCA and BBRI on ROE?")
    assert state.intent.name == "peer_comparison"
    assert state.analytics["peer_comparison"]["roe"]["sufficient"]


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


@pytest.mark.parametrize("query, name", [
    ("Lu siapa?", "about"),
    ("What can you do?", "about"),
    ("Ada ga sih bank yang jelek?", "advice"),
    ("Menurutlu bank apa yang perlu gue analisis?", "advice"),
    ("Should I buy bank stocks now?", "advice"),
])
def test_questions_outside_research_are_recognised_by_rules(query, name):
    entities, _ = resolve(query)
    assert rule_intent(query, entities).name == name


def test_a_named_company_keeps_advice_questions_on_the_research_path():
    q = "Apakah BBCA layak dibeli?"
    entities, _ = resolve(q)
    intent = rule_intent(q, entities)
    assert intent.name == "company_context" and intent.advice_requested


def test_questions_outside_research_spend_no_sectors_calls(run):
    for query in ("Lu siapa?", "Ada ga sih bank yang jelek?"):
        state = run(query)
        assert state.status == "needs_clarification" and state.tool_calls == []
        assert state.briefing.clarification_question


def test_ordinary_english_words_are_not_read_as_a_judgement():
    q = "Tolong terjemahkan good morning ke bahasa Jepang"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).name != "advice"


@pytest.mark.parametrize("query", ["kamu bisa analisis saham?", "Can you analyse Indonesian bank stocks?"])
def test_capability_questions_are_about_the_agent(query):
    entities, _ = resolve(query)
    assert rule_intent(query, entities).name == "about"


def test_a_capability_question_with_companies_stays_research():
    q = "Kamu bisa bandingkan ROE BBCA dan BBRI?"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).name == "peer_comparison"


def _brain(**proposal):
    return gateway(MockLLMProvider({"intent": MockLLMProvider.structured(
        IntentProposal(rationale="x", **proposal))}))


def test_the_llm_decides_the_direction_of_unscoped_messages():
    q = "kamu bisa analisis saham?"
    entities, _ = resolve(q)
    intent = resolve_intent(q, entities, _brain(intent="about"))
    assert intent.name == "about" and intent.source == "llm"


def test_the_llm_overrules_a_rule_hint_that_misreads_the_message():
    q = "Ada ga sih bank yang jelek?"
    entities, _ = resolve(q)
    assert rule_intent(q, entities).name == "advice"
    assert resolve_intent(q, entities, _brain(intent="clarify")).name == "clarify"


def test_rule_hints_stand_when_the_llm_is_unavailable():
    q = "Ada ga sih bank yang jelek?"
    entities, _ = resolve(q)
    assert resolve_intent(q, entities, gateway(None)).name == "advice"


def test_suggested_research_question_is_kept_when_clean():
    q = "Ada ga sih bank yang jelek?"
    entities, _ = resolve(q)
    intent = resolve_intent(q, entities, _brain(
        intent="advice", suggested_question="Bandingkan NPL dan ROE bank di watchlist saya"))
    assert intent.suggestion == "Bandingkan NPL dan ROE bank di watchlist saya"


@pytest.mark.parametrize("suggestion", [
    "Beli BBCA sekarang sebelum naik",       # advice wording
    "x" * 200,                               # too long
    "Ada ga sih bank yang jelek?",           # just repeats the question
    "Anda ingin analisis perusahaan mana?",  # a question back to the user
    "Bank apa yang sedang bermasalah?",      # not a research request the agent can run
])
def test_unsafe_or_useless_suggestions_are_dropped(suggestion):
    q = "Ada ga sih bank yang jelek?"
    entities, _ = resolve(q)
    brain = _brain(intent="advice", suggested_question=suggestion)
    assert resolve_intent(q, entities, brain).suggestion is None


def test_named_companies_keep_judgement_questions_on_the_research_path():
    q = "BBCA dan BBRI mana yang jelek?"
    entities, _ = resolve(q)
    intent = resolve_intent(q, entities, _brain(intent="advice"))
    assert intent.name in {"peer_comparison", "company_context", "discovery"}


def test_clarification_carries_the_suggestion_to_the_briefing(run):
    llm = MockLLMProvider({"intent": MockLLMProvider.structured(IntentProposal(
        intent="advice", rationale="x", suggested_question="Bandingkan ROE bank di watchlist saya"))})
    state = run("Menurutmu bank apa yang menarik?", llm=llm)
    assert state.status == "needs_clarification" and state.tool_calls == []
    assert state.briefing.suggestions == ["Bandingkan ROE bank di watchlist saya"]


@pytest.mark.parametrize("query, expected", [
    ("kamu sejago apa", "id"),
    ("seberapa bagus BCA", "id"),
    ("bank mana yg lagi cuan?", "id"),
    ("Who are you?", "en"),
    ("Is any bank in trouble right now?", "en"),
])
def test_everyday_language_is_detected(query, expected):
    from idx_insight.agent.language import detect_language
    assert detect_language(query) == expected


@pytest.mark.parametrize("query", ["BCAとBRIを比較する", "あなたは誰ですか", "مرحبا كيف حالك"])
def test_unsupported_scripts_get_a_bilingual_reply_without_any_call(run, query):
    state = run(query)
    assert state.status == "needs_clarification" and state.tool_calls == [] and state.llm_calls == []
    assert "Indonesia" in state.briefing.clarification_question
    assert "English" in state.briefing.clarification_question


def test_indonesian_with_accented_or_latin_names_is_supported():
    from idx_insight.agent.language import unsupported_script
    assert not unsupported_script("Bandingkan BBCA dan BBRI — kinerja café & résumé")
