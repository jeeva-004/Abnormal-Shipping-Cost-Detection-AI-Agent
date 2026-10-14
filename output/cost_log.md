# Token and cost log (one full run over all 2,940 shipments, no cache)

| Item | Count |
|---|---|
| LLM calls | 10 |
| LLM input tokens | 1986 |
| LLM output tokens | 86 |
| Embedding calls | 14 |
| Embedding input tokens | 550 |
| Total tokens | 2622 |

Model: `qwen2.5:1.5b` (chat) and `nomic-embed-text` (embeddings), both run locally via Ollama.

- Actual cost: no per-token charge for local models (compute only: your own machine).
- Illustration only: at an *assumed* hosted rate of $0.1/1M tokens (not a published Qwen price; replace with your provider's rate) this run would cost about $0.00026.
- LLM calls scale with the number of notes (10), not with shipments (2,940), route-weeks (728) or flagged rows (13).
