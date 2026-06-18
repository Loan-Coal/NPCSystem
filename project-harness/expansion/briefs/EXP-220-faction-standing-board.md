# EXP-220 — Faction standing board (demo)

**Goal / rationale:** Faction standings are seeded and live but never shown — the political layer is
invisible in the demo. A standing board surfaces faction relationships at a glance. Pure demo-side.

**First slice (your scope):** Add an `EngineClient.get_faction_standings()` wrapper + a FACTION tab/panel
in the demo right panel that renders faction standings. **Render on-demand only — do NOT add a live
poller and do NOT edit `demo_game/ui/game_window.py`** (poller wiring is slice 2; game_window is reserved
for another item this batch).

**Current state (verified):**
- `demo_game/ui/right_panel.py` — `RightPanel` enum has POLITICS but no FACTION tab (POLITICS shows
  pledges/leverage). Add a `RightPanel.FACTION` value + route to the new panel. (EXP-208 added
  `RightPanel.RETRIEVAL` here — follow that exact pattern; this is the only existing UI file you edit
  besides adding the new panel + the client method.)
- `demo_game/client.py` — no `get_faction_standings`. Add a GET wrapper for the faction-standings route
  (confirm the route path against `src/npc_engine/api/routes/factions.py` — read-only).

**Files:**
- EDIT `demo_game/client.py` — `get_faction_standings()` (graceful on non-200 → empty/None).
- NEW `demo_game/ui/faction_board.py` — panel widget rendering standings (faction pairs + standing).
- EDIT `demo_game/ui/right_panel.py` — `RightPanel.FACTION` + draw branch. Do NOT touch game_window.py.
- NEW/EXTEND test: `demo_game/tests/` — `test_faction_board_renders_standings` (mock payload → rendered;
  empty → graceful).

**Graph/API surface:** none new — consumes existing factions route. Demo-side.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema.

**Test plan (RED first):** mock `get_faction_standings` → assert the panel renders standings; empty →
graceful. Watch fail, implement. Run: `pytest demo_game/tests/ -k faction -q`.

**Done when:** a FACTION tab shows faction standings; test passes; no `src/` import; no game_window edit.
