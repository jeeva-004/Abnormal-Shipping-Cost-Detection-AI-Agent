"""Central configuration: paths, model names, LLM settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / ".cache"

SHIPMENTS_CSV = DATA_DIR / "shipment_records.csv"
NOTES_CSV = DATA_DIR / "context_notes.csv"
SAMPLE_OUTPUT_CSV = DATA_DIR / "sample_output_format_v2.csv"

# Local models (change LLM_MODEL here if you pull a larger one later)
LLM_MODEL = "qwen2.5:1.5b"
EMBED_MODEL = "nomic-embed-text"

# Deterministic generation: temperature 0 + fixed seed + greedy top_k=1
LLM_OPTIONS = {"temperature": 0, "seed": 42, "top_k": 1}

# Output contract (must equal the header of sample_output_format_v2.csv)
OUTPUT_COLUMNS = [
    "route", "week_of", "cost_per_tonne_km", "vs_own_history",
    "vs_similar_routes", "flagged", "matched_note_id", "reason",
]

# Stage 2: flagging thresholds (calibrated from data; see README)
MIN_PRIOR_WEEKS = 4      # no flags until a route has this much history
RISE_PCT = 7.0           # "rising": at least +7% vs own trailing history
PEER_GAP_PCT = 20.0      # "out of ordinary": at least +20% vs similar routes
STRONG_RISE_PCT = 15.0   # ...or a big jump vs own history regardless of peers
# Stage 3: evidence layer
ALL_ROUTES = "All Routes"
EFFECT_PERSISTENCE_WEEKS = 8     # open-ended notes explain at most this many weeks
MAGNITUDE_TOLERANCE_PCT = 3.0    # slack when a note quotes a % range
RETRIEVAL_K = 5
PROMPT_VERSION = "v1"            # bump to invalidate the LLM cache
NOTES_GOLD_CSV = DATA_DIR / "notes_gold.csv"

# Stage 4: output
NEAR_NOTE_DAYS = 14      # cite the closest note in an unexplained reason only if this close
RESULTS_CSV = OUTPUT_DIR / "results.csv"