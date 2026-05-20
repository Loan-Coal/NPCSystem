# Phase 2 — Demo Game Skeleton + Graph Debug Visualization

## Goal

Build a minimal playable demo game in `demo_game/` that calls the engine via
the FastAPI gateway. The game shows a few locations, a few NPCs, click-to-talk
dialogue, and — critically — a side panel that visualizes the live graph
(gossip spreading, relationships forming, rumors mutating). The side panel is
the primary mentor evaluation surface: it makes the invisible engine state
visible without requiring the mentor to read code.

## Why This Phase Exists

Phase 1 makes the engine correct. Phase 2 makes it visible. A mentor seeing raw
JSON responses in a terminal will not understand the system's depth. A mentor
seeing a graph panel update in real time as gossip spreads — that is the demo.
The demo game also exercises the API surface end-to-end from a real client
process, exposing integration bugs that unit tests cannot catch.

## Scope (In)

- `demo_game/` Python package (same repo, not a separate repo).
- Calls engine exclusively via HTTP to `localhost:8000`. No imports from
  `src/npc_engine/`.
- Minimal 2D interface: at least 2 locations, at least 3 NPCs (one faction
  each, one neutral), click-to-move and click-to-talk.
- Text dialogue display: player types a message, NPC response rendered.
- **Side panel: live graph visualization.** Polls `GET /v1/graph/nodes/` and
  edge endpoints. Renders the graph with nodes colored by faction/type and
  edges weighted by trust/fear. Updates every N seconds (configurable).
  Shows relationship delta events (new edges, trust changes) as they happen.
- Seed script: `demo_game/seed.py` creates the demo world via API calls
  (locations, factions, NPCs, WorldState epoch) without touching Neo4j directly.
- At least one scripted gossip event: trigger a war or faction conflict, watch
  it propagate across NPCs visible in the side panel.
- Evolve `docs/DEMO.md` to reflect the new demo game setup and flow.

## Scope (Out)

- **No combat, inventory, or skill mechanics.** The demo needs dialogue and
  gossip, not a full RPG.
- **No Phase 7 L engine exposure** (detective/political/social/strategy) unless
  Q4 from `open_questions.md` is resolved with "yes, expose them."
- **No persistent save state.** The demo is stateless across restarts (seed
  script re-creates the world).
- **No authentication UI.** The demo uses the dev API key hardcoded in `.env.dev`.
- **No audio or animation.** Text only.
- **No multi-player.** Single-player demo only.
- **No production deployment.** Runs locally only.

## Entry Criteria

- Phase 1 `handoff.md` is signed off.
- `make scenarios` passes with LLM judge gate (war scenario: PASS).
- Phase 1 baseline scenarios show correct world-state-grounded responses.
- The `GET /v1/graph/nodes/{node_type}` and edge read endpoints are confirmed
  working (smoke test or Phase 1 scenario coverage).

## Exit Criteria

1. **[HARD]** All pre-Phase-2 tests pass. (Note: `demo_game/` has its own test
   directory; it is excluded from the engine test suite counts.)
2. **[HARD]** `demo_game/` has unit tests for: seed script data shapes, HTTP
   client wrappers, graph polling logic. New tests pass.
3. **[HARD]** War scenario run from the demo game: gossip event seeded → graph
   panel updates → player talks to an NPC who knows about the war → response
   reflects war state. Phase owner records this in `handoff.md`.
4. **[HARD]** Phase owner runs the complete demo flow and signs off in `handoff.md`.
5. **[HARD]** LLM judge runs on at least one demo-game-initiated dialogue turn
   and returns PASS.
6. **[SOFT]** Coverage on `demo_game/` ≥ 78% (excluding UI rendering code).

## Affected Modules

- **New directory:** `demo_game/` — all new code
- `docs/DEMO.md` — evolve to new demo game setup
- `src/npc_engine/api/routes/` — no code changes; smoke test any routes the
  demo game relies on that weren't previously covered

## Docs to Evolve

- `docs/DEMO.md` — replace the `make demo-video` pytest scenario with the
  new demo game setup (`make demo` → starts engine + demo game), scripted flow
  description, side panel explanation.

## Demo Impact

This is the phase that creates the primary mentor demo artifact. After Phase 2,
the demo is: start `make demo`, open a window, click around, watch gossip spread
in the graph panel in real time, talk to NPCs whose responses reflect what they
know. Mentors can try it themselves.

## Risks

1. **Graph visualization library choice** — mitigation: use a simple Python
   approach (e.g., `pyvis` for static snapshots, or a minimal websocket + D3
   in a single HTML page). Do not over-engineer; the graph panel needs to be
   readable, not beautiful.
2. **Graph polling latency** — the graph panel polls the API. If Neo4j is slow
   under load, the panel lags. Mitigation: poll at 5s intervals; show a
   "last updated" timestamp so lag is visible, not silent.
3. **Seed script creates duplicate nodes on restart** — mitigation: seed script
   checks for existing nodes (via GET before POST) or uses idempotency keys.
4. **Demo game exercises API surface gaps** — mitigation: log all 4xx/5xx
   responses from the demo game; fix gaps as they appear. These are likely to
   surface edge cases in routes not hit by unit tests.

## Estimated Effort

TBD — fleshed out in P2.0 at phase start.

Rough range: 4–6 half-days. The graph visualization panel is the unknown; a
simple static-snapshot approach is 1 half-day; a live-updating panel is 2–3.

If I have to cut: cut the click-to-move UI (use a hardcoded location, just
show the dialogue and graph panel). Do not cut the graph panel — that is the
demo's primary visual.
