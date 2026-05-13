# Next Session Instructions

## Phase 4 — Authoring engines. Feature 4.1 next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

## Phase 3 e2e HTTP migration (completed 2026-05-13)

All 13 e2e scenario files now call only the HTTP API — no direct neo4j connections remain.
New admin routes added: `memories` router (CRUD + from-arousal + decay + consolidate),
DELETE endpoints on beliefs/goals/secrets/items, `k` param on secrets GET.
Verify: `grep -r "AsyncGraphDatabase" e2e/` → zero results.

## Phase 3 test foundation status (completed before this session)

All blocks are done — 667 unit tests green, 20 E2E scenario tests collected:
- Block 1: `api_seeder.py` enriched with beliefs, goals, items, secrets, debts, memories
- Block 2: Edge case unit tests added to all 6 Phase 3 test files
- Block 3: 6 edge case E2E scenario files (`scenario_*_edge.py`)
- Block 4: `e2e/scenarios/scenario_demo.py` — full Phase 3 story arc
- Block 5: `e2e/scenarios/scenario_llm_judge.py` + `e2e/helpers/llm_judge.py`
- Block 6: Makefile targets `scenario-edge`, `scenario-demo`, `eval-llm`; markers `demo`, `llm_eval` registered

---

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 3.8 as DONE (committed),
   add Phase 4 section with Feature 4.1 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 3 row to reflect 3.1–3.8 ✅ (complete),
   add Phase 4 row showing 4.1 IN_PROGRESS.

---

## Feature 4.1 — Faction politics engine (deterministic)

Read `project/ROADMAP.md` lines 613–635 first (the authoritative spec).

Only start after `pytest tests/ -q` is green.

**Context:** Faction standings drift over time based on events. This is a
deterministic rule-based engine — no LLM. On each tick it reads recent events,
matches them against rules in a YAML file, adjusts `STANDS_WITH.standing` edges,
and applies a slow drift-to-neutral decay. The `STANDS_WITH` edge already exists
in `type_registry/base_edges/stands_with.yaml` with fields `standing` (int,
[-100,100]) and `last_changed_at` (str). The factions graph layer already has
`graph/faction_service.py`, `graph/faction_queries.py`, and `graph/faction_writer.py`
with `set_standing` available.

### Architecture decisions (read before coding)

- **New package**: `engines/faction_politics/` with:
  - `__init__.py` — package docstring only.
  - `rules.yaml` — rule definitions (see format below).
  - `rules_loader.py` — loads and validates `rules.yaml` at startup.
  - `faction_politics_engine.py` (≤200 lines) — `FactionPoliticsEngine.run_tick(session)`.
- **No new graph nodes or edges.** Reads events from the graph, writes to
  `STANDS_WITH.standing` via `graph/faction_writer.set_standing`.
- **Tick wiring**: Inject `FactionPoliticsEngine` into `scheduler/tick_scheduler.py`
  as an optional field (same pattern as `MemoryConsolidationEngine` or
  `RoutineEngine`). Wire it into `api/dependency_singletons.py` with a
  `get_faction_politics_engine` singleton.
- **No new API routes.** Standings are already readable via the existing factions
  admin routes (`GET /v1/admin/factions/{faction_id}/standings`).

### Rule YAML format (`engines/faction_politics/rules.yaml`)

```yaml
decay:
  rate_per_tick: 1          # move standing 1 point toward 0 each tick
  min_magnitude: 2          # skip decay if |standing| < min_magnitude

rules:
  - id: betrayal_standing_penalty
    event_type: betrayal
    standing_delta: -10
    description: "A betrayal event between faction members reduces inter-faction standing."

  - id: alliance_act_bonus
    event_type: alliance_act
    standing_delta: 5
    description: "An alliance act between members of allied factions increases standing."
```

Fields per rule: `id` (str, unique), `event_type` (str), `standing_delta` (int),
`description` (str, optional).

### Steps

1. **`engines/faction_politics/rules.yaml`** — seed with at least two rules:
   `betrayal` → -10, `alliance_act` → +5. Include the `decay` block.

2. **`engines/faction_politics/rules_loader.py`**:
   - `FactionPoliticsRule` — frozen dataclass: `id`, `event_type`,
     `standing_delta`.
   - `DecayConfig` — frozen dataclass: `rate_per_tick`, `min_magnitude`.
   - `FactionPoliticsRules` — frozen dataclass: `decay`, `rules` (list).
   - `load_rules(path) -> FactionPoliticsRules` — loads YAML, validates unique
     `id`s, fails fast on schema violations.

3. **`engines/faction_politics/faction_politics_engine.py`** (≤200 lines):
   - `FactionPoliticsEngine(rules: FactionPoliticsRules)`.
   - `run_tick(session) -> None`:
     a. Query recent events (last N, configurable; default 20) that have a
        `src_character_id` field. For each event, look up the factions of the
        source character via the graph.
     b. For each matching rule (`event.event_type == rule.event_type`), find
        faction pairs (A, B) where A is the faction of the event source and B is
        any faction standing partner. Clamp delta application to [-100, 100].
        Call `set_standing(session, faction_a_id, faction_b_id, new_standing)`.
     c. After rule processing, apply decay: for every `STANDS_WITH` edge where
        `|standing| >= decay.min_magnitude`, move standing by `rate_per_tick`
        toward 0. Call `set_standing` for any edge that changes.
   - `CYPHER_GET_RECENT_EVENTS` and `CYPHER_GET_ALL_STANDINGS` — Cypher string
     constants in this file (or a companion `faction_politics_queries.py` if
     the engine file grows past 200 lines).

4. **`engines/faction_politics/__init__.py`** — package docstring only.

5. **Wiring**:
   - `api/dependency_singletons.py` — add `get_faction_politics_engine()` using
     `@lru_cache` (same pattern as other engine singletons).
   - `scheduler/tick_scheduler.py` — accept optional
     `faction_politics_engine: FactionPoliticsEngine | None = None`; call
     `await faction_politics_engine.run_tick(session)` in the advance loop if
     not None (same optional pattern as memory consolidation engine).
   - `main.py` — inject `get_faction_politics_engine()` into the scheduler
     singleton at startup (same pattern as other optional engines).

6. **Unit tests** `tests/unit/test_faction_politics_engine.py`:
   - `test_rules_loader_loads_yaml` — loads the real `rules.yaml`, assert 2+
     rules loaded and decay block present.
   - `test_run_tick_applies_matching_rule` — mock graph calls; event of type
     `betrayal` → standing decreases by 10.
   - `test_run_tick_no_matching_rule_no_change` — event type with no matching
     rule → no standing update.
   - `test_run_tick_clamps_to_bounds` — delta that would exceed ±100 is clamped.
   - `test_run_tick_applies_decay` — standing of magnitude >= min_magnitude drifts
     toward 0 each tick.
   - `test_run_tick_skips_decay_below_min_magnitude` — small standing is not decayed.

7. **E2E scenario** `e2e/scenarios/scenario_faction_politics.py`:
   - Seed two factions and one character belonging to faction A.
   - Inject a `betrayal` event linked to that character.
   - Run one engine tick.
   - Assert that the A→B standing decreased by 10.
   - Cleanup.

### Definition of done (4.1)
- `engines/faction_politics/rules.yaml` exists with ≥2 rules and decay config.
- `rules_loader.py` parses and validates the YAML at startup.
- `FactionPoliticsEngine.run_tick` applies rules and decay using the graph layer.
- Engine is wired into `TickScheduler` as optional injection.
- All 6 unit tests green.
- E2E scenario passes.
- No new graph nodes or edges introduced.
- Pre-merge checklist from `CLAUDE.md` satisfied.
- Commit: `feat: faction politics engine (Phase 4.1)`

---

## After 4.1 is committed — update this file for Feature 4.2

When Feature 4.1 is committed and `pytest tests/ -q` is green, rewrite this
file to target Feature 4.2 — Quest templates and slot-filling generation.

Read `project/ROADMAP.md` lines 636–671 before writing 4.2 instructions.

---

## Open issues to be aware of (do NOT fix during Phase 4.1 unless explicitly blocking)

- **ISSUE-013**: `how_long_ago` has no defined bucket for 7–27 days (P3)
- **ISSUE-005**: `adjust_reputation_for_event` not wired into event engine (P3)
- **ISSUE-006**: pre-existing `Character.faction` string field not migrated (P3)
- **ISSUE-004**: `edge_updater.py` no-any-return mypy warning (P3)
- **ISSUE-011**: `.env` uses Docker DNS (`bolt://neo4j:7687`) — fails outside Docker (P3)
- **FIXED**: `test_memory_service.py::test_decay_all_vividness_*` — fixed in
  the Phase 3 test foundation session (wrong mock type corrected, 667 tests green).

If any of these blocks Phase 4.1, log a new ISSUES.md entry describing the
blocking scenario and get approval before fixing.
