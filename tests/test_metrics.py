"""Unit tests for Stage 1. Run: python -m pytest tests -v"""
import math

import pandas as pd
import pytest

from src import metrics

BASE = pd.Timestamp("2024-01-01")  # a Monday


def make_ships(rates_by_route, route_types=None):
    """One shipment per route per week with qty=1, dist=1 so cost == rate."""
    route_types = route_types or {}
    rows, n = [], 0
    for route, rates in rates_by_route.items():
        origin, dest = route.split("-")
        for i, rate in enumerate(rates):
            n += 1
            rows.append({
                "shipment_id": f"S{n}", "origin": origin, "destination": dest,
                "route_type": route_types.get(route, "Short"), "material": "X",
                "quantity_tonnes": 1.0, "distance_km": 1.0,
                "freight_cost_inr": rate,
                "shipment_date": BASE + pd.Timedelta(weeks=i), "transporter": "T",
            })
    return pd.DataFrame(rows)


def build(rates_by_route, route_types=None):
    ships = metrics.prepare_shipments(make_ships(rates_by_route, route_types))
    return metrics.add_baselines(metrics.compute_weekly(ships))


def test_week_of_is_monday():
    raw = make_ships({"A-B": [1, 1]})
    raw["shipment_date"] = [pd.Timestamp("2024-01-07"), pd.Timestamp("2024-01-08")]  # Sun, Mon
    df = metrics.prepare_shipments(raw)
    assert list(df["week_of"]) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-08")]


def test_cost_is_pooled_not_mean_of_ratios():
    raw = make_ships({"A-B": [1]})
    extra = raw.iloc[[0]].copy()
    extra["shipment_id"] = "S99"
    raw.loc[0, ["quantity_tonnes", "distance_km", "freight_cost_inr"]] = [1, 10, 100]  # ratio 10
    extra[["quantity_tonnes", "distance_km", "freight_cost_inr"]] = [2, 10, 300]       # ratio 15
    raw = pd.concat([raw, extra], ignore_index=True)
    weekly = metrics.compute_weekly(metrics.prepare_shipments(raw))
    assert weekly.loc[0, "cost_per_tonne_km"] == pytest.approx(400 / 30)  # not 12.5


def test_history_excludes_current_week_and_caps_at_8():
    w = build({"A-B": list(range(1, 11))})  # rates 1..10
    assert w.loc[9, "own_hist_avg"] == pytest.approx(sum(range(2, 10)) / 8)  # weeks 2..9
    assert w.loc[2, "own_hist_avg"] == pytest.approx(1.5)                    # weeks 1,2


def test_history_cold_start_uses_available_weeks():
    w = build({"A-B": [5, 7, 9]})
    assert math.isnan(w.loc[0, "own_hist_avg"])
    assert list(w["n_prior_weeks"]) == [0, 1, 2]
    assert w.loc[1, "own_hist_avg"] == pytest.approx(5)


def test_peer_average_excludes_self():
    w = build({"A-B": [10], "C-D": [20], "E-F": [30]})
    a = w[w["route"] == "A-B"].iloc[0]
    assert a["peer_avg"] == pytest.approx(25)  # (20+30)/2, not including 10


def test_peer_is_nan_when_no_peers():
    w = build({"A-B": [10], "C-D": [20]}, {"A-B": "Short", "C-D": "Long"})
    assert w["peer_avg"].isna().all()


def test_validation_rejects_inconsistent_route_type():
    raw = make_ships({"A-B": [1, 2]})
    raw.loc[1, "route_type"] = "Long"
    with pytest.raises(ValueError):
        metrics.prepare_shipments(raw)