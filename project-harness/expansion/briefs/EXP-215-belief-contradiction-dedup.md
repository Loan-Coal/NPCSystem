# EXP-215 — Belief contradiction detection + dedup

**Goal / rationale:** NPCs learn beliefs from the player (`knowledge_learning`), but with no dedup or
contradiction check the belief graph accumulates duplicates and conflicting facts. Detecting a
contradiction before writing keeps learned knowledge coherent. Serves BUSINESS_INTENT "NPCs that learn."

**First slice (your scope):** A graph reader that finds an existing belief contradicting/duplicating a
candidate, called by `KnowledgeExtractionEngine` before it writes — so a contradictory/duplicate belief
is flagged (skipped or merged) rather than blindly added.

**Current state (verified):**
- `src/npc_engine/engines/knowledge_learning/knowledge_extraction_engine.py:56` — docstring states "No
  deduplication or contradiction detection in this slice." Find the write path (`process()` or similar)
  and insert a pre-write check.
- `src/npc_engine/graph/` — belief readers exist (e.g. `belief_queries.py`). Add a reader that, given a
  character + candidate belief content/subject, returns an existing belief that duplicates or contradicts
  it (simple content/subject match this slice — semantic contradiction can be slice 2).

**Files:**
- NEW or EXTEND `src/npc_engine/graph/belief_queries.py` — `async find_conflicting_belief(session,
  character_id, candidate) -> existing | None` (graph layer; module docstring `Does NOT:`/`Dependencies
  injected:`).
- EDIT `src/npc_engine/engines/knowledge_learning/knowledge_extraction_engine.py` — before writing a
  learned belief, call the reader; if a duplicate/contradiction exists, skip-or-merge (this slice: skip
  the write + log the decision; keep ≤40-line functions, extract a helper if needed).
- NEW/EXTEND test: `tests/unit/test_knowledge_extraction_engine.py` — duplicate not re-written;
  non-conflicting belief still written.

**Graph/API surface:** engine + graph internal. No schema change (use existing belief schema). No route.

**Architecture fit:** closed-edit (engine) + graph reader add. Layer engines→graph (allowed); no LLM in
graph. No schema.

**Test plan (RED first):** mock the reader to return an existing belief → assert the engine does NOT write
a duplicate; mock it to return None → assert it writes. Watch fail, implement.
Run: `pytest tests/unit/test_knowledge_extraction_engine.py -q`.

**Done when:** a contradicting/duplicate learned belief is detected pre-write and skipped (logged);
non-conflicting beliefs still write; tests pass; no schema change.
