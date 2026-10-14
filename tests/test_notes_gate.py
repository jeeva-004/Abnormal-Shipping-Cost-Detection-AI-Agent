"""Unit tests for Stage 3 (no Ollama needed). Run: python -m pytest tests -v"""
from datetime import date

import pandas as pd
import pytest

from src import config, gate, notes
from src.retrieval import NoteIndex


def real_notes(llm="raises_cost"):
    df = notes.load_notes_csv()
    return df, notes.enrich_notes(df, classify=lambda t: llm)


def mk(note_id="X1", applies_to="A-B", effect="raises_cost", start=date(2025, 3, 3),
       end=date(2025, 3, 9), mag_high=None, open_ended=False):
    return notes.Note(note_id, start, applies_to, "text", effect, effect, effect, start, end,
                      open_ended, None, mag_high)


WEEK = (date(2025, 3, 3), date(2025, 3, 9))


def check(note, own=20.0, peer=10.0, route="A-B"):
    return gate.check_note(note, route, WEEK[0], WEEK[1], own, peer)


# ---- parsing ----
def test_keyword_rules_match_hand_labels_on_all_real_notes():
    df, _ = real_notes()
    gold = pd.read_csv(config.NOTES_GOLD_CSV).set_index("note_id")["gold_effect"]
    for r in df.itertuples():
        assert notes.rule_effect(r.note) == gold[r.note_id], r.note_id


def test_window_parsing_on_real_notes():
    df, _ = real_notes()
    by = {r.note_id: r for r in df.itertuples()}
    assert notes.parse_window(by["N001"].note, by["N001"].date) == (date(2025, 2, 24), date(2025, 3, 8))
    assert notes.parse_window(by["N002"].note, by["N002"].date) == (date(2025, 1, 20), date(2025, 1, 26))
    assert notes.parse_window(by["N003"].note, by["N003"].date) == (date(2025, 5, 5), None)


def test_open_ended_window_is_capped():
    s, e, open_ended = notes.effective_window(date(2025, 5, 5), None)
    assert open_ended and e == date(2025, 6, 29)      # 8 weeks later, inclusive


def test_magnitude_parsing():
    df, _ = real_notes()
    by = {r.note_id: r.note for r in df.itertuples()}
    assert notes.parse_magnitude(by["N003"]) == (5.0, 7.0)
    assert notes.parse_magnitude(by["N001"]) == (None, None)


def test_llm_and_rules_must_agree():
    assert notes.combine_effect("raises_cost", "raises_cost") == "raises_cost"
    assert notes.combine_effect("raises_cost", "no_cost_effect") == "unclear"
    assert notes.combine_effect("unclear", "raises_cost") == "unclear"


def test_llm_veto_downgrades_real_cost_notes():
    _, enriched = real_notes(llm="no_cost_effect")     # a wrong LLM must not create justifications
    assert all(n.effect != "raises_cost" for n in enriched)


# ---- gate ----
def test_valid_note_justifies():
    assert check(mk()) is None


def test_wrong_route_rejected():
    assert check(mk(applies_to="C-D")) == "wrong_scope"


def test_note_outside_week_rejected():
    assert check(mk(start=date(2025, 3, 10), end=date(2025, 3, 16))) == "outside_window"


def test_note_saying_no_effect_rejected():
    assert check(mk(effect="no_cost_effect")) == "no_cost_effect"
    assert check(mk(effect="unclear")) == "no_cost_effect"


def test_market_wide_note_cannot_explain_peer_gap():
    n = mk(applies_to=config.ALL_ROUTES)
    assert check(n, peer=25.0) == "market_wide_cannot_explain_peer_gap"
    assert check(n, peer=5.0) is None


def test_quoted_magnitude_must_cover_the_rise():
    assert check(mk(mag_high=7.0), own=30.0) == "magnitude_exceeded"
    assert check(mk(mag_high=7.0), own=9.0) is None    # within 7 + 3 tolerance


# ---- retrieval (fake embeddings, real Chroma) ----
def test_retrieval_filters_scope_and_window():
    ns = [mk("N1", "A-B", start=date(2025, 3, 3), end=date(2025, 3, 9)),
          mk("N2", config.ALL_ROUTES, start=date(2025, 3, 1), end=date(2025, 3, 31)),
          mk("N3", "C-D", start=date(2025, 3, 3), end=date(2025, 3, 9)),
          mk("N4", "A-B", start=date(2025, 6, 1), end=date(2025, 6, 7))]
    fake = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    ids = [i for i, _ in NoteIndex(ns, fake).search("A-B", *WEEK)]
    assert ids == ["N1", "N2"]                         # N3 wrong route, N4 wrong window