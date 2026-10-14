"""Stage 3a: turn each free-text note into structured, verifiable facts."""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Optional

import pandas as pd

from src import config, usage

EFFECTS = ("raises_cost", "no_cost_effect", "unclear")
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

_RANGE = re.compile(r"\b([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s+to\s+([A-Za-z]{3})[a-z]*\s+(\d{1,2})\b")
_OPEN = re.compile(r"\bstarting this week\b", re.I)
_PCT_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%")
_PCT_ONE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_POSITIVE = re.compile(r"\b(higher|pushing up|push(?:ed|ing)? up|surcharge|rose|risen|"
                       r"increase[ds]?|raised|hike[ds]?)\b", re.I)
_NEGATIVE = re.compile(r"not\s+(?:significantly\s+)?affected|no\s+(?:major\s+|significant\s+)?disruptions|"
                       r"without a rate change|not part of|returned to normal|"
                       r"remained\s+(?:stable|normal)|improved road", re.I)


@dataclass(frozen=True)
class Note:
    note_id: str
    date: date
    applies_to: str
    text: str
    llm_effect: str
    rule_effect: str
    effect: str                 # final: raises_cost only if LLM and rules agree
    eff_start: date             # effective window, inclusive
    eff_end: date
    open_ended: bool
    mag_low: Optional[float]
    mag_high: Optional[float]


# ---------- deterministic parsing ----------
def load_notes_csv(path=config.NOTES_CSV) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"note_id", "date", "applies_to", "note"}
    if need - set(df.columns):
        raise ValueError(f"Notes file missing columns: {sorted(need - set(df.columns))}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ("note_id", "applies_to", "note"):
        df[col] = df[col].astype(str).str.strip()
    if df["note_id"].duplicated().any():
        raise ValueError("Duplicate note_id values")
    return df


def parse_window(text: str, note_date: date):
    """Return (start, end_or_None). None end means open-ended."""
    m = _RANGE.search(text)
    if m and m.group(1).lower() in MONTHS and m.group(3).lower() in MONTHS:
        start = date(note_date.year, MONTHS[m.group(1).lower()], int(m.group(2)))
        end = date(note_date.year, MONTHS[m.group(3).lower()], int(m.group(4)))
        if end < start:
            end = end.replace(year=end.year + 1)
        return start, end
    if _OPEN.search(text):
        return note_date, None
    monday = note_date - timedelta(days=note_date.weekday())
    return monday, monday + timedelta(days=6)   # default: the Mon-Sun week of the note


def effective_window(start: date, end: Optional[date]):
    """Cap open-ended notes at EFFECT_PERSISTENCE_WEEKS."""
    if end is None:
        return start, start + timedelta(weeks=config.EFFECT_PERSISTENCE_WEEKS) - timedelta(days=1), True
    return start, end, False


def parse_magnitude(text: str):
    m = _PCT_RANGE.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _PCT_ONE.search(text)
    if m:
        return float(m.group(1)), float(m.group(1))
    return None, None


def rule_effect(text: str) -> str:
    """Keyword second opinion. Negative cues win over positive cues."""
    if _NEGATIVE.search(text):
        return "no_cost_effect"
    if _POSITIVE.search(text):
        return "raises_cost"
    return "unclear"


def combine_effect(llm: str, rules: str) -> str:
    """Only a unanimous verdict counts; any disagreement is 'unclear'."""
    return llm if llm == rules else "unclear"


# ---------- caching ----------
def _read_cache(name: str) -> dict:
    p = config.CACHE_DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _write_cache(name: str, data: dict) -> None:
    config.CACHE_DIR.mkdir(exist_ok=True)
    (config.CACHE_DIR / name).write_text(json.dumps(data), encoding="utf-8")


def _key(*parts) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# ---------- LLM classification ----------
_SYSTEM = """You label short freight-industry notes by their effect on freight COST.
Answer with JSON: {"effect": "<label>"}. Labels:
- raises_cost: the note says freight costs went up, or a surcharge / higher trip cost applied.
- no_cost_effect: costs were not affected, stable, back to normal, no rate change, or the note is about something that does not touch the routes in question.
- unclear: you cannot tell.
Examples:
"A 4% fuel surcharge was added by all transporters this month." -> {"effect": "raises_cost"}
"Road works finished; traffic and rates unchanged." -> {"effect": "no_cost_effect"}
"A new rule was announced for a region we do not serve." -> {"effect": "no_cost_effect"}"""

_SCHEMA = {"type": "object",
           "properties": {"effect": {"type": "string", "enum": list(EFFECTS)}},
           "required": ["effect"]}


def classify_effect(text: str, use_cache: bool = True) -> str:
    """Ask the local LLM (temperature 0, fixed seed). Any failure -> 'unclear'."""
    cache = _read_cache("llm_effects.json") if use_cache else {}
    k = _key(config.LLM_MODEL, config.PROMPT_VERSION, text)
    if k in cache:
        return cache[k]["effect"]
    import ollama
    for fmt in (_SCHEMA, "json"):          # schema first; plain json for older servers
        try:
            r = ollama.chat(model=config.LLM_MODEL,
                            messages=[{"role": "system", "content": _SYSTEM},
                                      {"role": "user", "content": f'Note: "{text}"'}],
                            format=fmt, options={**config.LLM_OPTIONS, "num_predict": 40})
            usage.TRACKER.record("llm", config.LLM_MODEL, getattr(r, "prompt_eval_count", 0),
                                 getattr(r, "eval_count", 0))
            effect = json.loads(r["message"]["content"]).get("effect", "unclear")
            effect = effect if effect in EFFECTS else "unclear"
            if use_cache:
                cache[k] = {"effect": effect}
                _write_cache("llm_effects.json", cache)
            return effect
        except Exception as e:  # noqa: BLE001
            last = e
    print(f"  WARNING: LLM classification failed ({str(last)[:80]}); using 'unclear'")
    return "unclear"


# ---------- embeddings ----------
def embed_texts(texts: list, use_cache: bool = True) -> list:
    """Embed texts with the local embedding model (cached on disk)."""
    cache = _read_cache("embeddings.json") if use_cache else {}
    keys = [_key(config.EMBED_MODEL, t) for t in texts]
    missing = [t for t, k in zip(texts, keys) if k not in cache]
    if missing:
        import ollama
        r = ollama.embed(model=config.EMBED_MODEL, input=missing)
        usage.TRACKER.record("embed", config.EMBED_MODEL, getattr(r, "prompt_eval_count", 0), 0)
        for t, vec in zip(missing, r["embeddings"]):
            cache[_key(config.EMBED_MODEL, t)] = list(vec)
        if use_cache:
            _write_cache("embeddings.json", cache)
    return [cache[k] for k in keys]


# ---------- assembly ----------
def enrich_notes(df: pd.DataFrame, classify: Callable = classify_effect,
                 use_cache: bool = True) -> list:
    notes = []
    for r in df.itertuples(index=False):
        llm = classify(r.note, use_cache) if classify is classify_effect else classify(r.note)
        rules = rule_effect(r.note)
        start, end = parse_window(r.note, r.date)
        eff_start, eff_end, open_ended = effective_window(start, end)
        low, high = parse_magnitude(r.note)
        notes.append(Note(r.note_id, r.date, r.applies_to, r.note, llm, rules,
                          combine_effect(llm, rules), eff_start, eff_end, open_ended, low, high))
    return notes