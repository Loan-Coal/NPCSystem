# EXP-21 — World-state-aware quest trigger (first slice)

**Goal / rationale:** `QuestGenerationEngine` already reads `world_state.epoch` and injects it into
every quest prompt (`quest_generation_engine.py:153–157`), but there is no *trigger* that fires
automatically when the epoch changes. War begins → no quests appear. This trigger closes that gap by
detecting epoch-specific world conditions and scheduling appropriate quest generation. Business tie:
"living off-screen world" (`BUSINESS_INTENT.md:36,59`).

**First slice (worker scope):** A new `WorldStateQuestTrigger` class that on each tick reads the
current `world_state.epoch` + `active_conditions`, maps them to a list of applicable (archetype,
reason) pairs, and calls `QuestGenerationEngine.generate()` for the most appropriate NPC available,
with idempotency via a `CAUSED_BY` edge check (same pattern as `EventQuestTrigger`). No scheduler
wiring yet — just the class + unit tests. The scheduler registration is slice 2.

**Current state (verified):**
- `src/npc_engine/engines/quest_generation/event_quest_trigger.py`: reference implementation.
  Class `EventQuestTrigger` with `__init__(generation_engine, trigger_event_types, military_archetypes)`
  and `async run_tick(session, tick_id)`. Uses `get_unprocessed_trigger_events`, `get_any_military_npc`.
- `src/npc_engine/engines/quest_generation/need_quest_trigger.py`: second reference (need-driven).
- `src/npc_engine/engines/quest_generation/quest_generation_engine.py:34`: imports `get_world_state`.
  `generate()` at line 115 receives `session, quest_giver_id, player_id, rng`. It calls `get_world_state`
  internally — the trigger does NOT need to inject world state; it just picks the NPC.
- `src/npc_engine/graph/event_trigger_queries.py`: provides `get_any_military_npc(session)` and
  `get_military_npc_at_location(session, location_id)` — these can be reused for epoch="war".

**Files (ALL NEW — zero existing edits in this slice):**
- NEW `src/npc_engine/engines/quest_generation/world_state_quest_trigger.py`
  — `WorldStateQuestTrigger(generation_engine, max_per_tick=1)`.
  — `async run_tick(session, tick_id)`: read `get_world_state`, derive (archetype_hint, reason), pick
    NPC via `get_any_military_npc` for war / merchant for famine / healer for plague, call `generate()`.
  — Idempotency: skip if `world_state.tick_last_world_quest_triggered == tick_id` (or use a
    `WorldQuestCooldown` node if that field doesn't exist — check first; if absent, use a module-level
    `_last_triggered_tick` sentinel for now).
  — `_EPOCH_ARCHETYPE_MAP: dict[str, str]` — constant mapping epoch→archetype hint.
- NEW `tests/unit/test_world_state_quest_trigger.py`
  — Mock `get_world_state` to return epoch="war".
  — Mock `get_any_military_npc` to return a valid NPC id.
  — Mock `generation_engine.generate` to return a dummy QuestRecord.
  — Assert `run_tick(session, tick_id="t1")` calls generate once with the military NPC.
  — Assert `run_tick(session, tick_id="t1")` again (same tick) does NOT call generate (idempotency).

**Graph/API surface:** None. Engine-internal only. No schema change.

**Architecture fit:** Pure new-file-add (OCP). Pattern is identical to `EventQuestTrigger`.
Does NOT edit `quest_generation_engine.py` or `dependencies_engines.py` — that's slice 2 (scheduler
wiring). The new class is fully tested standalone.

**Test plan:**
Write `tests/unit/test_world_state_quest_trigger.py` FIRST (as above). Run:
`pytest tests/unit/test_world_state_quest_trigger.py -q`

**Done when:** Unit tests green; `world_state_quest_trigger.py` is < 100 lines with full docstrings.
Next slice (EXP-21 slice 2): edit `dependencies_engines.py` + `tick_scheduler.py` to wire the trigger.
