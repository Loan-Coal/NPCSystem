# EXP-230 — Session history persisted across restart (slice 1)

**Goal / rationale:** Dialogue session history lives only in memory, so a server restart wipes every
conversation — breaking the "persistent NPCs" promise across restarts. Persisting session turns to the
graph lets conversations survive a restart. Per OQ-9 the storage model is a `SESSION_TURNS` node (no new
type_registry node needed if you store turns as a JSON blob on an existing per-(npc,player) anchor — see
below). No schema YAML change in this slice.

**First slice (your scope):** Add `save_to_graph()` / `load_from_graph()` to `SessionStore` and call them
from the app lifespan (save on shutdown, load on startup) so a session survives a restart. Keep storage
simple: persist the last-N turns per (npc_id, player_id) as a serialized blob on the Character node (or a
lightweight dedicated write) — do NOT add a new type_registry node type this slice (avoid schema churn);
if a dedicated node is truly needed, STOP and report rather than adding schema.

**Current state (verified):**
- `src/npc_engine/engines/dialogue/session_store.py` — its docstring states "Does NOT: persist sessions
  across process restarts." Add `save_to_graph(session, ...)` + `load_from_graph(session, ...)` (or a
  graph helper it calls). Wrap shared-state mutation in the existing `asyncio.Lock` (session_store is
  lock-guarded per CLAUDE.md).
- App lifespan: `src/npc_engine/main.py` (the lifespan startup/shutdown where other stores bootstrap,
  e.g. `EmotionBootstrapper`). Add a load on startup + a save on shutdown. Keep it best-effort (a graph
  outage on save must not crash shutdown — log and continue).
- Graph write/read for the blob goes in `graph/` (a small writer/reader), not in the store directly if it
  keeps the layer clean. Cap the persisted turns (named constant).

**Files:**
- EDIT `src/npc_engine/engines/dialogue/session_store.py` — `save_to_graph`/`load_from_graph` (lock-guarded;
  ≤40-line functions).
- NEW or EXTEND a `graph/` reader/writer for the session blob (if needed) with the docstring contract.
- EDIT `src/npc_engine/main.py` (or the lifespan module) — load on startup, save on shutdown (best-effort).
- `config.py` — `MAX_PERSISTED_SESSION_TURNS` named constant if you cap (no magic numbers).
- NEW tests: `tests/unit/test_session_store_persistence.py` — round-trip (save then load restores turns);
  a graph-error on save is swallowed-and-logged (does not raise).

**Graph/API surface:** engine + graph internal + lifespan. No type_registry schema change this slice. No route.

**Architecture fit:** closed-edit (session_store + lifespan) + optional graph helper. Layer engines→graph
(no LLM). Lock-guarded shared state. NO `from src` imports.

**Test plan (RED first):** `test_session_round_trip_via_graph` (save → load restores the turns) +
`test_save_swallows_graph_error`. Watch fail, implement. Run: `pytest tests/unit/test_session_store_persistence.py -q`.

**Done when:** a dialogue session's turns survive a save/load round-trip via the graph and are restored on
startup; save is best-effort (errors logged, not raised); tests pass; no type_registry schema change; new
files carry the docstring contract; functions ≤40 lines; no `from src` imports.
