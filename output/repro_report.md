# Reproducibility report

Three consecutive runs on the same input, each with `--no-cache` (all LLM and embedding calls repeated).

| Run | results.csv SHA-256 | weekly_metrics.csv SHA-256 | LLM calls |
|---|---|---|---|
| 1 | `5e0ae05eb490fbbedc9e7a7e372f671917cb10258cda7a2178e4d10b6ffc4ab9` | `c7748dcce27799d4a0bd7fd5446abe13c49ecfbe822ad4b392d6504e45869501` | 10 |
| 2 | `5e0ae05eb490fbbedc9e7a7e372f671917cb10258cda7a2178e4d10b6ffc4ab9` | `c7748dcce27799d4a0bd7fd5446abe13c49ecfbe822ad4b392d6504e45869501` | 10 |
| 3 | `5e0ae05eb490fbbedc9e7a7e372f671917cb10258cda7a2178e4d10b6ffc4ab9` | `c7748dcce27799d4a0bd7fd5446abe13c49ecfbe822ad4b392d6504e45869501` | 10 |

Result: results.csv identical = **YES**, weekly_metrics.csv identical = **YES**.

Randomness controls: LLM options {'temperature': 0, 'seed': 42, 'top_k': 1} (temperature 0, fixed seed, greedy top_k=1) so the model always picks its most likely token.
All numbers, flags, gate decisions and reason text are deterministic code; the LLM only labels 10 notes, and a keyword check must agree with it before any note can justify a row.
