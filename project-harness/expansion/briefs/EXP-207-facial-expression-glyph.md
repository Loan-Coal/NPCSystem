# EXP-207 — Facial-expression glyph rendering (demo)

**Goal / rationale:** The dialogue response already carries a `facial_expression` (parsed in the demo),
but the UI never shows it — so the NPC's emotional read is invisible. Rendering a small glyph makes
emotion legible at a glance. Pure demo-side polish; data already parsed.

**First slice (your scope):** Render a glyph/emoji for the NPC's current `facial_expression` in the left
panel portrait zone, driven by a small `EXPRESSION_GLYPHS` mapping. No engine/API change.

**Current state (verified):**
- `demo_game/game_controller.py:312` — `facial_expression` is already parsed from the dialogue response;
  trace how it reaches the panel (controller state / NPC view model) before rendering.
- `demo_game/ui/left_panel.py` — the left/portrait panel; it does NOT render `facial_expression` and
  there is no `EXPRESSION_GLYPHS` dict. Add the mapping + render.

**Files:**
- EDIT `demo_game/ui/left_panel.py` — add a module-level `EXPRESSION_GLYPHS: dict[str, str]` (named
  constant, map known expressions → glyph; unknown/None → neutral default, no crash) and draw the glyph
  in the portrait zone. Keep functions ≤40 lines, nesting ≤3.
- NEW/EXTEND test: `demo_game/tests/` — `test_left_panel_renders_expression_glyph` (given an NPC view
  state with a known `facial_expression`, assert the mapped glyph is drawn; unknown/None → neutral
  default, no crash).

**Graph/API surface:** none — demo-side, consumes the already-parsed field.

**Architecture fit:** pure demo-side edit (`demo_game/` — zero `src/npc_engine` imports). No schema.
If `facial_expression` is not actually reachable in `left_panel.py`'s draw inputs, thread it through the
existing panel-state object (do NOT import from `src/` or reach into the controller's internals beyond
the existing view-model).

**Test plan (RED first):** construct the panel's NPC view state with `facial_expression="angry"` (or a
real value), assert the mapped glyph appears; an unknown value → the neutral default. Watch fail,
implement. Run: `pytest demo_game/tests/ -k left_panel -q` (or the panel's test module).

**Done when:** the left panel shows an expression glyph for the NPC; test passes; unknown/None handled;
no `src/` import.
