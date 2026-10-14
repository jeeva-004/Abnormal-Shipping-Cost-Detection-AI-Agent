"""Unit tests for Stage 2. Run: python -m pytest tests -v"""
import numpy as np
import pandas as pd

from src import flagging


def row(prior=8, own=0.0, peer=0.0):
    return pd.DataFrame([{"n_prior_weeks": prior, "vs_own_pct": own, "vs_peer_pct": peer}])


def flagged(**kw):
    return bool(flagging.flag_candidates(row(**kw)).loc[0, "is_candidate"])


def test_not_enough_history_never_flagged():
    assert not flagged(prior=3, own=40, peer=40)


def test_rise_but_peers_also_up_is_not_flagged():
    assert not flagged(own=8, peer=5)      # e.g. nationwide diesel rise


def test_rising_and_far_above_peers_is_flagged():
    assert flagged(own=7.5, peer=25)


def test_big_own_jump_flagged_even_without_peers():
    assert flagged(own=16, peer=np.nan)


def test_missing_own_history_never_flagged():
    assert not flagged(own=np.nan, peer=50)


def test_thresholds_are_inclusive_and_small_rise_ignored():
    assert flagged(own=7.0, peer=20.0)
    assert not flagged(own=6.9, peer=50)   # not rising enough