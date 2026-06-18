# EXP-228 — NPC deception / false-belief engine (slice 1, DEC-103)

**Goal / rationale:** NPCs can only hold true beliefs. Letting an NPC plant a *deliberate* false belief
(it knows X is false but states X to advance a goal) is the foundation of intrigue — and a hard
differentiator. The `believes.yaml` `is_deception` + `deception_goal_id` fields are ALREADY ADDED
(DEC-103) — do NOT change the schema. Serves BUSINESS_INTENT "emergent social drama."

**First slice (your scope):** A new `engines/deception/` engine + a graph write path that records a
deception belief: a `BELIEVES` edge with `is_deception=true` and a `deception_goal_id`. **Critical
coupling:** the anti-hallucination eval must treat an intended deception as *correct behavior*, not a
guard failure — wire that distinction in this slice (see below). Keep derivation simple.

**Current state (verified):**
- `src/npc_engine/type_registry/base_edges/believes.yaml` — now has `is_deception` (bool, optional) +
  `deception_goal_id` (str, optional). Applied; do NOT touch.
- Belief writes go through an existing path (e.g. `graph/belief_queries.py` `write_belief`, used by
  `engines/knowledge_learning/knowledge_extraction_engine.py`). Add a deception write that sets the two
  new fields — either extend the existing writer with optional `is_deception`/`deception_goal_id` kwargs
  (back-compat default false/None — if you change its signature, add `**_kwargs` tolerance to its test
  mocks) OR add a dedicated `write_deception_belief` reader/writer. Prefer the additive-kwarg approach.
- **Anti-hallucination eval coupling:** find where the anti-hallucination eval classifies a stated fact
  as a hallucination (under `evals/` — e.g. `anti_hallucination_runner.py` / its judge). Add a carve-out
  so a belief flagged `is_deception=true` is treated as *intended* (not a guard failure). If the eval is
  data-driven (cases JSON), the carve-out may be a runner-side check that skips/accepts deception-flagged
  beliefs. Keep this minimal and well-tested; do NOT weaken the guard for non-deception cases.

**Files:**
- NEW `src/npc_engine/engines/deception/deception_engine.py` + `__init__.py` (both with `Does NOT:` +
  `Dependencies injected:` docstring lines) — a `DeceptionEngine` that, given a goal + a target belief,
  produces a `DeceptionBelief` (Pydantic v2) and persists it via the graph write path with
  `is_deception=true`, `deception_goal_id=<goal>`.
- EDIT `src/npc_engine/graph/belief_queries.py` — additive `is_deception`/`deception_goal_id` kwargs on the
  belief writer (back-compat); if signature changes, add `**_kwargs` to its mocks in any driving test.
- EDIT the anti-hallucination eval runner/judge under `evals/` — the deception carve-out (minimal).
- NEW tests: `tests/unit/test_deception_engine.py` (deception belief carries is_deception=true +
  goal id) + an eval-side test that an `is_deception=true` belief is NOT counted as a hallucination
  failure while a normal unsupported claim still is.

**Graph/API surface:** engine + graph internal + eval-layer. No schema change (fields exist). No route this slice.

**Architecture fit:** new-file engine + additive graph-writer kwargs + minimal eval carve-out. Layer
engines→graph (no LLM in graph). No schema. NO `from src` imports.

**Test plan (RED first):** `test_deception_belief_sets_flags` + `test_eval_accepts_is_deception_belief`
+ `test_eval_still_flags_plain_hallucination`. Watch fail, implement.
Run: `pytest tests/unit/test_deception_engine.py -q` (+ the relevant eval test).

**Done when:** an NPC can persist a flagged deliberate false belief; the anti-hallucination eval treats
`is_deception=true` as intended (without weakening the guard for ordinary claims); tests pass; no schema
change; new files carry the docstring contract; functions ≤40 lines.
