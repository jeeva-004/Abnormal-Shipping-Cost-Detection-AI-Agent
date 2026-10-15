"""Evaluation harness. Run from project root: python eval/run_eval.py [--no-cache]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd 

from src import config, flagging, gate, metrics, notes, pipeline 
from src.retrieval import NoteIndex 

EVAL_DIR = Path(__file__).resolve().parent
use_cache = "--no-cache" not in sys.argv
results_log = []


def check(name, ok, detail=""):
    results_log.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


#shared setup
enriched = notes.enrich_notes(notes.load_notes_csv(), use_cache=use_cache)
by_id = {n.note_id: n for n in enriched}
index = NoteIndex(enriched, lambda t: notes.embed_texts(t, use_cache=use_cache))
weekly = flagging.flag_candidates(metrics.build_metrics())
results = pipeline.build_results(weekly[weekly["is_candidate"]], by_id, index)

#notes vs hand labels
print("\n[1] Note understanding vs hand labels")
gold_notes = pd.read_csv(config.NOTES_GOLD_CSV).set_index("note_id")
llm_hits = sum(n.llm_effect == gold_notes.loc[n.note_id, "gold_effect"] for n in enriched)
print(f"  (info) LLM alone agrees with hand labels on {llm_hits}/10 notes; "
      f"the keyword layer is the safety net")
false_just = [n.note_id for n in enriched
              if n.effect == "raises_cost" and gold_notes.loc[n.note_id, "gold_effect"] != "raises_cost"]
check("no non-cost note is ever labeled raises_cost", not false_just, str(false_just))
missed = [n.note_id for n in enriched
          if gold_notes.loc[n.note_id, "gold_effect"] == "raises_cost" and n.effect != "raises_cost"]
check("all cost-raising notes recovered", not missed, str(missed))
bad_win = []
for n in enriched:
    g = gold_notes.loc[n.note_id]
    if g["gold_effect"] == "raises_cost":
        end = "open" if n.open_ended else str(n.eff_end)
        if not (str(n.eff_start) == g["gold_start"] and end == g["gold_end"]):
            bad_win.append(n.note_id)
check("effective windows parsed correctly", not bad_win, str(bad_win))

#end-to-end rows vs hand labels
print("\n[2] Results vs hand-labeled rows (regression check: labels are my reading of the data)")
gold = pd.read_csv(EVAL_DIR / "gold_rows.csv", keep_default_na=False)
for g in gold.itertuples():
    hit = results[(results["route"] == g.route) & (results["week_of"] == g.week_of)]
    if g.expected_flagged == "absent":
        check(f"{g.route} {g.week_of} not flagged (market-wide rise)", hit.empty)
    else:
        ok = (not hit.empty and hit.iloc[0]["flagged"] == g.expected_flagged
              and hit.iloc[0]["matched_note_id"] == g.expected_note_id)
        got = "missing" if hit.empty else f"{hit.iloc[0]['flagged']} {hit.iloc[0]['matched_note_id']}".strip()
        check(f"{g.route} {g.week_of} -> {g.expected_flagged} {g.expected_note_id}".strip(), ok, got)
expected_set = {(g.route, g.week_of) for g in gold.itertuples() if g.expected_flagged != "absent"}
actual_set = set(zip(results["route"], results["week_of"]))
check("flagged set is exactly the expected 13 rows", expected_set == actual_set,
      f"extra={sorted(actual_set - expected_set)} missing={sorted(expected_set - actual_set)}")

#the supplied sample rows (independent truth)
print("\n[3] The 3 rows in sample_output_format_v2.csv (numbers, flag, note id)")
lines = config.SAMPLE_OUTPUT_CSV.read_text(encoding="utf-8").splitlines()
cols = lines[0].split(",")
for line in lines[1:]:
    s = dict(zip(cols, line.split(",", len(cols) - 1)))   # reason is last, may hold commas
    hit = results[(results["route"] == s["route"]) & (results["week_of"] == s["week_of"])]
    ok = (not hit.empty
          and abs(float(s["cost_per_tonne_km"]) - hit.iloc[0]["cost_per_tonne_km"]) < 1e-9
          and s["vs_own_history"] == hit.iloc[0]["vs_own_history"]
          and s["vs_similar_routes"] == hit.iloc[0]["vs_similar_routes"]
          and s["flagged"] == hit.iloc[0]["flagged"]
          and s["matched_note_id"] == hit.iloc[0]["matched_note_id"])
    check(f"{s['route']} {s['week_of']} matches the sample row", ok)

#trap scenarios through the real gate
print("\n[4] Trap scenarios (hypothetical rows through the real retrieval + gate)")
for r in pd.read_csv(EVAL_DIR / "scenarios.csv", keep_default_na=False).itertuples():
    row = {"route": r.route, "week_of": pd.Timestamp(r.week_of),
           "vs_own_pct": r.vs_own_pct, "vs_peer_pct": r.vs_peer_pct}
    e = gate.explain(row, by_id, index)
    ok = e.verdict == r.expected_verdict and e.note_id == r.expected_note_id
    check(r.name, ok, f"got {e.verdict} {e.note_id}".strip() + ("" if ok else f" (expected {r.expected_verdict} {r.expected_note_id})"))

passed = sum(results_log)
print(f"\nEVAL: {passed}/{len(results_log)} checks passed")
sys.exit(0 if passed == len(results_log) else 1)