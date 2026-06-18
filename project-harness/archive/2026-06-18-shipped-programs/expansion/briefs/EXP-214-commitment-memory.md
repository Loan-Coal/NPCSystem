# EXP-214 — Commitment/fact memory formation (DEC-100 `Memory.kind`)

**Goal / rationale:** Memories only form from arousal spikes, so a quietly-made promise ("I'll pay you
next week") is never remembered. Forming a `commitment` memory when the player and NPC agree to something
makes NPCs hold the player to their word. The `memory.yaml` `kind` field is ALREADY ADDED (DEC-100) — do
NOT change the schema.

**First slice (your scope):** A `MemoryEngine.create_from_commitment(...)` path that writes a memory with
`kind="commitment"`, plus one call site (quest accept) that forms it. Keep it small.

**Current state (verified):**
- `src/npc_engine/type_registry/base_nodes/memory.yaml` — now has `kind` (optional; values
  episodic|commitment|fact, null=episodic). Applied; do not touch.
- `src/npc_engine/engines/memory/memory_engine.py` — has `create_from_arousal`. Add
  `create_from_commitment(...)` that writes a memory with `kind="commitment"` (reuse the existing graph
  memory writer; pass `kind` through — the writer already accepts the new fields after EXP-211/212).
  Name the `kind` values as a `Literal`/enum or module constants (no raw strings).
- A call site: `src/npc_engine/engines/quest/quest_lifecycle_engine.py` (on quest accept) is the natural
  trigger. Add a single call to form a commitment memory when a quest is accepted.

**Files:**
- EDIT `src/npc_engine/engines/memory/memory_engine.py` — `create_from_commitment` (≤40 lines).
- EDIT `src/npc_engine/engines/quest/quest_lifecycle_engine.py` — one additive call site on accept.
- POSSIBLY EDIT `src/npc_engine/graph/memory_service.py`/`memory_queries.py` — only if the writer doesn't
  already accept `kind`; pass it through (it already takes `subject_player_id` after EXP-211).
- **IF you touch `context_builder.py`** (e.g. to surface commitment memories): do NOT let
  `build_serialized_context` exceed 40 lines — extract a 1-line helper (see `_maybe_append_top_need`/
  `_maybe_append_player_memory`), and mock any new graph call in ALL 3 context test files
  (test_context_builder, test_player_relation_context, test_context_metrics_observability_v14). Prefer NOT
  touching context_builder this slice (just form the memory; recall is covered by EXP-211's path).
- Tests: `tests/unit/test_memory_engine.py` (commitment memory has kind="commitment") + a quest-accept test.
  If you change `create_memory`'s signature, add `**_kwargs` tolerance to its mocks in test_memory_service.py.

**Graph/API surface:** engine + graph internal. No schema change (field exists). No route.

**Architecture fit:** closed-edit (memory + quest engines). Layer engines→graph. No schema.

**Test plan (RED first):** `test_create_from_commitment_sets_kind` + `test_quest_accept_forms_commitment_memory`.
Watch fail, implement. Run: `pytest tests/unit/test_memory_engine.py tests/unit/test_quest_lifecycle_engine.py -q`.

**Done when:** accepting a quest forms a `kind="commitment"` memory; tests pass; no schema change; any new
graph call mocked in all driving test files; `build_serialized_context` stays ≤40 lines.
