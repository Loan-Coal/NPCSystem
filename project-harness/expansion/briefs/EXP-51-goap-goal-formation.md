# EXP-51: NPC Goal-Formation & Action-Selection (lightweight GOAP) — slice 1

**Goal / business rationale**
Give NPCs autonomous intent: a per-tick engine that reads unmet `Need` nodes,
forms a `PURSUES` goal with urgency proportional to deprivation, and dispatches
a move-to-location action — the first "agentic, not just reactive" loop.
Traces to BUSINESS_INTENT §3 "agentic NPCs that initiate" and the `goal`/`PURSUES`
schema that has existed since Phase 0 but has never been driven by engine code.
DEC-083 approved `GOAL_TARGETS` edge + the 0-100 action priority system.

**First slice**
One goal type only: "satisfy most-decayed need."
1. New `GOAL_TARGETS` base edge (DEC-083).
2. New `engines/planning/` package: `action_priority.py` (constants), `goal_former.py`
   (reads needs, writes PURSUES + GOAL_TARGETS), `action_selector.py` (scores actions,
   dispatches move via existing `routine_queries.update_character_location`).
3. Planning engine runs AFTER routine in the tick scheduler, overrides only when
   `goal.urgency > ROUTINE_PRIORITY (50)`.
4. Unit test + one integration smoke test (mocked graph).

---

## Current state (verified against codebase)

| Location | What's there |
|---|---|
| `src/npc_engine/type_registry/base_nodes/goal.yaml` | `goal` node — `id, description, urgency (0-100), status, created_at_game_time, target_id (optional str)` |
| `src/npc_engine/type_registry/base_edges/pursues.yaml` | `PURSUES` edge — `character → goal`, no fields |
| `src/npc_engine/type_registry/base_nodes/need.yaml` | `Need` node — `id, kind, level (0-100), decay_rate, character_id` |
| `src/npc_engine/type_registry/base_edges/satisfies_need.yaml` | `SATISFIES_NEED` — `[location, item] → need`, field `magnitude` |
| `src/npc_engine/graph/goal_service.py:28` | `create_goal(session, character_id, description, urgency, game_time, target_id, node_id)` — MERGE semantics, stable-id safe |
| `src/npc_engine/graph/goal_queries.py` | `CYPHER_CREATE_GOAL`, `CYPHER_UPDATE_GOAL_STATUS`, `get_goals_for_character` |
| `src/npc_engine/graph/need_queries.py` | `get_needs_for_character` exists |
| `src/npc_engine/engines/routine/routine_engine.py:43` | `RoutineEngine.run_tick(session, time_of_day, npc_ids)` — calls `update_character_location` from `routine_queries` |
| `src/npc_engine/engines/routine/routine_queries.py` | `update_character_location(session, npc_id, new_location_id)` — reusable by planning engine |
| `src/npc_engine/scheduler/tick_scheduler.py` | Tick orchestrator — dispatch order for engines |
| `goal.target_id` field | Deprecated in favor of GOAL_TARGETS edge per DEC-083; leave in place |

---

## Files

**New base schema (one file):**
- `src/npc_engine/type_registry/base_edges/goal_targets.yaml`

```yaml
edge_type: GOAL_TARGETS
src_type: goal
dst_type: [character, location, faction, item]
fields:
  priority:
    type: int
    required: true
    range: [0, 100]
```

**New engine package (four files):**
- `src/npc_engine/engines/planning/__init__.py` — package docstring only
- `src/npc_engine/engines/planning/action_priority.py` — named integer constants:
  `ROUTINE_PRIORITY = 50`, `GOAL_CRITICAL = 90`, `GOAL_HIGH = 75`,
  `GOAL_NORMAL = 50`, `GOAL_LOW = 25`. No logic — pure constants module.
- `src/npc_engine/engines/planning/goal_former.py` — `GoalFormer` class:
  reads NPC needs via `need_queries`, identifies most-decayed need (lowest `level`),
  computes urgency = `min(100, 100 - need.level)`, creates goal via `goal_service.create_goal`,
  creates `GOAL_TARGETS` edge to the satisfying location.
- `src/npc_engine/engines/planning/action_selector.py` — `ActionSelector` class:
  given a character's active goals, picks the highest-urgency one, retrieves its
  `GOAL_TARGETS` location, compares urgency to `ROUTINE_PRIORITY`.
  If `urgency > ROUTINE_PRIORITY`: dispatch move via `update_character_location`.
  If `urgency <= ROUTINE_PRIORITY`: no-op (routine has already moved the NPC).

**New graph support (one file):**
- `src/npc_engine/graph/goal_targets_writer.py` — `create_goal_targets_edge(session, goal_id, target_id, priority)` using MERGE Cypher.

**New tests (two files):**
- `tests/unit/test_goal_former.py` — mock `need_queries`, `goal_service`; assert goal created with correct urgency; assert GOAL_TARGETS edge created with correct target.
- `tests/unit/test_action_selector.py` — assert high-urgency goal (>50) triggers `update_character_location`; assert low-urgency goal does not.

**No edits to tick_scheduler.py** — the planning engine is wired in slice-2 when it is ready to compete in the scheduler. Slice-1 tests in isolation.

---

## Graph / API surface

No new route. No new node type. One new edge type.

Example post-slice graph state for an NPC with social need at level 10:
```
(character) -[:PURSUES]-> (goal {urgency:90, description:"satisfy social need"})
                               -[:GOAL_TARGETS {priority:90}]-> (location:tavern)
```

---

## Architecture fit

OCP add-by-new-file: `planning/` is a new engine package. `goal_targets_writer.py` is a new graph module.
`action_priority.py` is a new constants module — no existing engine is edited.
`goal_former.py` calls `goal_service.create_goal` (existing seam, already MERGE-safe).
`action_selector.py` calls `routine_queries.update_character_location` (existing seam).
No LLM calls (LLM is optional for intent phrasing — slice-2). No Neo4j queries outside `graph/`.
Layer: `engines/planning` → `graph/`, `retrieval/` (for need reads), `config`, `utils`. Compliant.
DECISIONS: DEC-083 covers `GOAL_TARGETS` edge and priority system.

---

## Test plan

Write `tests/unit/test_goal_former.py` **first** (failing):

```python
# test 1 — most-decayed need selected
async def test_forms_goal_for_lowest_level_need():
    # mock get_needs_for_character → [Need(level=20), Need(level=80)]
    # assert create_goal called with urgency=80 (100-20)

# test 2 — urgency clamped at 100
async def test_urgency_clamped_when_need_at_zero():
    # Need(level=0) → urgency = 100 (not 101+)

# test 3 — GOAL_TARGETS edge written to correct location
async def test_goal_targets_edge_points_to_satisfying_location():
    # mock satisfies_need query → returns location "tavern"
    # assert create_goal_targets_edge called with target_id="tavern"
```

Write `tests/unit/test_action_selector.py` **first** (failing):

```python
# test 4 — high-urgency goal triggers move
async def test_high_urgency_goal_overrides_routine():
    # goal.urgency=90 > ROUTINE_PRIORITY=50 → update_character_location called

# test 5 — low-urgency goal does not trigger move
async def test_low_urgency_goal_defers_to_routine():
    # goal.urgency=30 <= ROUTINE_PRIORITY → update_character_location NOT called
```

Run: `pytest tests/unit/test_goal_former.py tests/unit/test_action_selector.py -v`

---

## Done when

- `pytest tests/unit/test_goal_former.py tests/unit/test_action_selector.py` passes (5 tests)
- `make check` green (no layer violations, no new ruff issues)
- NPC with a decayed need forms a goal node + GOAL_TARGETS edge in the graph (verifiable via admin GET `/v1/admin/characters/{id}/goals`)
- `action_priority.py` constants used everywhere; no raw integer `50` comparisons
