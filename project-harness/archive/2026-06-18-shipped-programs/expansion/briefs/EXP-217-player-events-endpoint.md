# EXP-217 — Player-observable event summary endpoint

**Goal / rationale:** Integrators (and the demo) have no clean way to read "what just happened" for a
player — events live in the graph but aren't exposed. A read endpoint serves the Unity/Unreal SDK story
and the demo's event feed. Serves BUSINESS_INTENT "clean HTTP API for studios."

**First slice (your scope):** A new graph reader for recent player-observable events + a new GET route
returning them. Read-only, layer-clean (api → graph).

**Current state (verified):**
- No `src/npc_engine/api/routes/player_events.py` exists; no `GET /player/{id}/events` (or similar) route.
- Events are written/queried via existing event modules in `src/npc_engine/graph/` (look at
  `graph/event_queries.py` if present, or the nearest event reader) and the event node type. Add a reader
  that returns the most recent N events relevant to a player (by witnessed/known relationship — match an
  existing event-read pattern). Do NOT invent a new node/edge; use existing event schema.

**Files:**
- NEW or EXTEND `src/npc_engine/graph/event_queries.py` — `async get_recent_player_events(session,
  player_id, limit)` returning typed event rows. Graph layer; module docstring with `Does NOT:` +
  `Dependencies injected:`.
- NEW `src/npc_engine/api/routes/player_events.py` — `GET` route returning the events via a Pydantic
  response model. Register it where routes are wired (follow an existing route module's registration;
  if registration is in `api/routes/__init__.py` or `main.py`, add it there — that's the only shared file
  you may touch, and confirm no other item in this batch touches it).
- Auth: every route except `GET /health` passes through `auth/middleware.py` — follow the existing
  route pattern (do not bypass auth). Cap `limit`.
- NEW test: `tests/unit/test_player_events_route.py` (or integration per pattern) — happy path + empty.

**Graph/API surface:** new GET route + new graph reader; Pydantic response model; no schema change.

**Architecture fit:** new-file-add (route + graph reader). Layer api → graph (allowed); no LLM. No schema.

**Test plan (RED first):** with a mocked reader returning events, assert the route returns them (200,
typed body); empty → 200 empty list. Watch fail, implement. Run: `pytest tests/unit/ -k player_events -q`.

**Done when:** `GET` returns recent player-observable events (typed, auth'd, capped); reader + route +
test exist; no schema change.
