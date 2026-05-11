# Next Session Instructions

## Phase 3 — World Depth. Feature 3.2 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.1 as DONE (committed), add Feature 3.2 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1 ✅, 3.2 IN_PROGRESS.

---

## Feature 3.2 — Memories vs Knowledge

Read `project/ROADMAP.md` lines 416–454 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** NPCs currently have `KNOWS_ABOUT` edges to Event nodes (factual knowledge).
Feature 3.2 introduces a distinct `Memory` node type — personal, emotional, vivid — and the
`REMEMBERS` edge. Memories decay over game time (vividness drops). The dialogue context
builder will include top-K memories in Tier A. This is rules-based only; no LLM creation.

### Architecture decisions (read before coding)

- `Memory` is a first-class graph node with its own YAML in `type_registry/base_nodes/memory.yaml`.
- `REMEMBERS` and `ABOUT` are edges in `type_registry/base_edges/`.
- `graph/memory_service.py` handles all Neo4j writes for Memory nodes and edges. Layer: `graph/`.
- `graph/memory_queries.py` holds all Cypher strings for the memory service.
- `engines/memory/memory_engine.py` contains the high-arousal trigger logic.
  Layer: `engines/`. It calls `graph/memory_service.py`.
- Vividness decay: `advance_time` hook — on each `day` advance, call `memory_engine.decay_vividness()`
  which runs a Cypher batch update (`vividness = max(0, vividness - DECAY_PER_DAY)`).
- Dialogue retrieval: `retrieval/context_builder.py` Tier A section — add top-K memories
  query (sorted by `vividness * recency_score`). Reuse `retrieval/subgraph_retriever.py` pattern.
- `created_at_game_time` stores a JSON-encoded `TimePoint` (year/season/day/time_of_day).
  Use `world.time_utils.TimePoint` serialised via `common.json_utils.dump_json`.

### Steps

1. **Schema: `type_registry/base_nodes/memory.yaml`** (new):
   - Fields: `id`, `content` (str, embedded), `vividness` (int 0–100),
     `emotional_charge` (int -100–100), `created_at_game_time` (str/JSON), `last_recalled_at` (str/JSON).

2. **Schema: `type_registry/base_edges/remembers.yaml`** (new):
   - `(:Character)-[:REMEMBERS {since_game_time}]->(:Memory)`
   - `since_game_time`: str, JSON-encoded TimePoint.

3. **Schema: `type_registry/base_edges/about.yaml`** (new):
   - `(:Memory)-[:ABOUT]->(:Event)`
   - No extra properties.

4. **`graph/memory_queries.py`** (new, Cypher strings only):
   - `CYPHER_CREATE_MEMORY` — MERGE Memory node + REMEMBERS edge.
   - `CYPHER_GET_MEMORIES_FOR_CHARACTER` — ORDER BY `vividness DESC`, LIMIT $k.
   - `CYPHER_DECAY_VIVIDNESS` — `SET m.vividness = max(0, m.vividness - $decay)` batch.

5. **`graph/memory_service.py`** (new, ≤200 lines):
   - `create_memory(session, character_id, content, vividness, emotional_charge, game_time) -> str` — creates Memory node + REMEMBERS edge, returns memory ID.
   - `get_memories_for_character(session, character_id, k=5) -> list[dict]` — top-K by vividness.
   - `decay_all_vividness(session, decay_per_day=5) -> int` — batch update, returns affected count.

6. **`engines/memory/__init__.py`** and **`engines/memory/memory_engine.py`** (new, ≤150 lines):
   - `MemoryEngine` class with `create_from_arousal(session, character_id, arousal, content, game_time)`.
   - High-arousal threshold: `arousal > 70` triggers memory creation.
   - `decay_vividness(session)` calls `graph/memory_service.decay_all_vividness`.

7. **Dialogue hook** in `engines/dialogue/dialogue_handler.py`:
   - After emotion update, if `emotion_state.arousal > 70`, call `MemoryEngine.create_from_arousal`.
   - Pass current `WorldState` time fields as `game_time`.

8. **Retrieval hook** in `retrieval/context_builder.py`:
   - In Tier A assembly, call `memory_service.get_memories_for_character(session, character_id, k=3)`.
   - Serialise as a `memories` list in the context payload.

9. **Unit tests** `tests/unit/test_memory_service.py`:
   - `create_memory` happy path (mock session).
   - `get_memories_for_character` returns sorted list.
   - `decay_all_vividness` clamps to 0.
   - `MemoryEngine.create_from_arousal` creates memory when arousal > 70, skips when ≤ 70.

10. **E2E scenario** `e2e/scenarios/scenario_memory_formation.py`:
    - Seed character + dialogue session with high-arousal outcome.
    - Advance time_of_day to trigger arousal write.
    - Assert memory node exists for character.
    - Advance day and assert vividness has decayed.

### Definition of done (3.2)
- `Memory` node YAML + REMEMBERS + ABOUT edge YAMLs exist.
- `graph/memory_service.py` and `engines/memory/memory_engine.py` pass all unit tests.
- Dialogue handler creates memories on high-arousal moments.
- Context builder includes top-K memories in Tier A.
- E2E scenario `scenario_memory_formation.py` passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: memory nodes and formation (Phase 3.2)`

---

## After 3.2 is committed — update this file for Feature 3.3

When Feature 3.2 is committed and `pytest tests/ -q` is green, rewrite this file to target
Feature 3.3 — Memory Consolidation Engine.

Read `project/ROADMAP.md` lines 456–479 before writing 3.3 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3.2 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.2, log a new ISSUES.md entry describing the blocking scenario
and get approval before fixing.
