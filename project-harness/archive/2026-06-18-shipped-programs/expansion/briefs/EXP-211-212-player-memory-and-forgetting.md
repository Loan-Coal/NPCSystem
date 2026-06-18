# EXP-211 + EXP-212 — Player-scoped memory recall + salience forgetting (one worker)

**Goal / rationale:** Memory is the headline moat, but it has no player-scoped recall and no
forgetting/salience curve. EXP-211 tags memories with the player they concern and surfaces them in that
player's dialogue context; EXP-212 makes low-salience memories decay while pinned ones persist. The
`memory.yaml` fields are ALREADY ADDED (DEC-097: `subject_player_id`, `recall_count`, `never_forget`) —
do NOT change the schema. These two items share `memory_engine.py` + `context_builder.py`, so they are
one worker.

**First slice (your scope):**
- **EXP-211:** when a memory is formed from a player interaction, populate `subject_player_id`; add a
  player-scoped recall path so a player's own memories surface in that player's dialogue context.
- **EXP-212:** compute a salience score from `recall_count` (+ emotional_charge/vividness already on the
  node); a memory is "forgettable" when salience < `MEMORY_FORGET_THRESHOLD` AND `never_forget` is false.
  Expose the salience/forget decision (a pure helper) — actual deletion/decay scheduling can be slice 2;
  this slice proves the computation + the player-scoped recall.

**Current state (verified):**
- `src/npc_engine/type_registry/base_nodes/memory.yaml` — now has `subject_player_id`, `recall_count`,
  `never_forget` (optional). Already applied; do not touch.
- `src/npc_engine/engines/memory/memory_engine.py` — memory formation lives here (e.g.
  `create_from_arousal`). Add `subject_player_id` population + a `compute_salience(...)` pure helper.
- `src/npc_engine/retrieval/context_builder.py` — assembles dialogue context. Add a player-scoped memory
  read (filter memories by `subject_player_id == player_id`). **This adds a new graph/memory call**: grep
  for the call site and MOCK it in EVERY context test file that drives `build_serialized_context`
  (`tests/unit/test_context_builder.py`, `test_player_relation_context.py`,
  `test_context_metrics_observability_v14.py`) — the gate WILL fail otherwise (this happened in cycle 2).
- `src/npc_engine/graph/` — if a player-scoped memory query doesn't exist, add a reader function here
  (graph layer); name it and keep it pure.

**Files:**
- EDIT `src/npc_engine/engines/memory/memory_engine.py` — `subject_player_id` population + `compute_salience`.
- EDIT `src/npc_engine/retrieval/context_builder.py` — player-scoped memory item (optional Tier-B/A as
  fits; keep `build_serialized_context` ≤40 lines — extract a helper, do NOT inline a block that tips it
  over, per the cycle-2/3 R006 lesson).
- POSSIBLY NEW `src/npc_engine/graph/<memory player-scoped reader>.py` or extend an existing memory reader.
- `config.py` — add `MEMORY_FORGET_THRESHOLD` named constant.
- Tests: `tests/unit/test_memory_engine.py` (salience + subject_player_id), context-builder test update
  + the 3 mocks above.

**Graph/API surface:** engine + retrieval + graph internal. No schema change (fields exist). No route.

**Architecture fit:** closed-edit (memory_engine, context_builder) + optional new graph reader. DEC-097
covers the fields. Layers: engines→graph, retrieval→graph (allowed). No LLM in retrieval/graph.

**Test plan (RED first):** (1) `test_memory_tagged_with_subject_player_id`; (2)
`test_player_scoped_memory_in_context` (mock the player-scoped reader → memory surfaces for that player,
absent for another); (3) `test_compute_salience_forgettable_below_threshold` +
`test_never_forget_memory_not_forgettable`. Watch each fail, implement.
Run: `pytest tests/unit/test_memory_engine.py tests/unit/test_context_builder.py -q`.

**Done when:** player-specific memories surface in that player's context; salience/forget computation
respects `never_forget` + `MEMORY_FORGET_THRESHOLD`; all context test files mock the new call; functions
≤40 lines; gate-ready.
