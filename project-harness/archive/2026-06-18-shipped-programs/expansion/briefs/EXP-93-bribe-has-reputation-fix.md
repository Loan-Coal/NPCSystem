# EXP-93 — Fix BribeScene → HAS_REPUTATION_WITH

**Phase:** 2 · **Effort:** S · **Deps:** none
**Touches:** `demo_game/run_scenes.py`, `demo_game/tests/test_action_workers.py`, `demo_game/tests/test_spread_rumor_worker.py`
**Does NOT touch:** `demo_game/run.py` (SCENES list already has BribeScene, no registration needed), `demo_game/client.py`

---

## Problem

ISSUE-060: `BribeScene.execute()` (`run_scenes.py:239`) calls
`runner.client.put_npc_reputation(player_id, faction_id, standing)`, which upserts a
`STANDS_WITH` edge. `STANDS_WITH` is contractually `faction→faction`; `player_demo` is
a `Character`, not a `Faction`. The edge service resolves the source as
`(:Faction {id:"player_demo"})`, finds nothing, raises `NodeNotFoundError` → HTTP 404.
ACT 3 aborts on every live `make demo-run`.

The correct mechanism is `HAS_REPUTATION_WITH` (Character→Faction), exposed via
`runner.client.adjust_npc_reputation(character_id, faction_id, delta, location_id, tick_id)`.

---

## Fix

### `demo_game/run_scenes.py` — BribeScene.execute()

1. Add module-level constant `_BRIBE_LOCATION: str = "loc_tavern"` (no magic strings; lira_fence
   lives in loc_tavern per `NPC_LOCATION_MAP` in constants.py).

2. Replace the `put_npc_reputation` call with `adjust_npc_reputation`. The current code
   computes `new_standing = min(_STANDING_CAP, current + BRIBE_STANDING_GAIN)` then sets
   the absolute value. `adjust_npc_reputation` accepts a delta and clamps server-side, so
   pass `BRIBE_STANDING_GAIN` as delta directly.

3. Get `tick_id` the same way `PropagatedReputationAct.execute()` does (run_scenes.py:403-404):
   ```python
   clock = runner.client.get_clock_state()
   tick_id: int = clock.get("data", {}).get("current_tick", 1)
   ```

4. The `current` standing fetch from `get_npc_reputation` can be kept for the print output
   (before/after), or dropped — keep it only if it stays within the 40-line function limit.

5. The `get_npc_reputation` call and the `_STANDING_CAP` cap computation are no longer
   needed for the write path (server clamps). Remove `_STANDING_CAP` constant if no other
   code uses it; otherwise leave it.

Resulting call:
```python
result = runner.client.adjust_npc_reputation(
    self.player_id, self.faction_id, BRIBE_STANDING_GAIN, _BRIBE_LOCATION, tick_id
)
```

### `demo_game/tests/test_action_workers.py` — TestBribeWorker

ISSUE-066 (bribe half): `test_bribe_ok_falls_back_to_put_when_no_tick` fails with
`TypeError: cannot unpack non-iterable NoneType object`. This test was written for the
old `put_npc_reputation` path. After this fix:

- Rename test to `test_bribe_ok_uses_adjust_reputation_with_tick`.
- Mock `get_clock_state` returning `{"data": {"current_tick": 5}}`.
- Assert `adjust_npc_reputation` is called with the correct args `(player_id, faction_id, BRIBE_STANDING_GAIN, _BRIBE_LOCATION, 5)`.
- Remove any mock/assertion on `put_npc_reputation`.

### `demo_game/tests/test_spread_rumor_worker.py`

ISSUE-066 (spread-rumor half): `test_falls_back_to_tick_zero_when_clock_unavailable`
fails with same error pattern. Investigate whether this is the same clock-unpacking bug
(the test may mock the clock return differently than the code expects). Fix the mock to
return a dict shaped like `{"data": {"current_tick": 0}}` when the clock is unavailable,
matching how the scene code reads it.

---

## TDD checklist

Write a failing test first before touching run_scenes.py:

1. `test_bribe_scene_calls_adjust_npc_reputation` — happy path:
   - Mock `get_npc_reputation` → `[{"faction_id": "thieves_guild", "standing": 0}]`
   - Mock `get_clock_state` → `{"data": {"current_tick": 3}}`
   - Mock `adjust_npc_reputation` → `{"data": {"standing": 15}}`
   - Call `BribeScene(...).execute(runner)`
   - Assert `adjust_npc_reputation` called with `("player_demo", "thieves_guild", 15, "loc_tavern", 3)`
   - Assert `put_npc_reputation` NOT called

2. `test_bribe_scene_skips_when_insufficient_gold` — edge case (already existed, keep passing)

Run `make test-demo` after changes; expect ISSUE-066 bribe failures gone.

---

## Issues to close

- Mark ISSUE-060 FIXED.
- Mark ISSUE-066 FIXED for the bribe half; update if spread_rumor half is also fixed.

---

## Pre-merge checklist

- [ ] All new tests pass
- [ ] No file exceeds 300 lines (run_scenes.py has DEC-051 waiver)
- [ ] Every new public function/class has docstring
- [ ] No layer rule violations
- [ ] Deferred work in ISSUES.md
- [ ] ISSUES.md updated (close ISSUE-060, ISSUE-066)
