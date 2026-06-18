# EXP-229 — Long-horizon covert scheming engine (slice 1, DEC-104)

**Goal / rationale:** The flagship emergent-drama capability: an NPC pursues a multi-step covert goal
(a "scheme") across ticks — the capstone that differentiates from every LLM-bolt-on. The `scheme` node +
`EXECUTES_SCHEME` + `SCHEME_STEP` edges are ALREADY ADDED (DEC-104) — do NOT change the schema. Serves
BUSINESS_INTENT "emergent social drama."

**First slice (your scope — keep SMALL; XL overall, slice-1 is the spine):** A new `engines/scheming/`
engine + a graph write/read path that: (1) forms a scheme (a `scheme` node + `EXECUTES_SCHEME` edge from
the NPC, capped at `MAX_ACTIVE_SCHEMES_PER_NPC`), and (2) advances ONE scheme step (a `SCHEME_STEP` edge /
status update). **Detection** (other NPCs discovering schemes via the graveyard `investigation` engine) is
DEFERRED to slice 2 — do NOT revive `investigation` this slice. Keep derivation simple.

**Current state (verified):**
- `src/npc_engine/type_registry/base_nodes/scheme.yaml` — fields: id, npc_id, goal, status (optional),
  created_at_game_time (optional). `base_edges/executes_scheme.yaml` — `EXECUTES_SCHEME: character →
  scheme`. `base_edges/scheme_step.yaml` — `SCHEME_STEP: scheme → event`. All applied; do NOT touch.
- Model the graph writer on `graph/player_model_writer.py` (EXP-226) or `graph/relation_phase_writer.py`
  — raw Cypher MERGE/SET, no engine import in graph.
- Add `MAX_ACTIVE_SCHEMES_PER_NPC: int` to `config.py` (Settings field, default 2) — name it; no magic
  numbers. The engine enforces the cap (count active EXECUTES_SCHEME edges before forming a new scheme).

**Files:**
- NEW `src/npc_engine/engines/scheming/scheming_engine.py` + `__init__.py` (both with `Does NOT:` +
  `Dependencies injected:` docstring lines) — `SchemingEngine` with `form_scheme(...)` (respects the cap)
  and `advance_step(...)`; typed Pydantic models (Scheme, SchemeStep).
- NEW `src/npc_engine/graph/scheme_writer.py` — MERGE the `scheme` node + `EXECUTES_SCHEME` edge; add a
  `SCHEME_STEP` edge / status update; a reader `get_active_schemes(session, npc_id)` for the cap check.
  Graph layer; docstring contract.
- EDIT `src/npc_engine/config.py` — `MAX_ACTIVE_SCHEMES_PER_NPC` Settings field (default 2).
- NEW tests: `tests/unit/test_scheming_engine.py` (forms a scheme; cap blocks the 3rd active; advances a
  step) + `tests/unit/test_scheme_writer.py` (Cypher targets `scheme` node + `EXECUTES_SCHEME`/`SCHEME_STEP`).

**Graph/API surface:** engine + graph internal (no route this slice). Uses the new node/edges — no schema change.

**Architecture fit:** new-file engine + graph writer; engine→graph (no LLM in graph). No composition-root
wiring this slice (scheduler wiring + detection = slice 2). NO `from src` imports.

**Test plan (RED first):** `test_form_scheme_persists_node_and_edge`, `test_cap_blocks_excess_schemes`,
`test_advance_step`. Watch fail, implement. Run: `pytest tests/unit/test_scheming_engine.py tests/unit/test_scheme_writer.py -q`.

**Done when:** an NPC can form a capped scheme and advance one step, persisted via the new node/edges;
unit tests pass; no schema change; new files carry the docstring contract; functions ≤40 lines; no
`from src` imports; detection deferred to slice 2.
