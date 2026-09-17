
## 2026-09-16 15:17:11 — phase T1

**FINDINGS - T1 Phase Review**

1. **T1.1 logic redundancy**: `_poll_for_disconnect` checks for `msg.get("type") == "websocket.disconnect"` (line 191) but Starlette signals WebSocket disconnect via exception, not message type—this condition is unreachable. The fix still works (disconnect raises exception → propagates → caught), but the check is dead code.

2. **T1.1 nesting depth claim unmet**: Commit says extracted `_poll_for_disconnect` "keeps nesting within the 3-level limit," but the while loop body contains `if await _poll_for_disconnect(...)` at level 4 (function → try → while → if). Same depth as before extraction.

3. **T1.2 seed fix incomplete**: Army repositioning (iron_legion: loc_guard_barracks → loc_north_gate) prevents tick-0 defeat via its location change, but the test only validates the seed state at tick 0. Missing verification that the new `evt_21_iron_legion_advance` event (which replaces military engine's Act 5 behavior) actually fires and uses the events engine—test doesn't confirm events engine processes it.

4. **T1.2 dependencies cleanup verified**: No remaining imports of `engines.military`, `graph.military`, or wiring sites missed. All factory singletons (`get_military_engine`, `MilitaryEngine` type imports) removed cleanly.

5. **T1.1 test isolation concern**: Mock `websocket.receive = AsyncMock(side_effect=WebSocketDisconnect())` bypasses actual Starlette WS behavior. Test validates slot management but not that the fix works with real WebSocket implementations or actual message receive loops.

## 2026-09-17 21:29:53 — phase T3

## Findings

1. **ISSUE-354 contradicts T3.3 completion**: The issue documents `GET /v1/admin/factions/{id}/standings` returning 500 due to response model mismatch (Cypher returns dict, model expects string). Task T3.3 requires "the kept faction and treaty read paths still return data" — a 500 error is a validation failure, not a pass. Deferring it because the client "degrades gracefully" misses that the endpoint itself is broken at the API contract level.

2. **Deferred work not isolated to ISSUES.md**: The issue correctly lives in `ISSUES.md`, but the task tick in `ROADMAP.md` (T3.3) should probably include a note linking back to ISSUE-354 rather than silently marking the validation complete when a read path is non-functional.

3. **Pre-existing diagnosis is correct but incomplete**: The issue traces the root cause correctly (`CYPHER_LIST_STANDINGS` returns `properties(b)` instead of `b.id`), but doesn't note whether this was supposed to be deleted in T3.2 or is a kept service. If it's kept, the response model is the bug; if it was supposed to be deleted, that's a gap in T3.2.

4. **Response validation error not logged when found**: ISSUE-354 cites a `ResponseValidationError` from FastAPI, which suggests active testing of the live stack occurred. The finding was correctly logged, but the task completion marker doesn't reflect that validation caught a failure.

5. **No code changes in this commit**: The commit only logs a finding and ticks tasks. The actual T3.2 deletion work is in the prior commit (`68e796bc`). Verify that prior commit removed `treaty` and `faction_politics` engines cleanly without leaving dangling callers.

## 2026-09-17 23:20:38 — phase T4

Looking at the T4.2 commit diff (the only T4 commit in the latest history), I've identified concrete issues:

## Findings

1. **Quote detection limited to double quotes** (`check_engine_census.py:147`): The `_tick_name_present()` function searches for tick names only with double quotes: `r'"' + re.escape(tick_name) + r'"'`. If `tick_scheduler.py` uses single quotes (`'gossip'`), the gate will incorrectly fail with "tick name not found" for valid engines.

2. **Substring matching false positive with overlapping engine names** (`check_engine_census.py:145`): The regex pattern `r"engines\." + re.escape(dir_name)` uses substring matching. The engine `"quest"` (non-tick) will incorrectly match imports of `"quest_generation"` (tick engine). If only `quest_generation` is imported but `quest` is checked, the gate will falsely report `quest` as imported.

3. **Empty/dead engine directories pass classification** (`check_engine_census.py:220-235`): The script verifies engines are classified and referenced but never checks that directories contain actual code. An empty directory classified as a tick engine could pass if its tick name exists in the scheduler, hiding dead code.

4. **DIR_TO_TICK_NAMES mappings lack validation** (`check_engine_census.py:58-77`): The tick name mappings (e.g., `"need" → ["need_decay"]`) are manually maintained. Incorrect or stale mappings only fail when the gate runs against the live scheduler—no early detection.

5. **ROADMAP.md entry marked done but dependencies unclear**: T4.2 is marked complete but doesn't verify that other T4 phases (T4.1 deletion, T4.3 refactor) completed successfully or that their changes don't invalidate the census gate assumptions.

**All functions comply with file size, length, docstring, and type annotation rules.**
