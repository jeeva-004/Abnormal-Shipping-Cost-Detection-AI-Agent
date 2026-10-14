# Walkthrough guide

## Components: What and Why
| Component | What | Why |
|---|---|---|
| `metrics.py` | Weekly pooled cost per tonne-km, 8-week own baseline, peer baseline | Every flag depends on these numbers being exactly as defined |
| `flagging.py` | Rule: rising >= 7% AND (peers >= 20% OR own >= 15%) | Simple, explainable, deterministic |
| `notes.py` | LLM label per note + keyword check; regex dates and %; cached | Turns free text into facts the gate can verify; only 10 LLM calls |
| `retrieval.py` | Chroma vector search over notes, filtered by route and week | The RAG step; filters stop wrong-route or wrong-time notes |
| `gate.py` | Deterministic referee: scope, window, effect, market-wide, magnitude | Guarantees every "justified" is traceable to a note that applies |
| `reasons.py` | Template reasons from the verified note | Cannot hallucinate; identical every run |
| `pipeline.py` | End-to-end run + output validation | One entry point; broken output is blocked |
| `eval/` | Labeled checks, sample rows, 11 trap scenarios | Shows why the system can be trusted |
| `scripts/repro.py` | 3 uncached runs, hash comparison, token log | Proves reproducibility and cost with real measurements |

## 10-minute demo
1. **0:00 Problem (1 min).** Cost creeps up; decide if a rise is justified by a real note, else say "unexplained".
2. **1:00 Architecture (1.5 min).** Draw: numbers by code, LLM only labels 10 notes, gate decides, template writes.
3. **2:30 Live run (1.5 min).** `python run.py`, then open `output\results.csv`: 13 rows, 3 justified, 10 flagged.
4. **4:00 Guardrails (2.5 min).** Show three rows:
   - Ahmedabad-Mumbai 2025-01-20 justified by N002 (festival week).
   - Chennai-Bangalore 2025-03-03 justified (N001) versus 2025-03-10 unexplained: the flood window ended Mar 8 and N009 says it is back to normal.
   - Mumbai-Pune Dec 2025: +39% above similar routes and no note, so unexplained.
5. **6:30 Trust (1.5 min).** `python eval\run_eval.py`: point to the sample-row matches and the trap scenarios.
6. **8:00 Repro and cost (1 min).** Show `output\repro_report.md` (3 identical hashes) and `output\cost_log.md`.
7. **9:00 Limits (1 min).** Thresholds tuned on the same data; N010 (LLM 9/10) was caught by the keyword layer; Q&A not built.

Before the demo: `python -m pytest tests -v` (37 pass) and `python run.py` once so the cache is warm.

## Likely interview questions
- **Why not let the LLM write the explanations?** A small model can invent causes. Templates only restate a verified note, so nothing is fabricated, and the reasons are identical every run.
- **Where is the LLM actually used?** Ten calls to label notes (does this say costs rose?). Numbers, flags, and verdicts are code.
- **Why a vector database for 10 notes?** The brief suggests retrieval and it scales to many notes. Metadata filters do the safety work; similarity only ranks. For 10 notes plain filtering would also work, and I say so.
- **What if the LLM is wrong?** A keyword check must agree before a note can justify anything. It caught N010. A wrong label can only make a row unexplained, not falsely justified.
- **How did you choose the thresholds?** From the distribution of weekly changes, then confirmed that the 13 candidates are unchanged across a range of values. Tuned on the same data, which I list as a limitation.
- **Why use the 8-week cap on N003?** An open-ended note would otherwise justify Mumbai-Pune's Sep-Dec creep. After 8 weeks the own-history baseline has absorbed the shift.
- **Why pooled cost and not average of ratios?** Averaging per-shipment ratios overweights small shipments; sum cost over sum tonne-km is the true route cost.
- **Why is the May diesel rise not flagged?** Every route rose together, so no route stands out against similar routes.
- **How do you know it is reproducible?** Three runs, LLM and embeddings re-called each time, byte-identical files. Temperature 0, seed 42.
- **What would you change with more time?** Held-out data for thresholds, a larger model for note labels, rolling window per route for peer gap, and the plain-English Q&A.
- **What does one run cost?** 10 LLM calls, about 2k LLM tokens; local so no charge. Calls scale with notes, not shipments.
- **A grader says a justified row is wrong. What do you check?** The reason text names the note id and window; open `context_notes.csv`, confirm the route, dates and wording. The gate's rejection codes explain any other candidate.