"""Stage 2 real-data check. Run from project root: python scripts/stage2_check.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config, flagging, metrics  # noqa: E402

w = flagging.flag_candidates(metrics.build_metrics())
cands = w[w["is_candidate"]]
config.OUTPUT_DIR.mkdir(exist_ok=True)
cands.to_csv(config.OUTPUT_DIR / "candidates.csv", index=False)

show = cands[["route", "week_of", "cost_per_tonne_km", "vs_own_pct", "vs_peer_pct", "trigger"]].copy()
show["week_of"] = show["week_of"].dt.date
print(show.round(2).to_string(index=False))
print(f"\ncandidates: {len(cands)}   by route: {cands.groupby('route').size().to_dict()}")

print("\nSensitivity (number of candidates; rows = rise threshold, cols = peer threshold):")
print("rise\\peer  " + "  ".join(f"{p:>3}" for p in (10, 15, 20, 25)))
for rise in (6, 7, 8, 9):
    counts = [int(flagging.flag_mask(w, rise=rise, peer=p).sum()) for p in (10, 15, 20, 25)]
    print(f"{rise:>9}  " + "  ".join(f"{c:>3}" for c in counts))