# FreightTiger Shipping-Cost Watchdog

Flags abnormal weekly increases in route cost per tonne-km and checks whether a relevant context note explains them. If evidence is insufficient, the result is **unexplained**—never guessed.

## Quick Start (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
python scripts/check_env.py
python run.py
```

Output: `output/results.csv`

Place `shipment_records.csv`, `context_notes.csv`, and `sample_output_format_v2.csv` in `data/`.

## How It Works

```text
Shipments → Weekly Metrics → Baselines → Flagging → 13 Candidates
Context Notes → LLM Labels + Keyword Check → Vector Retrieval
→ Evidence Gate → Verdicts → Validated results.csv
```

1. **Weekly metrics** (`src/metrics.py`): Groups shipments by route and Monday-based week. Cost per tonne-km = total cost ÷ total (tonnes × km). Historical baselines use up to 8 previous weeks; similar-route baselines use other routes of the same type in the same week. Missing history remains blank.

2. **Flagging** (`src/flagging.py`, `src/config.py`): Requires at least 4 prior weeks, a rise of ≥7% over the route's history, and either ≥20% over similar routes or ≥15% over its history.

3. **Note labeling** (`src/notes.py`): Qwen 2.5 1.5B (temperature 0, seed 42) labels notes as `raises_cost`, `no_cost_effect`, or `unclear`. A keyword check must agree; otherwise, the label becomes `unclear`. Dates and percentages are parsed using regex.

4. **Retrieval** (`src/retrieval.py`): Chroma and `nomic-embed-text` retrieve notes matching the route (or `All Routes`) and overlapping the week.

5. **Evidence gate** (`src/gate.py`): A note must match the route and time window, indicate rising costs, and support the observed increase. Market-wide notes cannot explain a gap versus peers.

6. **Output** (`src/reasons.py`, `src/pipeline.py`): Reasons use templates populated from verified note details, not LLM-generated explanations. Output is validated before and after writing.

## Decisions & Ambiguities

- **Thresholds:** The brief specifies none. Chosen from the data distribution; 13 candidates remain stable at a 7% historical threshold and peer thresholds of 10–20%. See `scripts/stage2_check.py`.
- **Output scope:** `results.csv` contains 13 flagged candidates; all 728 route-weeks with baselines are in `output/weekly_metrics.csv`.
- **Open-ended notes:** N003 (“starting this week”) can explain up to 8 weeks, until the historical baseline absorbs the change. A stated 5–7% rise cannot explain a much larger increase.
- **Nationwide rises:** The May 2025 diesel increase affects routes together, so it does not create an unusual peer gap.
- **Sample format:** The supplied `sample_output_format_v2.csv` has an unquoted comma in its last row. Its header defines the output contract; generated fields are properly quoted. The brief names `sample_output_format.csv`, but the supplied `_v2` file was used.
- **Sample validation:** All 3 sample rows' numbers, flags, and note IDs match exactly.

## Validation Results

| Check | Command | Result |
|---|---|---|
| Unit tests | `python -m pytest tests -v` | 37 passed |
| Evaluation: labels, output rows, sample rows, trap scenarios | `python eval/run_eval.py` | 35/35 passed |
| Independent weekly-metric recomputation | `python scripts/stage1_check.py` | 3/3 matched |
| Three fresh, uncached runs | `python scripts/repro.py` | Identical results and metrics |

## Reproducibility

LLM settings: temperature 0, seed 42, top-k 1 (greedy). Deterministic code calculates metrics and decides verdicts. `repro.py` reruns the LLM and embeddings without cache across three runs. See `output/repro_report.md` for hashes.

## Run Cost

- **LLM:** 10 calls; 1,986 input and 86 output tokens.
- **Embeddings:** 14 calls; 550 tokens.
- **Cost:** No per-token charge with local Ollama.
- Calls scale with note count, not shipment count.

Details: `output/cost_log.md`.

## Known Limitations

- Thresholds were tuned and evaluated on the same data; no held-out dataset was available.
- Hand-labeled evaluation data (`eval/gold_rows.csv`, `data/notes_gold.csv`) tests regressions, not independent accuracy. Sample rows and trap scenarios provide stronger checks.
- The 1.5B model mislabeled N010 (9/10 labels correct); the keyword check caught the error. A larger model may improve labeling.
- Short and Long route types have only 2 routes each, leaving just one peer for comparison.
- Mumbai–Pune typically runs ~12% above peers, so part of its peer gap is structural.
- The optional plain-English Q&A stretch goal is not implemented.

## Project Layout

- `run.py` — entry point
- `src/` — application logic
- `tests/` — unit tests
- `eval/` — labeled evaluation data and scenarios
- `scripts/` — environment, validation, and reproducibility checks
- `output/` — results, metrics, audit, cost, and reproducibility reports