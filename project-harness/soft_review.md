
## 2026-09-16 15:17:11 — phase T1

**FINDINGS - T1 Phase Review**

1. **T1.1 logic redundancy**: `_poll_for_disconnect` checks for `msg.get("type") == "websocket.disconnect"` (line 191) but Starlette signals WebSocket disconnect via exception, not message type—this condition is unreachable. The fix still works (disconnect raises exception → propagates → caught), but the check is dead code.

2. **T1.1 nesting depth claim unmet**: Commit says extracted `_poll_for_disconnect` "keeps nesting within the 3-level limit," but the while loop body contains `if await _poll_for_disconnect(...)` at level 4 (function → try → while → if). Same depth as before extraction.

3. **T1.2 seed fix incomplete**: Army repositioning (iron_legion: loc_guard_barracks → loc_north_gate) prevents tick-0 defeat via its location change, but the test only validates the seed state at tick 0. Missing verification that the new `evt_21_iron_legion_advance` event (which replaces military engine's Act 5 behavior) actually fires and uses the events engine—test doesn't confirm events engine processes it.

4. **T1.2 dependencies cleanup verified**: No remaining imports of `engines.military`, `graph.military`, or wiring sites missed. All factory singletons (`get_military_engine`, `MilitaryEngine` type imports) removed cleanly.

5. **T1.1 test isolation concern**: Mock `websocket.receive = AsyncMock(side_effect=WebSocketDisconnect())` bypasses actual Starlette WS behavior. Test validates slot management but not that the fix works with real WebSocket implementations or actual message receive loops.
