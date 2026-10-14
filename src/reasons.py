"""Stage 4a: format numbers and write grounded reasons (templates only, no LLM)."""
import pandas as pd

from src import config

FLAG_BY_VERDICT = {"justified": "No (justified)", "unexplained": "Yes"}
GENERIC_UNEXPLAINED = ("No matching note found for this route or date range. "
                       "Cost rise looks unexplained and worth a human review.")
REVIEW_TAIL = "No genuine justification found; flagged for review."


def fmt_vs_own(pct) -> str:
    if pct is None or pd.isna(pct):
        return "n/a (no prior weeks)"
    return f"{pct:+.1f}% vs this route's past average"


def fmt_vs_peers(pct) -> str:
    if pct is None or pd.isna(pct):
        return "n/a (no similar routes this week)"
    return f"{pct:+.1f}% vs similar-length routes this week"


def _sentence(text: str) -> str:
    t = " ".join(str(text).split())
    return t if t.endswith((".", "!", "?")) else t + "."


def _window(note) -> str:
    if note.open_ended:
        return (f"effective from {note.eff_start} for up to "
                f"{config.EFFECT_PERSISTENCE_WEEKS} weeks")
    return f"effective {note.eff_start} to {note.eff_end}"


def justified_reason(note) -> str:
    return (f"Justified by note {note.note_id} dated {note.date} "
            f"(applies to {note.applies_to}; {_window(note)}): {_sentence(note.text)} "
            f"The cost rise has a clear explanation.")


def unexplained_reason(exp, by_id: dict, row) -> str:
    """Generic text, or cite the closest note when it is genuinely close in time."""
    near = (exp.closest_id and exp.closest_gap_days is not None
            and exp.closest_gap_days <= config.NEAR_NOTE_DAYS)
    if not near:
        return GENERIC_UNEXPLAINED
    n = by_id[exp.closest_id]
    ref = f"{n.note_id}, {n.date}"
    if n.effect == "raises_cost":
        code = exp.rejections.get(n.note_id)
        if code == "market_wide_cannot_explain_peer_gap":
            return (f"Note {ref} reports a market-wide cost rise, but this route is far above "
                    f"similar routes that faced the same conditions, so it cannot explain the gap. "
                    f"{REVIEW_TAIL}")
        if code == "magnitude_exceeded":
            size = (f"{n.mag_low:g}-{n.mag_high:g}%" if n.mag_low != n.mag_high
                    else f"{n.mag_high:g}%")
            return (f"Note {ref} explains only a rise of about {size}, far below the "
                    f"{float(row['vs_own_pct']):+.1f}% rise seen here. {REVIEW_TAIL}")
        if exp.closest_gap_days > 0:
            return (f"The nearest note ({ref}) describes a cost rise, but its window "
                    f"({n.eff_start} to {n.eff_end}) does not cover the week of "
                    f"{row['week_of'].date()}, so it cannot justify this rise. {REVIEW_TAIL}")
        return GENERIC_UNEXPLAINED
    return (f'The closest note ({ref}) says: "{_sentence(n.text)}" -- it does not establish '
            f"a reason for a cost rise on this route. {REVIEW_TAIL}")


def build_reason(exp, by_id: dict, row) -> str:
    if exp.verdict == "justified":
        return justified_reason(by_id[exp.note_id])
    return unexplained_reason(exp, by_id, row)