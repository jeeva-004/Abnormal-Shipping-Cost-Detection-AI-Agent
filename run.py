"""Run the full pipeline. Usage (from project root):
    python run.py              # use cached note labels/embeddings
    python run.py --no-cache   # call the LLM/embeddings fresh
    python run.py --out path\\to\\file.csv
"""
import argparse
import hashlib
from pathlib import Path

from src import config, pipeline, usage


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--out", default=str(config.RESULTS_CSV))
    args = p.parse_args()

    results, weekly, _ = pipeline.run_pipeline(use_cache=not args.no_cache)
    out = Path(args.out)
    pipeline.write_results(results, out)
    n_rows = pipeline.validate_file(out)

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    weekly.to_csv(config.OUTPUT_DIR / "weekly_metrics.csv", index=False)   # full audit trail

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    n_just = int((results["flagged"] == "No (justified)").sum())
    print(f"wrote {out}  rows={n_rows}  justified={n_just}  flagged(Yes)={n_rows - n_just}")
    print(f"sha256: {digest}")
    print(f"usage: {usage.TRACKER.summary()}")


if __name__ == "__main__":
    main()