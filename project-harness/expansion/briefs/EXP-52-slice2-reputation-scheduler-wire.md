# EXP-52 slice-2 — Reputation Engine: tick-scheduler wire

**Goal / rationale:** EXP-52 slice-1 built `ReputationEngine` with `run_tick()` and shipped it
with `enabled: false` in `reputation_rules.yaml`.  Slice-2 wires the engine into the tick
scheduler and composition root so game operators can enable it by flipping the flag.
Business intent: personal reputation propagates 1-hop through the social graph each tick.

**Prerequisite:** EXP-52 slice-1 merged ✅ (`engines/reputation/reputation_engine.py` exists).

---

## First slice (worker scope)

1. EDIT `tick_scheduler.py` — add `reputation_engine: BaseEngine | None = None` optional kwarg
   following the `world_state_quest_trigger` pattern (lines 82–84, `__init__` + docstring + `advance()`).
   Add `"reputation"` key to `response` dict; call `_run_engine_safe("reputation", tick_id, ...)` in
   the tick loop.
2. EDIT `dependencies_engines.py` — add `get_reputation_engine() → ReputationEngine` factory
   (load `reputation_rules.yaml` via `load_propagation_config()`; inject `RelationReader` +
   `apply_trust_nudge` via the graph helpers).  Wire into `get_tick_scheduler()`.
3. NEW `tests/unit/test_reputation_scheduler_wire.py` — verify the wiring (mock scheduler,
   assert `reputation_engine.run_tick` called when engine is set; not called when `None`).

---

## Current state (verified)

- `src/npc_engine/engines/reputation/reputation_engine.py` — `ReputationEngine.run_tick(session, player_id, npc_ids)` exists; config flag `enabled: false` checked internally.
- `src/npc_engine/engines/reputation/reputation_rules.yaml:6` — `enabled: false`.
- `src/npc_engine/scheduler/tick_scheduler.py:82–84` — `world_state_quest_trigger` pattern to follow exactly.
- `src/npc_engine/api/dependencies_engines.py:127–134` — `get_world_state_quest_trigger()` factory pattern to follow.

### Signature note

`ReputationEngine.run_tick(session, player_id, npc_ids)` takes `player_id` + `npc_ids`.  For the
tick scheduler, create a thin `ReputationTickAdapter` in `engines/reputation/reputation_tick_adapter.py`
that wraps `ReputationEngine.run_tick` with the `run_tick(session, tick_id) → dict` signature expected
by `TickScheduler`.  The adapter fetches all active (player_id, npc_ids) from a configurable source
(or, in this slice, uses `get_settings().WORLD_ID` as player_id and queries character IDs from graph via
a new `graph/character_reader.get_npc_ids(session)` helper if it does not already exist).

If `graph/character_reader.py` already exists and has `get_npc_ids`, reuse it.  If not, add one function
there or create `graph/character_reader.py` (graph layer, single function).  Do NOT query characters
from inside `engines/`.

---

## Files

**New:**
- `src/npc_engine/engines/reputation/reputation_tick_adapter.py`
- `tests/unit/test_reputation_scheduler_wire.py`

**Edited:**
- `src/npc_engine/scheduler/tick_scheduler.py`
- `src/npc_engine/api/dependencies_engines.py`

**Maybe new (check first):**
- `src/npc_engine/graph/character_reader.py` — add `get_npc_ids(session) → list[str]` if missing.

---

## Graph / API surface

No new HTTP route. No schema change.  Tick scheduler result dict gains `"reputation"` key (additive).
Engine is off by default (`enabled: false` in YAML) so wiring has zero runtime cost when disabled.

---

## Architecture fit

New-file-add adapter.  Wiring-only edit to two existing files.  All graph queries in `graph/` layer.

---

## Test plan

Write `tests/unit/test_reputation_scheduler_wire.py` FIRST.

| Test | Asserts |
|------|---------|
| `test_reputation_engine_called_when_set` | mock engine; `_run_engine_safe` invokes `run_tick` |
| `test_reputation_engine_not_called_when_none` | `reputation_engine=None` → mock never called |
| `test_adapter_returns_empty_when_disabled` | config `enabled=False` → `run_tick` returns `{"nudges": 0}` |

Run: `pytest tests/unit/test_reputation_scheduler_wire.py -q`

---

## Done when

- Tests green.
- `tick_scheduler.py` accepts `reputation_engine` kwarg; `"reputation"` in response dict.
- `dependencies_engines.py` has `get_reputation_engine()` wired into `get_tick_scheduler()`.
- No file > 300 lines.  No schema change.
- Adjacent issues spotted: report, do NOT fix.
