# FreightTiger Shipping-Cost Watchdog

Flags weeks where a route's cost per tonne-km rises abnormally, then says whether a context note
genuinely explains it. If no note applies it says **unexplained**; it never guesses.

## Quick start (Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
python scripts\check_env.py        # environment check
python run.py                      # writes output\results.csv
```
Place the three input CSVs in `data\`: `shipment_records.csv`, `context_notes.csv`, `sample_output_format_v2.csv`.

## How it works
```
shipments -> weekly cost per tonne-km -> baselines -> flag rule -> 13 candidate rows
notes -> LLM label (+ keyword check) -> vector index -> deterministic gate -> verdict -> results.csv
```
1. **Weekly metrics** (`src/metrics.py`). Group by route (`Origin-Destination`) and Monday-based week.
   Cost per tonne-km = sum(cost) / sum(tonnes x km), pooled (not an average of per-shipment ratios).
   - *vs own history:* mean of the route's previous up to 8 weekly values, strictly before the current week.
     With fewer than 8 prior weeks, all available weeks are used; the first week has no baseline (blank, not padded).
   - *vs similar routes:* mean of all other routes with the same `route_type` in the same week.
2. **Flag rule** (`src/flagging.py`). A route-week is a candidate when it has >= 4 prior weeks, is >= +7% vs
   own history, AND (>= +20% vs similar routes OR >= +15% vs own history). Thresholds are in `src/config.py`.
3. **Note understanding** (`src/notes.py`). The local LLM (Qwen 2.5 1.5B, temperature 0, seed 42) labels each
   note once as raises_cost / no_cost_effect / unclear. A keyword check must agree; any disagreement becomes
   `unclear`, which can never justify a row. Date windows and % magnitudes are parsed by regex, not by the LLM.
4. **Retrieval** (`src/retrieval.py`). Chroma vector index over the notes (nomic-embed-text embeddings),
   filtered to notes for the route (or "All Routes") whose window overlaps the week.
5. **Gate** (`src/gate.py`). A retrieved note justifies a row only if it applies to the route, its window
   overlaps the week, it says costs rose, it is not a market-wide note being used to explain a gap versus peers,
   and its quoted % (if any) is not far below the observed rise.
6. **Output** (`src/reasons.py`, `src/pipeline.py`). Reasons are templates filled from the verified note
   (id, date, window, text); no LLM writes them. The output is validated before and after writing.

## Decisions and ambiguities
- **Flag thresholds are not given in the brief.** I chose them from the data's distribution; results are
  stable (13 candidates) for any rise threshold of 7 and any peer threshold from 10 to 20 (grid in `scripts/stage2_check.py`).
- **Output contains only flagged candidates** (13 rows, like the 3-row sample). All 728 route-weeks with
  baselines are in `output/weekly_metrics.csv`.
- **Open-ended notes** ("starting this week", N003) explain at most 8 weeks, after which the own-history
  baseline has absorbed the shift. A note that only says 5-7% cannot explain a much larger rise.
- **Nationwide rises** (the May 2025 diesel step) lift every route together, so they are not "out of the
  ordinary" versus similar routes and are not flagged.
- **`sample_output_format_v2.csv`** has an unquoted comma in its last row, so it does not parse as CSV.
  I treat only its header as the contract and write properly quoted fields. The brief names the file
  `sample_output_format.csv`; I used the supplied `_v2`.
- **Sample-row check:** my numbers, flags and note ids reproduce all 3 rows of the sample exactly.

## How I checked it is right
| Check | Command | Result I observed |
|---|---|---|
| Unit tests (metrics, flags, parsing, gate, output) | `python -m pytest tests -v` | 37 passed |
| Eval harness: note labels, 13 result rows + 4 must-not-flag rows, 3 sample rows, 11 trap scenarios | `python eval\run_eval.py` | 35/35 checks passed |
| Independent recomputation of weekly numbers in plain Python | `python scripts\stage1_check.py` | 3/3 matched |
| Reproducibility, 3 fresh runs, no cache | `python scripts\repro.py` | identical results and metrics files (hashes in `output/repro_report.md`) |

## Reproducibility
LLM options: temperature 0, seed 42, top_k 1 (greedy). Everything that decides a verdict or number is
deterministic code. `repro.py` re-calls the LLM and embeddings in all 3 runs (`--no-cache`), so cached
answers cannot hide variation. Full table: `output/repro_report.md`.

## Cost of one full run
10 LLM calls, 1,986 input tokens, 86 output tokens; 14 embedding calls, 550 tokens. Local Ollama models:
no per-token charge. LLM calls scale with the number of notes, not with shipments. Details: `output/cost_log.md`.

## Known limitations
- Thresholds were tuned on the same data they are scored on; no held-out data was available.
- My hand labels (`eval/gold_rows.csv`, `data/notes_gold.csv`) are my reading of the notes, so that part of the
  eval catches regressions rather than proving independence. The 3 sample rows and the trap scenarios are the stronger evidence.
- The 1.5B model labeled one note (N010) wrongly (9/10); the keyword check caught it. A larger model would help.
- Short and Long route types have only 2 routes, so "similar routes" there is a single other route.
- Mumbai-Pune is structurally above its peers (~12% typical), so its peer gap is partly normal.
- Stretch goal (plain-English Q&A over findings) is not implemented.

## Layout
`run.py` entry point - `src/` logic - `tests/` unit tests - `eval/` labeled checks and scenarios -
`scripts/` environment, stage and reproducibility checks - `output/` results, audit, cost and repro reports.# FreightTiger Shipping-Cost Watchdog

Flags weeks where a route's cost per tonne-km rises abnormally, then says whether a context note
genuinely explains it. If no note applies it says **unexplained**; it never guesses.

## Quick start (Windows)
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
python scripts\check_env.py        # environment check
python run.py                      # writes output\results.csv
```
Place the three input CSVs in `data\`: `shipment_records.csv`, `context_notes.csv`, `sample_output_format_v2.csv`.

## How it works
```
shipments -> weekly cost per tonne-km -> baselines -> flag rule -> 13 candidate rows
notes -> LLM label (+ keyword check) -> vector index -> deterministic gate -> verdict -> results.csv
```
1. **Weekly metrics** (`src/metrics.py`). Group by route (`Origin-Destination`) and Monday-based week.
   Cost per tonne-km = sum(cost) / sum(tonnes x km), pooled (not an average of per-shipment ratios).
   - *vs own history:* mean of the route's previous up to 8 weekly values, strictly before the current week.
     With fewer than 8 prior weeks, all available weeks are used; the first week has no baseline (blank, not padded).
   - *vs similar routes:* mean of all other routes with the same `route_type` in the same week.
2. **Flag rule** (`src/flagging.py`). A route-week is a candidate when it has >= 4 prior weeks, is >= +7% vs
   own history, AND (>= +20% vs similar routes OR >= +15% vs own history). Thresholds are in `src/config.py`.
3. **Note understanding** (`src/notes.py`). The local LLM (Qwen 2.5 1.5B, temperature 0, seed 42) labels each
   note once as raises_cost / no_cost_effect / unclear. A keyword check must agree; any disagreement becomes
   `unclear`, which can never justify a row. Date windows and % magnitudes are parsed by regex, not by the LLM.
4. **Retrieval** (`src/retrieval.py`). Chroma vector index over the notes (nomic-embed-text embeddings),
   filtered to notes for the route (or "All Routes") whose window overlaps the week.
5. **Gate** (`src/gate.py`). A retrieved note justifies a row only if it applies to the route, its window
   overlaps the week, it says costs rose, it is not a market-wide note being used to explain a gap versus peers,
   and its quoted % (if any) is not far below the observed rise.
6. **Output** (`src/reasons.py`, `src/pipeline.py`). Reasons are templates filled from the verified note
   (id, date, window, text); no LLM writes them. The output is validated before and after writing.

## Decisions and ambiguities
- **Flag thresholds are not given in the brief.** I chose them from the data's distribution; results are
  stable (13 candidates) for any rise threshold of 7 and any peer threshold from 10 to 20 (grid in `scripts/stage2_check.py`).
- **Output contains only flagged candidates** (13 rows, like the 3-row sample). All 728 route-weeks with
  baselines are in `output/weekly_metrics.csv`.
- **Open-ended notes** ("starting this week", N003) explain at most 8 weeks, after which the own-history
  baseline has absorbed the shift. A note that only says 5-7% cannot explain a much larger rise.
- **Nationwide rises** (the May 2025 diesel step) lift every route together, so they are not "out of the
  ordinary" versus similar routes and are not flagged.
- **`sample_output_format_v2.csv`** has an unquoted comma in its last row, so it does not parse as CSV.
  I treat only its header as the contract and write properly quoted fields. The brief names the file
  `sample_output_format.csv`; I used the supplied `_v2`.
- **Sample-row check:** my numbers, flags and note ids reproduce all 3 rows of the sample exactly.

## How I checked it is right
| Check | Command | Result I observed |
|---|---|---|
| Unit tests (metrics, flags, parsing, gate, output) | `python -m pytest tests -v` | 37 passed |
| Eval harness: note labels, 13 result rows + 4 must-not-flag rows, 3 sample rows, 11 trap scenarios | `python eval\run_eval.py` | 35/35 checks passed |
| Independent recomputation of weekly numbers in plain Python | `python scripts\stage1_check.py` | 3/3 matched |
| Reproducibility, 3 fresh runs, no cache | `python scripts\repro.py` | identical results and metrics files (hashes in `output/repro_report.md`) |

## Reproducibility
LLM options: temperature 0, seed 42, top_k 1 (greedy). Everything that decides a verdict or number is
deterministic code. `repro.py` re-calls the LLM and embeddings in all 3 runs (`--no-cache`), so cached
answers cannot hide variation. Full table: `output/repro_report.md`.

## Cost of one full run
10 LLM calls, 1,986 input tokens, 86 output tokens; 14 embedding calls, 550 tokens. Local Ollama models:
no per-token charge. LLM calls scale with the number of notes, not with shipments. Details: `output/cost_log.md`.

## Known limitations
- Thresholds were tuned on the same data they are scored on; no held-out data was available.
- My hand labels (`eval/gold_rows.csv`, `data/notes_gold.csv`) are my reading of the notes, so that part of the
  eval catches regressions rather than proving independence. The 3 sample rows and the trap scenarios are the stronger evidence.
- The 1.5B model labeled one note (N010) wrongly (9/10); the keyword check caught it. A larger model would help.
- Short and Long route types have only 2 routes, so "similar routes" there is a single other route.
- Mumbai-Pune is structurally above its peers (~12% typical), so its peer gap is partly normal.

## Layout
`run.py` entry point - `src/` logic - `tests/` unit tests - `eval/` labeled checks and scenarios -
`scripts/` environment, stage and reproducibility checks - `output/` results, audit, cost and repro reports.