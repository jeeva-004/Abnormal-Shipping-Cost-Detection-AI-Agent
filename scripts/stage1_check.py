"""Stage 1 real-data check. Run from project root: python scripts/stage1_check.py"""
import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd  # noqa: E402

from src import config, metrics  # noqa: E402

w = metrics.build_metrics()
config.OUTPUT_DIR.mkdir(exist_ok=True)
w.to_csv(config.OUTPUT_DIR / "weekly_metrics.csv", index=False)

print(f"route-weeks: {len(w)}  routes: {w['route'].nunique()}")
print("weeks per route:", w.groupby("route").size().unique().tolist())
print("route types:", w.groupby("route_type")["route"].unique().apply(list).to_dict())
print("first week has no history:", w[w["n_prior_weeks"] == 0]["own_hist_avg"].isna().all())


# ---- Independent recomputation in plain Python (no pandas) ----
def monday(d):
    return d - timedelta(days=d.weekday())


cost, tkm, rtype = defaultdict(float), defaultdict(float), {}
with open(config.SHIPMENTS_CSV, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        route = f"{r['origin']}-{r['destination']}"
        key = (route, monday(date.fromisoformat(r["shipment_date"])))
        cost[key] += float(r["freight_cost_inr"])
        tkm[key] += float(r["quantity_tonnes"]) * float(r["distance_km"])
        rtype[route] = r["route_type"]
rate = {k: cost[k] / tkm[k] for k in cost}


def independent(route, wk):
    weeks = sorted(k[1] for k in rate if k[0] == route)
    prior = [rate[(route, x)] for x in weeks if x < wk][-8:]
    own = sum(prior) / len(prior) if prior else None
    peers = [rate[(r, wk)] for r in rtype if r != route and rtype[r] == rtype[route] and (r, wk) in rate]
    peer = sum(peers) / len(peers) if peers else None
    return rate[(route, wk)], own, peer


checks = [("Mumbai-Pune", date(2025, 9, 15)), ("Chennai-Bangalore", date(2025, 3, 3)),
          ("Delhi-Chennai", date(2024, 1, 15))]
ok = True
for route, wk in checks:
    c, own, peer = independent(route, wk)
    row = w[(w["route"] == route) & (w["week_of"] == pd.Timestamp(wk))].iloc[0]
    match = (abs(c - row["cost_per_tonne_km"]) < 1e-9
             and abs(own - row["own_hist_avg"]) < 1e-9
             and abs(peer - row["peer_avg"]) < 1e-9)
    ok &= match
    print(f"{'MATCH' if match else 'MISMATCH'}  {route} {wk}: cost={c:.4f} own={own:.4f} peer={peer:.4f}")
print("\nINDEPENDENT CHECK PASSED" if ok else "\nINDEPENDENT CHECK FAILED")

# ---- The three illustrative rows from the sample file ----
print("\nSample-file route-weeks (the sample values are illustrative; just compare):")
for route, wk in [("Delhi-Jaipur", "2024-11-11"), ("Ahmedabad-Mumbai", "2025-01-20"),
                  ("Mumbai-Pune", "2025-09-15")]:
    r = w[(w["route"] == route) & (w["week_of"] == pd.Timestamp(wk))].iloc[0]
    print(f"{route} {wk}: cost={r['cost_per_tonne_km']:.2f}  vs_own={r['vs_own_pct']:+.1f}%  "
          f"vs_peer={r['vs_peer_pct']:+.1f}%")