# EXP-224 — Mood-contagion visualiser (demo)

**Goal / rationale:** Mood contagion runs in the engine (one NPC's mood influences a neighbour's) but the
demo's emotion panel shows a single NPC, so contagion is invisible. A two-NPC view makes contagion
legible. Pure demo-side.

**First slice (your scope):** Extend the emotion panel to render a second NPC's mood alongside the first
(a pair view), and extend `EmotionPoller` to track a pair. **Do NOT edit `demo_game/ui/game_window.py`**
(the poller's instantiation site is reserved for another item this batch; make the poller accept an
optional second NPC with a safe default so existing single-NPC callers are unaffected).

**Current state (verified):**
- `demo_game/ui/emotion_panel.py` — renders a single NPC's mood. Add a second row/section for a paired NPC.
- The `EmotionPoller` (in a `*_poller.py`) tracks one NPC. Extend it to optionally track a second NPC
  (default None → behaves exactly as today). Keep the constructor back-compatible so the existing
  game_window instantiation still works untouched.

**Files:**
- EDIT `demo_game/ui/emotion_panel.py` — two-row contagion section (first NPC + paired NPC); graceful when
  no pair is set (render single, as today).
- EDIT the emotion poller file (`demo_game/*_poller.py` containing `EmotionPoller`) — optional second NPC,
  back-compatible default. Do NOT edit game_window.py.
- NEW/EXTEND test: `demo_game/tests/` — `test_emotion_panel_renders_pair` (two NPC moods rendered);
  `test_emotion_poller_pair_optional` (single-NPC behavior unchanged when no pair).

**Graph/API surface:** none — demo-side, consumes existing emotion endpoint. No schema.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema. Keep the
poller constructor back-compatible (no game_window change needed).

**Test plan (RED first):** panel with two moods → both rendered; poller with no pair → single-NPC
unchanged. Watch fail, implement. Run: `pytest demo_game/tests/ -k 'emotion_panel or emotion_poller' -q`.

**Done when:** the emotion panel can show a contagion pair; poller optionally tracks a pair (back-compat);
tests pass; no `src/` import; no game_window edit.
