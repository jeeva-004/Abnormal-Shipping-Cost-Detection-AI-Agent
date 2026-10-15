"""Environment check. Run from the project root: python scripts/check_env.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config 

results = []


def report(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))


# 1. Python version
report("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])

# 2. Libraries
for lib in ("pandas", "numpy", "ollama", "chromadb", "pytest"):
    try:
        mod = __import__(lib)
        report(f"import {lib}", True, getattr(mod, "__version__", ""))
    except Exception as e:
        report(f"import {lib}", False, str(e)[:120])

# 3. Data files
try:
    import pandas as pd

    ships = pd.read_csv(config.SHIPMENTS_CSV)
    notes = pd.read_csv(config.NOTES_CSV)
    header = config.SAMPLE_OUTPUT_CSV.read_text(encoding="utf-8").splitlines()[0]
    sample_cols = [c.strip() for c in header.split(",")]
    report("shipment_records.csv rows == 2940", len(ships) == 2940, str(len(ships)))
    report("context_notes.csv rows == 10", len(notes) == 10, str(len(notes)))
    report("output columns match sample header",
           sample_cols == config.OUTPUT_COLUMNS, str(sample_cols))
except Exception as e: 
    report("data files readable (put CSVs in data/)", False, str(e)[:150])

#Ollama chat model + determinism
try:
    import ollama

    def ask():
        r = ollama.chat(
            model=config.LLM_MODEL,
            messages=[{"role": "user",
                       "content": "Name three Indian cities, comma separated."}],
            options={**config.LLM_OPTIONS, "num_predict": 30},
        )
        return r["message"]["content"], r.get("prompt_eval_count"), r.get("eval_count")

    a, b = ask(), ask()
    report(f"LLM '{config.LLM_MODEL}' responds", bool(a[0].strip()), a[0].strip()[:60])
    report("LLM deterministic (2 identical runs)", a[0] == b[0])
    print(f"      token counts seen: input={a[1]}, output={a[2]}")
except Exception as e:
    report(f"LLM '{config.LLM_MODEL}'", False, str(e)[:150])

#llama embeddings
try:
    import ollama

    emb = ollama.embed(model=config.EMBED_MODEL, input=["freight cost test"])
    dim = len(emb["embeddings"][0])
    report(f"embeddings '{config.EMBED_MODEL}'", dim > 0, f"dimension={dim}")
except Exception as e:  
    report(f"embeddings '{config.EMBED_MODEL}'", False, str(e)[:150])

print("\nALL CHECKS PASSED" if all(results) else "\nSOME CHECKS FAILED - paste this output to me")  