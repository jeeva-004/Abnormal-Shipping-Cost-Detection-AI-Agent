"""Unit tests for Stage 4 (no Ollama needed). Run: python -m pytest tests -v"""
import csv
from datetime import date

import numpy as np
import pandas as pd
import pytest

from src import config, gate, notes, pipeline, reasons

ROW = {"route": "A-B", "week_of": pd.Timestamp("2025-03-03"), "vs_own_pct": 20.0,
       "vs_peer_pct": 10.0, "cost_per_tonne_km": 3.0}


def mk(note_id="N1", applies_to="A-B", effect="raises_cost", start=date(2025, 3, 3),
       end=date(2025, 3, 9), text="Floods raised trip costs.", open_ended=False,
       low=None, high=None):
    return notes.Note(note_id, start, applies_to, text, effect, effect, effect,
                      start, end, open_ended, low, high)


def exp(verdict="unexplained", note_id="", rejections=None, closest="", gap=None):
    return gate.Explanation(verdict, note_id, rejections or {}, closest, gap)


def test_number_formats():
    assert reasons.fmt_vs_own(35.52) == "+35.5% vs this route's past average"
    assert reasons.fmt_vs_peers(-3.04) == "-3.0% vs similar-length routes this week"
    assert "n/a" in reasons.fmt_vs_own(np.nan) and "n/a" in reasons.fmt_vs_peers(np.nan)


def test_justified_reason_cites_id_date_text_and_window():
    r = reasons.justified_reason(mk())
    for piece in ("N1", "2025-03-03", "Floods raised trip costs.",
                  "effective 2025-03-03 to 2025-03-09", "clear explanation"):
        assert piece in r


def test_open_ended_window_text():
    r = reasons.justified_reason(mk(open_ended=True, end=date(2025, 4, 27)))
    assert "effective from 2025-03-03 for up to 8 weeks" in r


def test_unexplained_generic_when_no_nearby_note():
    by_id = {"N1": mk()}
    assert reasons.unexplained_reason(exp(closest="N1", gap=30), by_id, ROW) == reasons.GENERIC_UNEXPLAINED
    assert reasons.unexplained_reason(exp(), by_id, ROW) == reasons.GENERIC_UNEXPLAINED


def test_unexplained_quotes_nearby_no_effect_note():
    by_id = {"N9": mk("N9", effect="no_cost_effect", text="Everything returned to normal.")}
    r = reasons.unexplained_reason(exp(closest="N9", gap=1), by_id, ROW)
    assert 'N9' in r and '"Everything returned to normal."' in r
    assert "does not establish a reason" in r and "flagged for review" in r


def test_unexplained_nearby_cost_note_outside_window():
    by_id = {"N1": mk()}                                   # window Mar 3-9, row week is Mar 10
    row = {**ROW, "week_of": pd.Timestamp("2025-03-10")}
    r = reasons.unexplained_reason(exp(closest="N1", gap=1), by_id, row)
    assert "does not cover the week of 2025-03-10" in r


def test_market_wide_message():
    by_id = {"N3": mk("N3", applies_to="All Routes")}
    r = reasons.unexplained_reason(
        exp(closest="N3", gap=0, rejections={"N3": "market_wide_cannot_explain_peer_gap"}), by_id, ROW)
    assert "market-wide" in r and "cannot explain the gap" in r


def test_magnitude_message():
    by_id = {"N3": mk("N3", low=5.0, high=7.0)}
    r = reasons.unexplained_reason(
        exp(closest="N3", gap=0, rejections={"N3": "magnitude_exceeded"}), by_id, ROW)
    assert "5-7%" in r and "+20.0%" in r


class FakeIndex:
    """Always 'retrieves' N1, even for the wrong week, to prove the gate protects us."""
    def search(self, route, week_start, week_end, k=5):
        return [("N1", 1.0)]


def candidates_df():
    return pd.DataFrame([
        {**ROW, "week_of": pd.Timestamp("2025-06-02")},    # outside N1's window
        {**ROW, "week_of": pd.Timestamp("2025-03-03")},    # inside N1's window
    ])


def test_build_results_end_to_end_with_bad_retrieval():
    by_id = {"N1": mk()}
    res = pipeline.build_results(candidates_df(), by_id, FakeIndex())
    assert list(res.columns) == config.OUTPUT_COLUMNS
    assert list(res["week_of"]) == ["2025-03-03", "2025-06-02"]          # chronological
    assert list(res["flagged"]) == ["No (justified)", "Yes"]
    assert list(res["matched_note_id"]) == ["N1", ""]
    pipeline.validate_output(res, valid_note_ids={"N1"})


def good_df():
    return pd.DataFrame([{
        "route": "A-B", "week_of": "2025-03-03", "cost_per_tonne_km": 3.0,
        "vs_own_history": "+1.0% vs this route's past average",
        "vs_similar_routes": "+1.0% vs similar-length routes this week",
        "flagged": "Yes", "matched_note_id": "", "reason": "x"}])


def test_validate_output_rejects_bad_frames():
    pipeline.validate_output(good_df())                                   # baseline is valid
    cases = [
        lambda d: d.rename(columns={"reason": "why"}),
        lambda d: d.assign(week_of="2025-03-04"),                         # not a Monday
        lambda d: d.assign(flagged="Maybe"),
        lambda d: d.assign(matched_note_id="N1"),                         # Yes row with an id
        lambda d: d.assign(flagged="No (justified)"),                     # justified, no id
        lambda d: d.assign(flagged="No (justified)", matched_note_id="N9", reason="N9 ok"),  # unknown id
        lambda d: d.assign(reason=np.nan),
    ]
    for make_bad in cases:
        with pytest.raises(ValueError):
            pipeline.validate_output(make_bad(good_df()), valid_note_ids={"N1"})


def test_write_and_validate_file_roundtrip(tmp_path):
    by_id = {"N1": mk(text="Floods, detours, and higher costs.")}        # commas must be quoted
    res = pipeline.build_results(candidates_df(), by_id, FakeIndex())
    path = tmp_path / "r.csv"
    pipeline.write_results(res, path)
    assert pipeline.validate_file(path) == 2
    with open(path, newline="", encoding="utf-8") as f:
        assert all(len(row) == 8 for row in csv.reader(f))