# Next Session Instructions

## Phase 2 is in progress — Feature 2.3 next

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 2.3 as IN_PROGRESS, set today's date.
2. `project/STATUS.md` — no change needed.

---

## Feature 2.3 — Routine disruption

Read `project/ROADMAP.md` lines 361–382 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** The RoutineEngine (Phase 2.2) already reads and clears `character.routine_override`
on each tick. This feature makes two things _write_ that field:
1. The event engine, when a high-impact event occurs near a character.
2. The dialogue handler, when the emotion engine detects extreme negative valence.

The `routine_override` shape is: `{"location_id": "...", "expires_at_tick": N}`.

### Architecture decision (read before coding)

`emotion_updater.py` is currently I/O-free (in-memory only). Adding graph writes requires a
session. The cleanest approach: **the caller handles the write**. After `apply_dialogue_mood`
returns an `EmotionState`, the caller (in `dialogue_handler.py`) checks `state.valence < -60`
and calls `set_routine_override`. Do NOT add a session parameter to `emotion_updater`.

### Steps

1. **Disruption rules YAML** — create `src/npc_engine/engines/events/disruption_rules.yaml`:
   ```yaml
   rules:
     - trigger_event_types: [death, betrayal]
       override_location: home
       duration_ticks: 10
     - trigger_severity_min: 70
       override_location: home
       duration_ticks: 5
   ```
   Load at startup via `engines/events/disruption_loader.py` (new, ≤80 lines) — a thin YAML
   reader following the same pattern as `engines/gossip/gossip_config.py`. Use
   `common/yaml_utils.load_yaml_mapping` for loading.

2. **`set_routine_override` write function** — add to `engines/routine/routine_queries.py`
   (already contains related Cypher constants for the routine engine):
   ```python
   async def set_routine_override(
       session: AsyncSession,
       character_id: str,
       location_id: str,
       expires_at_tick: int,
   ) -> None:
   ```
   Cypher: `MATCH (c:Character {id: $character_id}) SET c.routine_override = $override_json`
   where `override_json = json.dumps({"location_id": ..., "expires_at_tick": ...})`.

3. **Event handler wiring** (`engines/events/event_handler.py`):
   - After `seed_awareness_tx` completes (inside `run_tick`), load the disruption rules if not
     already loaded (cache as `self._disruption_rules` set in `__init__`).
   - For each disruption rule: if the created event's `event_type` matches `trigger_event_types`
     OR `event.severity >= trigger_severity_min`, query characters near the event location
     (characters with `LOCATED_AT` pointing to the same location).
   - For each affected character, call `set_routine_override(session, char_id, "home", tick_id + duration_ticks)`.
   - Use a new helper function `_apply_disruption_rules(rules, event_type, severity, tick_id)` → list of applicable rules.
   - Import `set_routine_override` from `npc_engine.engines.routine.routine_queries`.
   - Add `disruption_rules_path: str | None = None` to `EventHandler.__init__` (default None →
     loads from `settings.EVENT_POOL_PATH.parent / "disruption_rules.yaml"`). This keeps the
     existing constructor signature backward-compatible.

4. **Emotion-triggered disruption** (`engines/dialogue/dialogue_handler.py`):
   - After calling `self._emotion_updater.apply_dialogue_mood(npc_id, mood_update)`, check if
     `new_state.valence < -60`.
   - If so, call `await set_routine_override(session, npc_id, "home", tick_id + 5)`.
   - `tick_id` is available as `context.tick_id` in `DialogueHandler.handle`. If the tick_id
     is not currently in scope, pass it through from the dialogue request context. Check
     `dialogue_handler.py` and `dialogue_models.py` for how tick context flows today.
   - Import `set_routine_override` from `npc_engine.engines.routine.routine_queries`.

5. **Unit tests** `tests/unit/test_routine_disruption.py`:
   - Disruption rule fires on matching event type.
   - Disruption rule fires when severity ≥ threshold.
   - No rule fires when event type and severity do not match.
   - Override is set with correct `expires_at_tick = tick_id + duration_ticks`.
   - Emotion threshold `valence < -60` triggers `set_routine_override` call.
   - Emotion threshold `valence == -60` does NOT trigger (strictly less than).
   - Override correctly expires — reuse logic from `test_routine_engine.py` (the routine engine
     already handles expiry; no new expiry logic needed here).
   - All tests mock Neo4j and `set_routine_override` — no I/O.

6. **E2E extension** — add a new test function to `e2e/scenarios/scenario_daily_life.py`:
   - Seed a death event near the guard's location.
   - Advance N ticks.
   - Assert the guard is at `home` (their `routine_override` is active).
   - Advance past `expires_at_tick`.
   - Assert the guard resumes their schedule location.

### Definition of done (2.3)
- `disruption_rules.yaml` loads without errors.
- `disruption_loader.py` parses rules at startup.
- Event handler applies overrides for matching event types and severity.
- Dialogue handler writes override when valence < -60.
- `tests/unit/test_routine_disruption.py` passes (all cases listed above).
- E2E scenario demonstrates death event → stay-home → expiry → resume.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: routine disruption rules (Phase 2.3)`

---

## After 2.3 is committed — update this file for Phase 3

When Feature 2.3 is committed and `pytest tests/ -q` is green, rewrite this file to target
Phase 3 — World depth. Feature 3.1 is the first step: Time as a first-class concept.

Read `project/ROADMAP.md` lines 387–414 before writing 3.1 instructions.

3.1 key points:
- `WorldState` already has `time_of_day`. Add `year: int`, `season: str`, `day: int`.
- `world/time_utils.py` — `TimePoint` dataclass + `how_long_ago(from_, to) -> str` helper.
- `world/world_time_service.py` — pure `advance_time(field, world_state) -> WorldState`
  with wrap-around rules (day 1-28 → increment season, winter → spring → increment year).
- `POST /v1/clock/advance` extended with optional `advance_time_field` param.
- WorldState is serialized wholesale via `model_dump_json()` at Tier 0 in
  `retrieval/context_builder.py:132` — adding fields to the model is sufficient for dialogue
  context; no YAML semantic annotation needed.
- Unit tests for all time advance transitions + how_long_ago buckets.
- E2E scenario: `scenario_time_passage.py`.

---

## Open issues to be aware of (do NOT fix during Phase 2 unless explicitly blocking)

- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 2.3, log a new ISSUES.md entry describing the blocking scenario
and get approval before fixing.
