"""Stage 4b: end-to-end pipeline and output validation."""
import csv
from pathlib import Path

import pandas as pd

from src import config, flagging, gate, metrics, notes, reasons
from src.retrieval import NoteIndex


def build_results(candidates: pd.DataFrame, by_id: dict, index) -> pd.DataFrame:
    """One output row per candidate, in the exact output schema."""
    rows = []
    for _, r in candidates.sort_values(["week_of", "route"]).iterrows():
        exp = gate.explain(r, by_id, index)
        rows.append({
            "route": r["route"],
            "week_of": r["week_of"].date().isoformat(),
            "cost_per_tonne_km": round(float(r["cost_per_tonne_km"]), 2),
            "vs_own_history": reasons.fmt_vs_own(r["vs_own_pct"]),
            "vs_similar_routes": reasons.fmt_vs_peers(r["vs_peer_pct"]),
            "flagged": reasons.FLAG_BY_VERDICT[exp.verdict],
            "matched_note_id": exp.note_id,
            "reason": reasons.build_reason(exp, by_id, r),
        })
    return pd.DataFrame(rows, columns=config.OUTPUT_COLUMNS)


def validate_output(df: pd.DataFrame, valid_note_ids=None) -> None:
    """Raise ValueError if the frame breaks the output contract."""
    if list(df.columns) != config.OUTPUT_COLUMNS:
        raise ValueError(f"Columns must be exactly {config.OUTPUT_COLUMNS}")
    if df.isna().any().any():
        raise ValueError("Output contains null values (use empty string instead)")
    if df.duplicated(["route", "week_of"]).any():
        raise ValueError("Duplicate route/week rows")
    if not pd.to_datetime(df["week_of"]).dt.dayofweek.eq(0).all():
        raise ValueError("week_of must be a Monday")
    bad = set(df["flagged"]) - set(reasons.FLAG_BY_VERDICT.values())
    if bad:
        raise ValueError(f"Invalid flagged values: {sorted(bad)}")
    for r in df.itertuples(index=False):
        if not str(r.reason).strip():
            raise ValueError("Empty reason")
        if r.flagged == "No (justified)":
            if not r.matched_note_id:
                raise ValueError("Justified row without matched_note_id")
            if valid_note_ids is not None and r.matched_note_id not in valid_note_ids:
                raise ValueError(f"Unknown note id {r.matched_note_id}")
            if r.matched_note_id not in r.reason:
                raise ValueError("Note id must also appear in the reason text")
        elif r.matched_note_id:
            raise ValueError("Unexplained row must have a blank matched_note_id")


def write_results(df: pd.DataFrame, path) -> None:
    """Deterministic CSV: fixed newline, 2-decimal costs, proper quoting."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", encoding="utf-8", float_format="%.2f")


def validate_file(path) -> int:
    """Check the written file against the sample header and field counts. Returns data rows."""
    expected = config.SAMPLE_OUTPUT_CSV.read_text(encoding="utf-8").splitlines()[0].strip().split(",")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if rows[0] != expected:
        raise ValueError(f"Header {rows[0]} != sample header {expected}")
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != len(expected):
            raise ValueError(f"Line {i} has {len(row)} fields, expected {len(expected)}")
    return len(rows) - 1


def run_pipeline(use_cache: bool = True):
    """CSV inputs -> metrics -> flags -> notes -> retrieval + gate -> validated results."""
    weekly = flagging.flag_candidates(metrics.build_metrics())
    candidates = weekly[weekly["is_candidate"]]
    enriched = notes.enrich_notes(notes.load_notes_csv(), use_cache=use_cache)
    by_id = {n.note_id: n for n in enriched}
    index = NoteIndex(enriched, lambda t: notes.embed_texts(t, use_cache=use_cache))
    results = build_results(candidates, by_id, index)
    validate_output(results, valid_note_ids=set(by_id))
    return results, weekly, enriched