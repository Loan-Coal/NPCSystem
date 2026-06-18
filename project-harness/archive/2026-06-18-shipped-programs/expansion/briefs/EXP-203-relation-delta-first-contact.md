# EXP-203 — Relation-delta first-contact fix

**Goal / rationale:** The very first relationship signal between an NPC and player is currently
**swallowed**: if no `RELATES_TO` edge exists yet, the delta write raises `RelationEdgeNotFoundError`,
which is caught and only logged — the relationship never forms. Fixing it is correctness (CLAUDE.md
"never swallow errors") and makes first impressions actually register.

**First slice (your scope):** On `RelationEdgeNotFoundError`, **create** the `RELATES_TO` edge with
baseline values, then apply the delta — instead of logging and dropping it. Regression test first.

**Current state (verified):**
- `src/npc_engine/engines/dialogue/relation_mutator.py:42-54` — `_write_delta` calls
  `apply_relation_delta(...)`; the `except RelationEdgeNotFoundError:` branch (line 53-54) only does
  `_LOGGER.warning("relation_edge_missing", ...)` and returns. This is the bug.
- `apply_relation_delta` lives in `src/npc_engine/graph/graph_writer.py`. Look there for an existing
  create/ensure `RELATES_TO` helper; if one exists, reuse it. If not, add a minimal
  `ensure_relation_edge(session, src_id, dst_id, baseline)` in `graph_writer.py` (graph layer) — this is
  the only existing file you may edit besides `relation_mutator.py`. **Do NOT change the edge schema**
  (`relates_to.yaml`); use the existing required fields' defaults for baseline (trust/fear/affection/
  interaction_count = 0, relevance_score = 0.0, last_updated_at = now, etc. — match the schema).

**Files:**
- EDIT `src/npc_engine/engines/dialogue/relation_mutator.py` — in the except branch, ensure the edge
  then re-apply the delta (extract a `≤40`-line helper if needed; keep nesting ≤3).
- POSSIBLY EDIT `src/npc_engine/graph/graph_writer.py` — only if no ensure/create helper exists.
- NEW test: `tests/unit/test_relation_mutator.py` (or extend if present) —
  `test_first_contact_creates_edge_and_applies_delta`.

**Graph/API surface:** engine + graph internal. No new node/edge type, no schema change, no route.

**Architecture fit:** closed-edit to one engine file (single-module bug fix — allowed) + optional graph
helper add. No layer change. `graph_writer.py` remains the only transaction owner.

**Test plan (RED first):** mock `apply_relation_delta` to raise `RelationEdgeNotFoundError` on first
call then succeed; assert the ensure-edge path is taken and the delta is applied (not swallowed). Watch
it fail against current code, then implement. Run: `pytest tests/unit/test_relation_mutator.py -q`.

**Done when:** first-contact delta persists (edge created + delta applied); regression test passes; no
swallowed error remains; no schema change.
