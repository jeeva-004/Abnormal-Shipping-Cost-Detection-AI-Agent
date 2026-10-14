"""Stage 2: decide which route-weeks are anomalous cost rises (candidates)."""
import pandas as pd

from src import config


def flag_mask(df: pd.DataFrame, rise=config.RISE_PCT, peer=config.PEER_GAP_PCT,
              strong=config.STRONG_RISE_PCT, min_weeks=config.MIN_PRIOR_WEEKS) -> pd.Series:
    """True where a route-week is rising AND out of the ordinary.

    Comparisons with NaN (no history / no peers) evaluate to False, so rows
    without a baseline are never flagged.
    """
    enough_history = df["n_prior_weeks"] >= min_weeks
    rising = df["vs_own_pct"] >= rise
    unusual = (df["vs_peer_pct"] >= peer) | (df["vs_own_pct"] >= strong)
    return enough_history & rising & unusual


def flag_candidates(weekly: pd.DataFrame) -> pd.DataFrame:
    """Add `is_candidate` and `trigger` (which condition fired) columns."""
    df = weekly.copy()
    df["is_candidate"] = flag_mask(df)
    vs_peers = df["vs_peer_pct"] >= config.PEER_GAP_PCT
    vs_own = df["vs_own_pct"] >= config.STRONG_RISE_PCT
    df["trigger"] = ""
    df.loc[df["is_candidate"] & vs_peers & vs_own, "trigger"] = "peers+own_history"
    df.loc[df["is_candidate"] & vs_peers & ~vs_own, "trigger"] = "peers"
    df.loc[df["is_candidate"] & ~vs_peers & vs_own, "trigger"] = "own_history"
    return df