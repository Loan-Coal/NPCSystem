# EXP-31 — Retrieval-quality eval harness (precision@k / recall)

**Goal / rationale:** The full retrieval stack (embedding_index, cross_encoder_reranker, subgraph_retriever,
context_relevance_engine) exists but only dialogue *tone* is evaluated — retrieval quality is asserted, never
measured. Turn the buyer claim "retrieval returns the *right* memories" into a reported number
(precision@k / recall@k, **k=5, report-only, no SLA gate** per DEC/OQ-D2). Roadmap Phase 15.

**First slice (this worker's scope):** A labeled relevant-set fixture + an eval that, per query, retrieves the
ranked context-item IDs for an NPC and computes precision@5 / recall@5 / MRR against the labels, surfaced via a
`make eval-retrieval` target. Start with the **demo world** (`demo_game/seed.py` NPCs) — ~15-20 labeled queries.

**Current state (verify):**
- `evals/runner.py` (dialogue-only today), `evals/summary.py`, `evals/matchers.py`, `evals/cases/` — match the
  existing case/matcher conventions; the new set must be loadable by the same runner or a clearly-named sibling.
- Retrieval entry point: `src/npc_engine/retrieval/` — `embedding_index.search(...)`, `subgraph_retriever`,
  `context_builder`. The eval needs the **ranked context-item IDs** for `(npc_id, query)`. If no debug surface
  exists, call the retrieval path directly in-process from the eval (it's a test/eval harness, not a route) —
  do NOT add a production route in this slice (that's S15.1, separate).
- `grep -r "precision@|recall@|relevant_set"` → only an unrelated chapter hit; confirms greenfield.

**Files (all NEW → zero conflict):**
- NEW `evals/cases/retrieval_demo.json` (or `.yaml` matching existing cases) — `{id, npc_id, query, relevant_node_ids, k}`.
- NEW `evals/retrieval_runner.py` — loads the cases, runs retrieval per query, computes precision@k/recall@k/MRR.
- NEW `evals/retrieval_matchers.py` (or extend `matchers.py` ONLY if no other batch item touches it — else new file).
- EDIT `Makefile` — add `eval-retrieval` target. **Conflict note:** EXP-83 also edits `Makefile`; if both run in
  the same batch, sequence the Makefile edits or let the orchestrator add both target lines at fan-in.
- NEW `tests/unit/test_retrieval_eval.py` — unit-test the precision@k/recall@k math on a hand-built ranked list
  (no Neo4j/Ollama needed for the math test).

**Graph/API surface:** none (eval/test layer only).

**Architecture fit:** new eval files; zero engine edits. The metric functions are pure and unit-testable.

**Test plan (write FIRST):** `tests/unit/test_retrieval_eval.py` — feed `precision_at_k`/`recall_at_k`/`mrr` a known
ranked list + relevant-set and assert exact values (e.g. ranked `[a,b,c,d,e]`, relevant `{a,c}`, k=5 →
precision@5=0.4, recall@5=1.0, MRR=1.0). Run: `pytest tests/unit/test_retrieval_eval.py -q`.

**Done when:** the metric math is unit-green, and `make eval-retrieval` runs the demo-world cases end-to-end and
prints precision@5 / recall@5 (live retrieval, needs the stack up — that's the integration check, not the unit gate).
(Labeled-set authoring: see `expansion/EXP32_EVAL_QA_TASK.md` — Opus can generate the relevant-sets from the seed graph.)
