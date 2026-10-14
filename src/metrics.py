"""Stage 1: load shipments, build weekly cost per tonne-km, add baselines."""
import numpy as np
import pandas as pd

from src import config

REQUIRED_COLUMNS = [
    "shipment_id", "origin", "destination", "route_type", "material",
    "quantity_tonnes", "distance_km", "freight_cost_inr", "shipment_date",
    "transporter",
]
VALID_ROUTE_TYPES = {"Short", "Medium", "Long"}
HISTORY_WINDOW = 8  # weeks, fixed by the case study


def prepare_shipments(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate raw shipments and add `route` and `week_of` (Monday) columns."""
    missing = set(REQUIRED_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df = raw.copy()
    if df[REQUIRED_COLUMNS].isna().any().any():
        raise ValueError("Shipment data contains null values")
    if df["shipment_id"].duplicated().any():
        raise ValueError("Duplicate shipment_id values found")
    for col in ("quantity_tonnes", "distance_km", "freight_cost_inr"):
        if (df[col] <= 0).any():
            raise ValueError(f"Non-positive values in {col}")
    bad_types = set(df["route_type"].unique()) - VALID_ROUTE_TYPES
    if bad_types:
        raise ValueError(f"Unknown route_type values: {sorted(bad_types)}")

    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="raise")
    df["route"] = df["origin"].str.strip() + "-" + df["destination"].str.strip()

    if (df.groupby("route")["route_type"].nunique() > 1).any():
        raise ValueError("A route has more than one route_type")

    # Weeks run Monday-Sunday; week_of is that week's Monday.
    days_since_monday = pd.to_timedelta(df["shipment_date"].dt.dayofweek, unit="D")
    df["week_of"] = (df["shipment_date"] - days_since_monday).dt.normalize()
    return df


def compute_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """One row per route-week with pooled cost per tonne-km."""
    df = df.assign(tonne_km=df["quantity_tonnes"] * df["distance_km"])
    weekly = df.groupby(["route", "route_type", "week_of"], as_index=False).agg(
        n_shipments=("shipment_id", "size"),
        total_cost_inr=("freight_cost_inr", "sum"),
        total_tonne_km=("tonne_km", "sum"),
    )
    weekly["cost_per_tonne_km"] = weekly["total_cost_inr"] / weekly["total_tonne_km"]
    return weekly.sort_values(["route", "week_of"]).reset_index(drop=True)


def add_baselines(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add own-history and similar-routes baselines plus % differences."""
    w = weekly.sort_values(["route", "week_of"]).reset_index(drop=True).copy()
    rate = w["cost_per_tonne_km"]

    # Own history: previous <=8 weeks only (shift(1) removes the current week).
    w["own_hist_avg"] = w.groupby("route")["cost_per_tonne_km"].transform(
        lambda s: s.shift(1).rolling(HISTORY_WINDOW, min_periods=1).mean()
    )
    w["n_prior_weeks"] = w.groupby("route").cumcount().clip(upper=HISTORY_WINDOW)

    # Peers: same week + same route_type, excluding the route itself.
    grp = w.groupby(["route_type", "week_of"])["cost_per_tonne_km"]
    total, count = grp.transform("sum"), grp.transform("count")
    w["peer_avg"] = np.where(count > 1, (total - rate) / (count - 1).clip(lower=1), np.nan)

    w["vs_own_pct"] = 100 * (rate / w["own_hist_avg"] - 1)
    w["vs_peer_pct"] = 100 * (rate / w["peer_avg"] - 1)
    return w


def build_metrics(path=config.SHIPMENTS_CSV) -> pd.DataFrame:
    """Full Stage 1 pipeline: CSV -> validated -> weekly -> baselines."""
    raw = pd.read_csv(path)
    return add_baselines(compute_weekly(prepare_shipments(raw)))