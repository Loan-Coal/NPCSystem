# EXP-225 — Proactive window surface (demo, PARTIAL)

**Goal / rationale:** The interactive window already shows an NPC-initiative bubble (`NpcInitiativePoller`
+ bubble), but it doesn't pull the player toward responding — the intent NPC isn't highlighted and the
input box isn't primed. Closing that loop makes NPC initiative feel interactive. Pure demo-side.

**First slice (your scope):** When a proactive intent bubble appears, highlight the initiating NPC in the
list and pre-fill the input box to address that NPC, so the player can respond immediately.

**Current state (verified):**
- `demo_game/ui/game_window.py:452-470` (approx) — `NpcInitiativePoller` and the intent-bubble display
  already exist. The gap: on bubble display, the NPC list isn't highlighted and the input box isn't
  pre-filled. This is the ONLY file this item edits (it is reserved to this item in this batch).

**Files:**
- EDIT `demo_game/ui/game_window.py` — in the event loop where the intent bubble is shown, set the active/
  highlighted NPC to the intent's NPC and pre-fill the input box (or focus it addressed to that NPC).
  Keep functions ≤40 lines (extract a helper if the event-loop block grows); nesting ≤3.
- NEW/EXTEND test: `demo_game/tests/` — `test_intent_bubble_highlights_and_prefills` (simulate an intent
  arriving → assert active NPC switches to the intent NPC and input is pre-filled; no intent → unchanged).

**Graph/API surface:** none — demo-side, uses the existing poller/intent. No schema.

**Architecture fit:** pure demo-side (`demo_game/` — zero `src/npc_engine` imports). No schema. Only
`game_window.py` + the test are in scope.

**Test plan (RED first):** drive an intent through the poller/handler → assert highlight + prefill happen;
absent intent → no change. Watch fail, implement. Run: `pytest demo_game/tests/ -k 'game_window or intent' -q`.

**Done when:** an arriving proactive intent highlights its NPC and pre-fills the input; test passes; no
`src/` import; no other file touched.
