# EXP-208 — Retrieval-explainer panel (demo)

**Goal / rationale:** The engine has a live retrieval-debug endpoint, but to a buyer the LLM looks like a
black box — they can't see *why* an NPC said what it did. A demo panel that shows the retrieved context
items (and their scores) makes the "grounded, explainable memory" moat visible. Pure demo-side.

**First slice (your scope):** Add an `EngineClient.get_retrieval_debug()` wrapper for the existing
`GET /v1/admin/debug/retrieval` route and a new RETRIEVAL tab/panel in the demo right panel that renders
the returned retrieved items (key + score/tier). No engine/API change.

**Current state (verified):**
- `src/npc_engine/api/routes/debug_retrieval.py` — the route `GET /v1/admin/debug/retrieval` is already
  implemented (returns the retrieved/ranked context items for an NPC+message). Confirm its exact path,
  query params (npc_id, message?), and response shape before wiring.
- `demo_game/client.py` — `EngineClient` has **no** `get_retrieval_debug` method. Add a thin one
  following the existing GET-wrapper pattern in this file (auth header, base URL, error handling).
- `demo_game/ui/right_panel.py` — the right panel hosts tabbed views via a `RightPanel` enum; there is
  no RETRIEVAL tab. Add the enum value + a panel that renders the debug payload. Follow an existing
  panel (e.g. the memory/gossip panel) for the rendering pattern.

**Files:**
- EDIT `demo_game/client.py` — add `get_retrieval_debug(self, npc_id, message=...)` (or matching the
  route's params) returning the parsed payload; graceful on non-200 (return empty/None, no crash).
- NEW `demo_game/ui/retrieval_panel.py` — a panel widget rendering the retrieved items (key, tier,
  score). ≤300 lines, functions ≤40, nesting ≤3, module + public docstrings.
- EDIT `demo_game/ui/right_panel.py` — add `RightPanel.RETRIEVAL` and route to the new panel. (This is
  the only existing UI file you edit; confirm no other item in this batch touches it — none do.)
- NEW/EXTEND test: `demo_game/tests/` — `test_retrieval_panel_renders_items` (given a mocked debug
  payload, assert the panel renders the item keys/scores; empty payload → graceful empty state).

**Graph/API surface:** none new — consumes existing `GET /v1/admin/debug/retrieval`. Demo-side only.

**Architecture fit:** pure demo-side (`demo_game/` is a REST/WS client with **zero `src/npc_engine`
imports** — do NOT import `src/`). No schema, no engine change.

**Test plan (RED first):** mock `EngineClient.get_retrieval_debug` to return a small items payload;
assert the panel's rendered output includes the item keys/scores; empty → graceful state. Watch fail,
implement. Run: `pytest demo_game/tests/ -k retrieval -q`.

**Done when:** the demo has a RETRIEVAL tab showing the retrieved context items for the current turn;
test passes; no `src/` import; graceful when the endpoint returns nothing.
