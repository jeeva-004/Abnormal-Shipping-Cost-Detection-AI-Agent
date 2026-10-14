"""Reproducibility check + token/cost log. Run from project root: python scripts/repro.py
Runs the pipeline 3 times with --no-cache (LLM and embeddings really re-called each time)."""
import ast
import difflib
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402

N_RUNS = 3
# ASSUMPTION for illustration only: a hosted small-model rate. Local Ollama has no per-token fee.
ILLUSTRATIVE_USD_PER_M_TOKENS = 0.10


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


config.OUTPUT_DIR.mkdir(exist_ok=True)
runs = []
for i in range(1, N_RUNS + 1):
    out = config.OUTPUT_DIR / f"repro_run{i}.csv"
    print(f"run {i}/{N_RUNS} (fresh LLM + embedding calls, no cache)...", flush=True)
    p = subprocess.run([sys.executable, str(ROOT / "run.py"), "--no-cache", "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stdout, p.stderr)
        sys.exit("run failed")
    usage_line = next(l for l in p.stdout.splitlines() if l.startswith("usage:"))
    usage = ast.literal_eval(usage_line[len("usage:"):].strip())
    runs.append({"file": out, "results_sha": sha(out),
                 "metrics_sha": sha(config.OUTPUT_DIR / "weekly_metrics.csv"), "usage": usage})
    print(f"   results sha256 {runs[-1]['results_sha'][:16]}...  LLM calls={usage['llm_calls']}")

same_results = len({r["results_sha"] for r in runs}) == 1
same_metrics = len({r["metrics_sha"] for r in runs}) == 1
print("\nresults.csv identical across runs:        ", "YES" if same_results else "NO")
print("weekly_metrics.csv identical across runs:  ", "YES" if same_metrics else "NO")

if not same_results:
    base = runs[0]["file"].read_text(encoding="utf-8").splitlines()
    for r in runs[1:]:
        diff = list(difflib.unified_diff(base, r["file"].read_text(encoding="utf-8").splitlines(), lineterm="", n=0))
        print("\n".join(diff[:20]))

submission = config.RESULTS_CSV
if submission.exists():
    print("submitted results.csv equals fresh-run output: ", "YES" if sha(submission) == runs[0]["results_sha"] else "NO (re-run python run.py)")

u = runs[0]["usage"]
total_tokens = u["llm_input_tokens"] + u["llm_output_tokens"] + u["embed_input_tokens"]
illustrative = total_tokens / 1_000_000 * ILLUSTRATIVE_USD_PER_M_TOKENS

report = f"""# Reproducibility report

Three consecutive runs on the same input, each with `--no-cache` (all LLM and embedding calls repeated).

| Run | results.csv SHA-256 | weekly_metrics.csv SHA-256 | LLM calls |
|---|---|---|---|
""" + "\n".join(f"| {i} | `{r['results_sha']}` | `{r['metrics_sha']}` | {r['usage']['llm_calls']} |"
                for i, r in enumerate(runs, 1)) + f"""

Result: results.csv identical = **{'YES' if same_results else 'NO'}**, weekly_metrics.csv identical = **{'YES' if same_metrics else 'NO'}**.

Randomness controls: LLM options {config.LLM_OPTIONS} (temperature 0, fixed seed, greedy top_k=1) so the model always picks its most likely token.
All numbers, flags, gate decisions and reason text are deterministic code; the LLM only labels 10 notes, and a keyword check must agree with it before any note can justify a row.
"""
(config.OUTPUT_DIR / "repro_report.md").write_text(report, encoding="utf-8")

cost = f"""# Token and cost log (one full run over all 2,940 shipments, no cache)

| Item | Count |
|---|---|
| LLM calls | {u['llm_calls']} |
| LLM input tokens | {u['llm_input_tokens']} |
| LLM output tokens | {u['llm_output_tokens']} |
| Embedding calls | {u['embed_calls']} |
| Embedding input tokens | {u['embed_input_tokens']} |
| Total tokens | {total_tokens} |

Model: `{config.LLM_MODEL}` (chat) and `{config.EMBED_MODEL}` (embeddings), both run locally via Ollama.

- Actual cost: no per-token charge for local models (compute only: your own machine).
- Illustration only: at an *assumed* hosted rate of ${ILLUSTRATIVE_USD_PER_M_TOKENS}/1M tokens (not a published Qwen price; replace with your provider's rate) this run would cost about ${illustrative:.5f}.
- LLM calls scale with the number of notes ({u['llm_calls']}), not with shipments (2,940), route-weeks (728) or flagged rows (13).
"""
(config.OUTPUT_DIR / "cost_log.md").write_text(cost, encoding="utf-8")
print("\nwrote output\\repro_report.md and output\\cost_log.md")
print("REPRODUCIBILITY CHECK PASSED" if same_results and same_metrics else "REPRODUCIBILITY CHECK FAILED")
sys.exit(0 if same_results and same_metrics else 1)