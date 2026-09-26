"""Bilingual behaviour: detection, message catalogue and end-to-end briefings."""

import json
import string

import pytest

from idx_insight.agent.i18n import MESSAGES
from idx_insight.agent.language import detect_language
from idx_insight.analytics.events import _TYPE_BASE

DISCOVERY_ID = "Apa saja disclosure yang perlu saya pantau minggu depan untuk sektor perbankan?"
DISCOVERY_EN = "Which banking disclosures should I watch next week?"

# Words that only appear in Indonesian output text.
INDONESIAN_MARKERS = ["relevan karena", "saham", "emiten", "peristiwa", "tidak ", "dari total",
                      "triliun", "miliar", "Perbandingan", "Pertumbuhan", "bukan rekomendasi"]


@pytest.mark.parametrize("query, expected", [
    (DISCOVERY_ID, "id"),
    (DISCOVERY_EN, "en"),
    ("Bandingkan BBCA dan BBRI dari sisi profitability", "id"),
    ("Compare BBCA and BBRI on profitability", "en"),
    ("Is BBCA worth buying?", "en"),
    ("BBCA", "id"),  # undecided → Indonesian default
])
def test_language_detection(query, expected):
    assert detect_language(query) == expected


def test_catalogue_has_both_languages_with_matching_placeholders():
    fields = string.Formatter()
    for key, versions in MESSAGES.items():
        assert set(versions) == {"id", "en"}, key
        names = [{f for _, f, _, _ in fields.parse(v) if f} for v in versions.values()]
        assert names[0] == names[1], key


def test_every_relevance_reason_code_has_a_message():
    codes = set(_TYPE_BASE) | {"ownership_large", "ownership_medium", "large_value", "insider",
                               "forward", "cluster", "watchlist"}
    assert all(f"reason.{code}" in MESSAGES for code in codes)


@pytest.mark.parametrize("query", [
    DISCOVERY_EN,
    "Compare BBCA, BBRI, BMRI and BBNI on profitability and efficiency",
    "How is BBTN performing?",
])
def test_english_briefing_contains_no_indonesian(run, query):
    state = run(query)
    assert state.language == "en"
    text = json.dumps({"briefing": state.briefing.model_dump(),
                       "trace": [t.detail for t in state.trace],
                       "decisions": [d.reason for d in state.second_hop],
                       "recovery": [(r.action, r.outcome) for r in state.recovery]},
                      ensure_ascii=False)
    leaks = [w for w in INDONESIAN_MARKERS if w in text]
    assert not leaks, leaks


def test_indonesian_briefing_uses_indonesian_number_format(run):
    state = run(DISCOVERY_ID)
    titles = [e.title for e in state.relevant_events]
    assert any("1,05% saham" in t and "Rp862,4 miliar" in t for t in titles)


def test_english_briefing_uses_english_number_format(run):
    state = run(DISCOVERY_EN)
    titles = [e.title for e in state.relevant_events]
    assert any("1.05% of shares" in t and "IDR 862.4 bn" in t for t in titles)


def test_explicit_language_overrides_detection(run):
    state = run(DISCOVERY_ID, language="en")
    assert state.language == "en"
    assert state.briefing.sections[0].heading == "Events worth attention"


def test_english_advice_request_gets_boundary_note(run):
    state = run("Is BBCA worth buying?")
    assert state.intent.advice_requested
    assert "does not give recommendations" in state.briefing.boundary_note


def test_english_clarification(run):
    state = run("Disclosures for bank syariah next week")
    assert state.briefing.clarification_question.startswith("Which company do you mean?")
    assert "BRIS or BTPS" in state.briefing.clarification_question


def test_narrative_request_states_the_language():
    from idx_insight.agent.prompts import synthesis_user_prompt

    assert synthesis_user_prompt("q", "en", [], []).startswith("Write the briefing in English.")
    assert "Indonesian" in synthesis_user_prompt("q", "id", [], [])
