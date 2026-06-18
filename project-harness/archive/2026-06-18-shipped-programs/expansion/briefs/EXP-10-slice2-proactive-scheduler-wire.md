# EXP-10 slice-2 — Proactive Dialogue: graph adapters + tick-scheduler wire

**Goal / rationale:** EXP-10 slice-1 built `ProactiveDialogueEngine` with two Protocol stubs
(`MemoryServiceProtocol`, `LocationServiceProtocol`) but left both unimplemented.  Slice-2
implements the real graph adapters and wires the engine into the tick scheduler so it fires
every tick. Business intent: agentic NPCs that hail idle players (Phase 14).

**Prerequisite:** EXP-10 slice-1 merged ✅ (`engines/proactive_dialogue/` exists).

---

## First slice (worker scope)

1. `graph/proactive_memory_reader.py` — `ProactiveMemoryReader` implementing
   `MemoryServiceProtocol`: Cypher over `REMEMBERS` edges, ordered vividness DESC, limit `k`.
   **Schema waiver:** `memory.yaml` has no `shared` field; return `shared: False` for every
   memory in this slice.  Document in the module docstring as a known limitation.
2. `graph/player_location_reader.py` — `PlayerLocationReader` implementing
   `LocationServiceProtocol` + a `get_collocated_pairs(session) → list[tuple[str,str]]` helper:
   - `get_player_idle_ticks()` — Cypher: match `(player {is_player:true})-[r:LOCATED_AT]->(loc)<-[:LOCATED_AT]-(npc {id:$npc_id})`; return `tick_id - r.arrived_at_tick` (0 if no edge or no `arrived_at_tick`).
   - `get_collocated_pairs(session)` — Cypher: match all (npc, player) pairs at same location; return `[(npc_id, player_id), ...]`.
3. `engines/proactive_dialogue/proactive_tick_adapter.py` — `ProactiveDialogueTick` with
   `run_tick(session, tick_id) → dict`:
   - calls `get_collocated_pairs(session)` to get candidate pairs
   - for each pair: `engine.check_trigger()` → if trigger → `engine.generate_line()`
   - returns `{"proactive_lines": [line.model_dump() ...]}`
   - cap pairs to `MAX_PROACTIVE_CHECKS_PER_TICK = 20` (config constant, not magic number)
4. EDIT `tick_scheduler.py` — add `proactive_dialogue_engine: BaseEngine | None = None` kwarg
   following the `world_state_quest_trigger` pattern (lines 82–84).  Add `"proactive_dialogue"` to
   the `response` dict; call in the tick loop with `_run_engine_safe`.
5. EDIT `dependencies_engines.py` — add `get_proactive_dialogue_engine() → ProactiveDialogueTick`
   factory; wire into `get_tick_scheduler()`.

---

## Current state (verified)

- `src/npc_engine/engines/proactive_dialogue/proactive_engine.py:43–88` — `MemoryServiceProtocol` +
  `LocationServiceProtocol` already defined (both `runtime_checkable`).
- `src/npc_engine/type_registry/base_nodes/memory.yaml` — no `shared` field (waiver applies).
- `src/npc_engine/type_registry/base_edges/located_at.yaml:7` — `arrived_at_tick: {type: int, required: false}`.
- `src/npc_engine/type_registry/base_nodes/character.yaml:9` — `is_player: {type: bool, required: true}`.
- `src/npc_engine/scheduler/tick_scheduler.py:82–84` — `world_state_quest_trigger` pattern to follow exactly.
- `src/npc_engine/api/dependencies_engines.py:127–134` — `get_world_state_quest_trigger()` pattern to follow exactly.

---

## Files

**New:**
- `src/npc_engine/graph/proactive_memory_reader.py`
- `src/npc_engine/graph/player_location_reader.py`
- `src/npc_engine/engines/proactive_dialogue/proactive_tick_adapter.py`
- `tests/unit/test_proactive_memory_reader.py`
- `tests/unit/test_proactive_tick_adapter.py`

**Edited:**
- `src/npc_engine/scheduler/tick_scheduler.py`
- `src/npc_engine/api/dependencies_engines.py`

---

## Graph / API surface

No new HTTP route. No schema change.  Tick scheduler result dict gains `"proactive_dialogue"` key
(additive).  New graph queries use only existing `REMEMBERS`, `LOCATED_AT`, and `Character` nodes.

---

## Architecture fit

New-file-add graph adapters.  Tick adapter follows `ProactiveDialogueTick(engine, reader)` pattern
with constructor injection.  Graph queries stay in `graph/` layer (no Cypher in `engines/`).
`dependencies_engines.py` is the composition root — sole place that wires everything.

---

## Test plan

Write `tests/unit/test_proactive_memory_reader.py` and `tests/unit/test_proactive_tick_adapter.py`
FIRST.  Both mock all I/O (no DB, no LLM).

| Test | Asserts |
|------|---------|
| `test_memory_reader_returns_memories_sorted_vividness` | mocked session returns rows sorted by vividness DESC |
| `test_memory_reader_all_marked_unshared` | every returned memory has `shared: False` |
| `test_location_reader_computes_idle_ticks` | `arrived_at_tick=90, tick_id=95` → returns 5 |
| `test_location_reader_returns_zero_no_edge` | no `LOCATED_AT` edge → returns 0 |
| `test_tick_adapter_fires_on_trigger` | mock engine.check_trigger returns trigger → generate_line called |
| `test_tick_adapter_skips_on_no_trigger` | check_trigger returns None → generate_line NOT called |
| `test_tick_adapter_caps_pairs` | >MAX pairs → only first MAX checked |
| `test_tick_adapter_returns_empty_no_pairs` | no collocated pairs → `{"proactive_lines": []}` |

Run: `pytest tests/unit/test_proactive_memory_reader.py tests/unit/test_proactive_tick_adapter.py -q`

---

## Done when

- `pytest tests/unit/test_proactive_memory_reader.py tests/unit/test_proactive_tick_adapter.py` green.
- `ProactiveDialogueTick.run_tick(session, tick_id)` exists and is async.
- `tick_scheduler.py` accepts `proactive_dialogue_engine` kwarg; `"proactive_dialogue"` in response dict.
- `dependencies_engines.py` has `get_proactive_dialogue_engine()` and wires it into `get_tick_scheduler()`.
- No file > 300 lines.  All Cypher in `graph/` layer.  No schema file touched.
- Adjacent issues spotted: report them, do NOT fix.
