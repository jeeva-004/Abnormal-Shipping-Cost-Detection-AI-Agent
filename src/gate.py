"""Stage 3c: deterministic gate. A note justifies a row only if every check passes."""
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from src import config


@dataclass
class Explanation:
    verdict: str                                  # "justified" | "unexplained"
    note_id: str = ""                             # matched note (blank if unexplained)
    rejections: dict = field(default_factory=dict)  # note_id -> rejection code
    closest_id: str = ""                          # nearest in-scope note by date
    closest_gap_days: Optional[int] = None


def check_note(note, route, week_start, week_end, vs_own_pct, vs_peer_pct) -> Optional[str]:
    """Return None if the note justifies this row, else a rejection code."""
    if note.applies_to not in (route, config.ALL_ROUTES):
        return "wrong_scope"
    if note.eff_end < week_start or note.eff_start > week_end:
        return "outside_window"
    if note.effect != "raises_cost":
        return "no_cost_effect"
    if note.applies_to == config.ALL_ROUTES and vs_peer_pct >= config.PEER_GAP_PCT:
        return "market_wide_cannot_explain_peer_gap"
    if note.mag_high is not None and vs_own_pct > note.mag_high + config.MAGNITUDE_TOLERANCE_PCT:
        return "magnitude_exceeded"
    return None


def _gap_days(note, week_start, week_end) -> int:
    if note.eff_end < week_start:
        return (week_start - note.eff_end).days
    if note.eff_start > week_end:
        return (note.eff_start - week_end).days
    return 0


def explain(row, notes_by_id: dict, index) -> Explanation:
    """Explain one candidate row (needs: route, week_of, vs_own_pct, vs_peer_pct)."""
    week_start = row["week_of"].date()
    week_end = week_start + timedelta(days=6)
    route = row["route"]

    rejections, matched = {}, ""
    for note_id, _sim in index.search(route, week_start, week_end):
        code = check_note(notes_by_id[note_id], route, week_start, week_end,
                          row["vs_own_pct"], row["vs_peer_pct"])
        if code is None:
            matched = note_id
            break
        rejections[note_id] = code

    in_scope = [n for n in notes_by_id.values() if n.applies_to in (route, config.ALL_ROUTES)]
    closest = min(in_scope, key=lambda n: (_gap_days(n, week_start, week_end), n.note_id),
                  default=None)
    return Explanation(
        verdict="justified" if matched else "unexplained",
        note_id=matched, rejections=rejections,
        closest_id=closest.note_id if closest else "",
        closest_gap_days=_gap_days(closest, week_start, week_end) if closest else None,
    )