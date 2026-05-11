# Next Session Instructions

## Phase 3 — World Depth. Feature 3.1 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — add Phase 3 section, mark Feature 3.1 as IN_PROGRESS, set today's date.
2. `project/STATUS.md` — update to reflect Phase 3 has started.

---

## Feature 3.1 — Time as a first-class concept

Read `project/ROADMAP.md` lines 387–414 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** `WorldState` already has `time_of_day: str`. This feature adds structured
time fields (`year`, `season`, `day`) and a helper for human-readable time distances.
The clock advance endpoint already exists at `POST /v1/clock/advance`; it accepts
`delta_ticks` and `game_time_seconds`. Feature 3.1 extends it with an optional
`advance_time_field` parameter.

### Architecture decisions (read before coding)

- `WorldState` lives in `world/world_state.py`. It is a Pydantic `BaseModel` serialized
  via `model_dump_json()`. Adding fields is sufficient for dialogue context inclusion
  (context builder serializes the whole model at Tier 0, line 132 of `retrieval/context_builder.py`).
  No YAML semantic annotation needed.
- `world/time_utils.py` must be a **pure, I/O-free module** (no sessions, no imports from
  `graph/` or `engines/`). Keep it in `world/`.
- `world/world_time_service.py` — pure `advance_time(field, world_state) -> WorldState`.
  Returns a new `WorldState`; never mutates. Follows the immutability rule.
- Wrap-around rules: day 1–28, season cycles `spring → summer → autumn → winter → spring`,
  each season change increments `day` back to 1; winter→spring increments `year`.
- The `POST /v1/clock/advance` handler is in `api/routes/clock.py` (or similar). Extend it.

### Steps

1. **`WorldState` schema update** (`world/world_state.py`):
   - Add `year: int = 1`, `season: str = "spring"`, `day: int = 1` fields.
   - `time_of_day` is already present — leave it.
   - Update the CYPHER_MERGE_WORLD_STATE constant in `engines/events/event_handler.py` to
     include the new fields (and any other place that serializes WorldState to graph).

2. **`world/time_utils.py`** (new, ≤80 lines):
   - `TimePoint` frozen dataclass: `year: int`, `season: str`, `day: int`, `time_of_day: str`.
   - `how_long_ago(from_: TimePoint, to: TimePoint) -> str` — returns human-friendly string:
     - Same time_of_day and day → `"moments ago"`
     - Same day → `"earlier today"`
     - 1 day ago → `"yesterday"`
     - 2–6 days → `"a few days ago"`
     - 1 season ago → `"last season"`
     - More than a season → `"long ago"`

3. **`world/world_time_service.py`** (new, ≤120 lines):
   - `SEASONS = ["spring", "summer", "autumn", "winter"]`
   - `advance_time(field: str, world_state: WorldState) -> WorldState` — pure function.
   - `field` is one of `"time_of_day"`, `"day"`, `"season"`, `"year"`.
   - `time_of_day` cycles through the five existing values (`morning → midday → afternoon →
     evening → night → morning`). When it wraps from `night → morning`, increment `day`.
   - `day` wraps 1–28; at day 29 reset to 1 and advance `season`.
   - `season` wraps; at `winter → spring` increment `year`.
   - `year` never wraps (increment indefinitely).
   - Returns a new `WorldState` via `model_copy(update={...})`.

4. **`POST /v1/clock/advance` extension**:
   - Locate the clock advance handler (check `api/routes/` or `api/routes/clock.py`).
   - Add optional `advance_time_field: str | None = None` to the request body.
   - When provided, call `world_time_service.advance_time(field, current_world_state)` and
     persist the updated world state to Neo4j using the existing MERGE pattern.
   - When not provided, existing behavior is unchanged.

5. **Unit tests** `tests/unit/test_world_time_service.py`:
   - `time_of_day` advances through all five slots and wraps.
   - `night → morning` increments `day`.
   - `day 28 → day 1` increments `season`.
   - `winter → spring` increments `year`.
   - `how_long_ago` returns correct bucket for each distance category.
   - `advance_time` is pure (original WorldState unchanged).

6. **E2E scenario** `e2e/scenarios/scenario_time_passage.py`:
   - Advance `time_of_day` through a full day cycle.
   - Assert the day increments after `night`.
   - Advance day to 28 and assert season increments.

### Definition of done (3.1)
- `WorldState` has `year`, `season`, `day` fields.
- `time_utils.py` and `world_time_service.py` pass all unit tests.
- Clock advance endpoint accepts `advance_time_field` and persists the result.
- `tests/unit/test_world_time_service.py` passes all cases listed above.
- E2E scenario `scenario_time_passage.py` passes.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: structured game time (Phase 3.1)`

---

## After 3.1 is committed — update this file for Feature 3.2

When Feature 3.1 is committed and `pytest tests/ -q` is green, rewrite this file to target
Feature 3.2 — Memories vs Knowledge.

Read `project/ROADMAP.md` lines 416+ before writing 3.2 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 3 unless explicitly blocking)

- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)

If any of these blocks Phase 3.1, log a new ISSUES.md entry describing the blocking scenario
and get approval before fixing.
