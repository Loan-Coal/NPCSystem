# Next Session Instructions

## Phase 4 — Authoring engines. Feature 4.3 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

## Phase 4.1–4.2 completion status (committed 2026-05-13)

- 4.1: Faction politics engine — deterministic rules + decay, wired into TickScheduler.
- 4.2: Quest generation engine — slot-filling + LLM flavor text + graph validation.
- 681 unit tests green.

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 4.3 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 4 row: 4.1 ✅, 4.2 ✅, 4.3 IN_PROGRESS.

---

## Feature 4.3 — Story pacing engine

Read `project/ROADMAP.md` lines 675–699 first (the authoritative spec).

**Context:** The pacing engine is a meta-engine that gates other engines. It runs on each tick
advance, reads active quests and recent player activity, then writes `max_event_severity` and
`quest_generation_rate` multipliers to `WorldState`. Other engines read these before sampling.
No LLM. No new graph nodes or edges (WorldState fields are added).

### WorldState changes

Add two new fields to `WorldState` in `world/world_state.py` **and** in the WorldState type
registry contract (if a YAML exists for it — check `type_registry/base_nodes/world_state.yaml`):

```python
max_event_severity: int = 100    # events above this severity are suppressed; default = unconstrained
quest_generation_rate: float = 1.0  # multiplier on new quest generation; default = 1.0
```

These fields must have defaults so existing WorldState nodes in Neo4j (which lack these fields)
continue to load without error.

### Architecture

New package `engines/story_pacing/`:
- `__init__.py` — package docstring only.
- `pacing_rules.yaml`:
  ```yaml
  high_severity_quest_threshold: 70    # quests with severity >= this suppress events
  suppression_event_severity_cap: 30   # max_event_severity when high-severity quest is active
  suppression_quest_rate: 0.5          # quest_generation_rate when high-severity quest active
  cooldown_ticks: 10                   # ticks since last major event before pacing relaxes
  major_event_severity_floor: 60       # events above this count as "major"
  ```
- `pacing_rules_loader.py` — `PacingRules` frozen dataclass; `load_pacing_rules(path) -> PacingRules`.
- `pacing_queries.py` — Cypher constants:
  - `CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS` — find Quest nodes with status != 'completed' and severity >= N.
  - `CYPHER_GET_RECENT_MAJOR_EVENTS` — find Event nodes in last M ticks with severity >= floor.
- `story_pacing_engine.py` (≤200 lines) — `StoryPacingEngine(rules: PacingRules)`:
  - `run_tick(session, tick_id) -> dict`:
    a. Query active high-severity quests.
    b. Query recent major events (by tick_id or time).
    c. Compute new `max_event_severity` and `quest_generation_rate` based on rules.
    d. Write updated values to WorldState via `world_writer.upsert_world_state`.
    e. Return `{"max_event_severity": N, "quest_generation_rate": F, "suppressed": bool}`.

**Respecting pacing in other engines:**
- `engines/events/event_handler.py` — before sampling an event from the pool, read
  `world_state.max_event_severity`; skip events whose severity exceeds the cap.
- `engines/quest_generation/quest_generation_engine.py` — multiply new-quest probability
  by `world_state.quest_generation_rate` (only relevant if generation is rate-controlled).

Wiring:
- `api/dependency_singletons.py` — add `get_story_pacing_engine()` with `@lru_cache`.
- `scheduler/tick_scheduler.py` — add optional `story_pacing_engine: object = None`; call
  `await self._story_pacing_engine.run_tick(session=session, tick_id=tick_id)` before
  gossip/event sampling in each tick so pacing state is fresh when samplers run.
- `main.py` — inject `get_story_pacing_engine()` into the scheduler singleton.

### Steps

1. Add `max_event_severity` and `quest_generation_rate` fields to `WorldState` (with defaults).
   If `type_registry/base_nodes/world_state.yaml` exists, add the fields there too.
2. Implement `engines/story_pacing/` package.
3. Wire event_handler to check `world_state.max_event_severity` before sampling.
4. Wire quest_generation_engine to check `world_state.quest_generation_rate`.
5. Add `get_story_pacing_engine()` singleton and wire into `TickScheduler`.
6. Unit tests `tests/unit/test_story_pacing_engine.py`:
   - `test_pacing_rules_loader_loads_yaml` — loads real rules.yaml, asserts fields present.
   - `test_run_tick_suppresses_when_high_severity_quest_active` — mock: high-severity quest
     active → max_event_severity drops to suppression cap.
   - `test_run_tick_normal_when_no_high_severity_quest` — no such quest → max_event_severity = 100.
   - `test_run_tick_relaxes_after_cooldown` — no major events in cooldown window → rate normal.
   - `test_event_handler_skips_suppressed_severity` — event above max_event_severity not fired.
7. E2E scenario `e2e/scenarios/scenario_story_pacing.py`:
   - Seed a high-severity quest (severity=80, status=in_progress).
   - Run one tick advance.
   - Read WorldState; assert max_event_severity <= 30 (suppression cap).
   - Cleanup.

### Definition of done (4.3)
- WorldState extended with pacing fields (backward-compatible defaults).
- `engines/story_pacing/` package: rules loader, Cypher constants, engine.
- EventHandler respects `max_event_severity`.
- QuestGenerationEngine respects `quest_generation_rate`.
- Engine wired into TickScheduler.
- 5 unit tests green.
- E2E scenario passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: story pacing engine (Phase 4.3)`

---

## After 4.3 is committed — update this file for Feature 4.4

Read `project/ROADMAP.md` lines 701–719 and the Phase 4 plan file at
`~/.claude/plans/goal-implement-phase-4-dapper-kettle.md` (Iteration 4 section).
Replace this file with the Iteration 4 NEXT_SESSION.md content from that plan.

---

## Open issues to be aware of (do NOT fix unless blocking)

- ISSUE-013: `how_long_ago` bucket gap 7–27 days (P3)
- ISSUE-005: `adjust_reputation_for_event` not wired (P3)
- ISSUE-006: `Character.faction` string field not migrated (P3)
- ISSUE-004: `edge_updater.py` mypy warning (P3)
- ISSUE-011: `.env` uses Docker DNS (P3)
