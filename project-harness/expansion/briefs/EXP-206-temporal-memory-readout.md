# EXP-206 — Temporal memory readout (demo)

**Goal / rationale:** Phase 26 gave memories temporal cognition (when an event occurred, whether it's
historical), but the demo's memory panel never shows it — so the buyer can't see that NPCs reason about
*time*. Surfacing it makes the "persistent, temporally-aware memory" moat visible. Pure demo-side.

**First slice (your scope):** Render `occurred_at_game_time` and `is_historical` for each memory in the
demo memory panel, alongside the existing vividness/content. No engine or API change — the fields are
already returned by the client.

**Current state (verified):**
- `demo_game/ui/memory_panel.py:134-176` — the memory-block draw renders only `vividness` and `content`;
  it does NOT render the temporal fields.
- `demo_game/client.py` (~`get_memories`, near line 685) already returns memory dicts that include
  `occurred_at_game_time` and `is_historical` (Phase 26 fields). Verify the exact key names against the
  client method before rendering.

**Files:**
- EDIT `demo_game/ui/memory_panel.py` — in the per-memory block draw, add a line/badge showing the
  occurred-at game time and a marker when `is_historical` is true. Keep functions ≤40 lines, nesting ≤3.
  Handle missing/None fields gracefully (older cached memories may lack them → render nothing, no crash).
- NEW/EXTEND test: `demo_game/tests/test_memory_panel.py` (or the existing demo UI test module) —
  `test_memory_block_renders_temporal_fields` (assert the formatted text/surface includes the occurred-at
  value and the historical marker when present, and omits them cleanly when absent).

**Graph/API surface:** none — demo-side only, consumes existing client fields.

**Architecture fit:** pure demo-side edit (`demo_game/` is a REST/WS client with zero `src/npc_engine`
imports — do NOT import from `src/`). No schema, no route.

**Test plan (RED first):** construct a memory dict with `occurred_at_game_time` + `is_historical=True`,
assert the panel's rendered text/lines include them; a dict without those keys renders the same as today.
Watch fail, implement. Run: `pytest demo_game/tests/ -k memory_panel -q` (or the panel's test file).

**Done when:** the memory panel shows occurred-at time + a historical marker; test passes; no `src/`
import; graceful when fields absent.
