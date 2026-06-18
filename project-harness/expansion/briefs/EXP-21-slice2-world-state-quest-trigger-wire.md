# EXP-21 slice-2 — Wire WorldStateQuestTrigger into tick scheduler

**Goal / rationale:** EXP-21 slice-1 delivered `WorldStateQuestTrigger` as a standalone class
with unit tests. This slice wires it into the running tick scheduler so epoch changes actually fire
quest generation without manual intervention. Pattern is identical to the `event_quest_trigger`
integration that already exists.

**First slice status:** `WorldStateQuestTrigger` in
`src/npc_engine/engines/quest_generation/world_state_quest_trigger.py` — fully tested.

**Slice-2 scope:** Two additive edits, no new files, no API surface change.

**Current state (verified):**

`src/npc_engine/api/dependencies_engines.py`:
- Line 38-39: imports `EventQuestTrigger`, `NeedQuestTrigger` — add `WorldStateQuestTrigger` here.
- Lines 107-123: `get_event_quest_trigger()` + `get_need_quest_trigger()` `@lru_cache` factories —
  add `get_world_state_quest_trigger()` following the same pattern.
- Lines 219-221: `get_tick_scheduler()` call passes `event_quest_trigger=get_event_quest_trigger(),
  need_quest_trigger=get_need_quest_trigger()` — add `world_state_quest_trigger=get_world_state_quest_trigger()`.

`src/npc_engine/scheduler/tick_scheduler.py` (602 lines — waiver already in DECISIONS.md):
- Lines 82-83: `event_quest_trigger: BaseEngine | None = None, need_quest_trigger: BaseEngine | None = None`
  constructor params — add `world_state_quest_trigger: BaseEngine | None = None` after them.
- Lines 131-133: docstring entries for those params — add matching docstring entry.
- Lines 167-168: `self._event_quest_trigger = ...` assignments — add `self._world_state_quest_trigger = world_state_quest_trigger`.
- Lines 507-521: the `if self._event_quest_trigger is not None` + `if self._need_quest_trigger is not None`
  call blocks — add identical block for `self._world_state_quest_trigger` labelled `"world_state_quest"`.

**Files:**
- EDIT `src/npc_engine/scheduler/tick_scheduler.py` — 4 targeted additions (param, docstring, assignment, call block).
- EDIT `src/npc_engine/api/dependencies_engines.py` — add import, factory, and wire into `get_tick_scheduler()`.

**No new files.** No new tests required beyond verifying the existing unit test suite stays green
(`pytest tests/unit/test_world_state_quest_trigger.py tests/unit/test_tick_scheduler.py -q`).
If `test_tick_scheduler.py` constructs `TickScheduler` directly, verify it still passes with the
new optional param (default `None` means it's backward compatible).

**Graph/API surface:** None — engine-internal scheduler change only.

**Architecture fit:** Pure additive injection; follows the existing `event_quest_trigger` pattern
verbatim. No layer rules affected.

**Done when:** `pytest tests/ -q` stays green; `WorldStateQuestTrigger` appears in
`get_tick_scheduler()` call in `dependencies_engines.py`.
