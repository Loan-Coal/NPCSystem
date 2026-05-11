# Next Session Instructions

## Phase 1 is done — Phase 2 starts now

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

Before writing a single line of Phase 2 code, do these three edits:

1. `project/IMPLEMENTATION_TRACKER.md` — mark Phase 2 as IN_PROGRESS, set today's date.
2. `project/STATUS.md` — already updated.
3. Confirm `docs/DATA_MODELS.md` has the Phase 2 schema sections (they were added in session prep).

---

## Feature 2.1 — Schedule nodes and edges

Read `project/ROADMAP.md` lines 282–319 first (the authoritative spec).

### Steps

1. **Schema files** (create):
   - `src/npc_engine/type_registry/base_nodes/schedule.yaml`
   - `src/npc_engine/type_registry/base_edges/follows_schedule.yaml`

2. **WorldState extension**: add `time_of_day` string field (enum: `morning`, `midday`,
   `afternoon`, `evening`, `night`) to `world/world_state.py` `WorldState` model.
   Default: `"morning"`. Check if `type_registry/base_nodes/world_state.yaml` exists and
   update it too.

3. **Character extension**: add `routine_override` JSON-nullable field to Character schema.
   Shape when set: `{"location_id": "...", "expires_at_tick": 42}`. Used in 2.2 — define
   now so schema is stable.

4. **Service**: `src/npc_engine/graph/schedule_service.py` (≤300 lines).
   Use `src/npc_engine/graph/faction_service.py` as the style reference.
   - `create_schedule(id, name, description, entries) -> dict`
   - `assign_schedule(character_id, schedule_id) -> None` — creates `FOLLOWS_SCHEDULE` edge
   - `get_character_location_at(character_id, time_of_day) -> str | None`
   - `get_characters_at_location(location_id, time_of_day) -> list[str]`
   Extract Cypher into `src/npc_engine/graph/schedule_queries.py`.

5. **Unit tests**: `tests/unit/test_schedule_service.py` — mock Neo4j, cover all 4 ops
   plus failure cases (character not found, schedule not found, invalid time_of_day).

6. **Integration tests**: `tests/integration/test_schedule_service.py` — requires test Neo4j.

7. **API routes**: `src/npc_engine/api/routes/schedules.py` under `/v1/admin/schedules/`:
   - `POST /v1/admin/schedules/` — create schedule
   - `POST /v1/admin/schedules/{schedule_id}/assign/{character_id}` — assign to character
   - `GET /v1/admin/schedules/location/{location_id}?time_of_day=morning` — who's there
   - `GET /v1/admin/schedules/character/{character_id}?time_of_day=morning` — where is character
   Wire into `main.py` / `dependencies.py`.

8. **E2E script**: `e2e/scenarios/scenario_daily_life.py` — seed world, assign schedules,
   query each time_of_day, assert expected locations. No tick advancing yet (that's 2.2).

9. **Update `docs/DATA_MODELS.md`**: confirm the Phase 2 schema sections are present
   (added in session prep). If missing, add them now.

### Definition of done (2.1)
- Schema YAML files exist and load without startup errors.
- All 4 service operations have unit + integration tests passing.
- Admin API routes respond correctly.
- `docs/DATA_MODELS.md` has Schedule node and FOLLOWS_SCHEDULE edge documented.
- `e2e/scenarios/scenario_daily_life.py` runs successfully (query-only).
- Pre-merge checklist from `CLAUDE.md` is satisfied.
- Commit: `feat: schedule nodes and edges (Phase 2.1)`

---

## Feature 2.2 — Routine engine

Read `project/ROADMAP.md` lines 321–353 first.  
Only start after 2.1 is committed and `pytest tests/ -q` is green.

### Steps

1. **New engine package**: `src/npc_engine/engines/routine/`
   - `__init__.py` (package docstring)
   - `routine_engine.py` (≤300 lines) — tick handler
   - `routine_queries.py` — all Cypher strings

2. **`RoutineEngine.run_tick(time_of_day: str) -> None`**:
   - Query all active characters that have a `FOLLOWS_SCHEDULE` edge.
   - For each: parse `schedule.entries` JSON, find entry matching `time_of_day`.
   - Check `character.routine_override`: if non-null and `tick_id < expires_at_tick`,
     use override `location_id`. If expired, clear it in the same transaction.
   - Compare to current `LOCATED_AT` target. If different: delete old `LOCATED_AT`,
     create new one (atomic, single transaction). Log movement.
   - Skip characters where `is_active = false`.

3. **Register with scheduler**: update `scheduler/tick_scheduler.py` to instantiate
   `RoutineEngine` and call `run_tick(world_state.time_of_day)` each tick.
   Add `get_routine_engine` singleton to `api/dependency_singletons.py`.

4. **Gossip verification**: `engines/gossip/pair_selector.py` queries `LOCATED_AT` —
   confirm no change needed but add one integration test that seeds a schedule,
   advances a tick, and asserts gossip pairs now reflect the updated locations.

5. **Unit tests**: `tests/unit/test_routine_engine.py` — mock graph:
   - Character moves when schedule says new location.
   - Character stays when already at scheduled location.
   - Inactive character is skipped entirely.
   - `routine_override` non-null and not expired → override location used.
   - `routine_override` expired → cleared, schedule location used.

6. **Integration tests**: `tests/integration/test_routine_engine.py` — full tick cycle
   moves characters correctly against test Neo4j.

7. **E2E**: extend `e2e/scenarios/scenario_daily_life.py` — advance N ticks via
   `POST /v1/clock/advance`, assert NPCs are at expected locations per schedule.

### Definition of done (2.2)
- Engine runs tick, moves characters, clears expired overrides.
- Inactive characters unaffected.
- Scheduler wires engine on every tick.
- Unit + integration tests pass.
- E2E scenario advances ticks and asserts correct locations.
- `docs/ARCHITECTURE.md` updated with routine engine section (brief, under gossip engine pattern).
- Pre-merge checklist satisfied.
- Commit: `feat: routine engine tick-driven location updates (Phase 2.2)`

---

## Feature 2.3 — Routine disruption

Read `project/ROADMAP.md` lines 361–382 first.  
Only start after 2.2 is committed and tests are green. May spill to next session.

### Steps

1. **`engines/events/disruption_rules.yaml`** — map event conditions to override durations.
   Example:
   ```yaml
   rules:
     - trigger: related_character_death
       override_location: home
       duration_ticks: 10
     - trigger: severe_negative_event_nearby  # severity > 70
       override_location: home
       duration_ticks: 5
   ```

2. **Wire into event engine**: after an event is processed in `engines/events/event_handler.py`,
   check disruption rules. If triggered, set `routine_override` on affected characters.

3. **Emotion integration**: in `engines/emotion/emotion_updater.py`, after applying emotion
   updates, if `valence < -60`, set `routine_override` (stay-home) for `duration_ticks = 5`.
   Read the `EmotionState` valence from `engines/emotion/emotion_state.py`.

4. **Unit tests**: `tests/unit/test_routine_disruption.py` — cover:
   - Disruption rule fires on matching event type.
   - Override is set with correct duration.
   - Emotion threshold triggers override.
   - Override correctly cleared by routine engine on expiry (reuse test from 2.2).

5. **E2E**: `e2e/scenarios/scenario_daily_life.py` — inject a death event, assert affected
   character stays home for N ticks then resumes schedule.

### Definition of done (2.3)
- Disruption rules YAML loads without errors.
- Event engine triggers overrides per rules.
- Emotion threshold triggers override.
- Tests pass.
- Pre-merge checklist satisfied.
- Commit: `feat: routine disruption rules (Phase 2.3)`

---

## Open issues to be aware of (do NOT fix during Phase 2 unless explicitly blocking)

- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 2, log a new ISSUES.md entry describing the blocking scenario
and get approval before fixing.
