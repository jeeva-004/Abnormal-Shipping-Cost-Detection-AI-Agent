"""Stage 3 real-data check. Run from project root: python scripts/stage3_check.py [--no-cache]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd  

from src import config, flagging, gate, metrics, notes, usage  
from src.retrieval import NoteIndex

use_cache = "--no-cache" not in sys.argv
print(f"model={config.LLM_MODEL}  cache={'on' if use_cache else 'off'}\n")

df = notes.load_notes_csv()
enriched = notes.enrich_notes(df, use_cache=use_cache)
gold = pd.read_csv(config.NOTES_GOLD_CSV).set_index("note_id")

print("=== Notes: LLM vs keyword rules vs my hand labels ===")
llm_ok = final_ok = win_ok = n_win = 0
for n in enriched:
    g = gold.loc[n.note_id]
    llm_ok += n.llm_effect == g["gold_effect"]
    final_ok += n.effect == g["gold_effect"]
    win = ""
    if g["gold_effect"] == "raises_cost":
        n_win += 1
        parsed_end = "open" if n.open_ended else str(n.eff_end)
        match = str(n.eff_start) == g["gold_start"] and parsed_end == g["gold_end"]
        win_ok += match
        win = f"window {n.eff_start}..{parsed_end} {'OK' if match else 'WRONG'}"
    print(f"{n.note_id}  llm={n.llm_effect:<15} rules={n.rule_effect:<15} final={n.effect:<15} "
          f"gold={g['gold_effect']:<15} {win}")
print(f"\nLLM agrees with gold:   {llm_ok}/10")
print(f"Final effect matches:   {final_ok}/10")
print(f"Windows parsed right:   {win_ok}/{n_win}")

print("\n=== Candidates through retrieval + gate ===")
weekly = flagging.flag_candidates(metrics.build_metrics())
cands = weekly[weekly["is_candidate"]]
index = NoteIndex(enriched, lambda t: notes.embed_texts(t, use_cache=use_cache))
by_id = {n.note_id: n for n in enriched}
rows = []
for _, r in cands.iterrows():
    e = gate.explain(r, by_id, index)
    rows.append({"route": r["route"], "week_of": r["week_of"].date(), "verdict": e.verdict,
                 "note_id": e.note_id, "rejections": ";".join(f"{k}:{v}" for k, v in e.rejections.items()),
                 "closest": f"{e.closest_id} ({e.closest_gap_days}d)"})
out = pd.DataFrame(rows)
config.OUTPUT_DIR.mkdir(exist_ok=True)
out.to_csv(config.OUTPUT_DIR / "stage3_explanations.csv", index=False)
print(out.to_string(index=False))
print("\njustified:", int((out.verdict == "justified").sum()), " unexplained:", int((out.verdict == "unexplained").sum()))
print("\nusage this run:", usage.TRACKER.summary())