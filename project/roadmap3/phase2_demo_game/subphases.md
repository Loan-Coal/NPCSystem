# Phase 2 Subphases (Skeleton)

<!-- Skeleton only. Fleshed out in P2.0 at the start of Phase 2,
     using the Phase 1 handoff. Do not add detail speculatively. -->

## P2.0 — Flesh out subphases.md (0.5 half-day)

Read `phase1_prompting_and_retrieval/handoff.md`. Confirm which API routes the
demo game will use. Decide on graph visualization library. Expand each skeleton
subphase into full-detail format. Commit before starting P2.1.

---

## P2.1 — Project scaffold

Create `demo_game/` package structure. HTTP client wrapper for engine API.
`.env.demo` config. Basic `make demo` target.

---

## P2.2 — Seed script

`demo_game/seed.py` creates demo world via API: locations, factions, NPCs,
WorldState. Idempotent (check-before-create). Unit tests for data shapes.

---

## P2.3 — Dialogue UI

Minimal interface: location view, NPC list, text input, NPC response display.
Wire to `POST /v1/dialogue`. Show degradation level in UI.

---

## P2.4 — Graph visualization panel

Poll `GET /v1/graph/nodes/` and edge endpoints. Render graph with faction
coloring and trust-weighted edges. Update on configurable interval (default 5s).
Show "last updated" timestamp.

---

## P2.5 — Gossip trigger + end-to-end demo flow

`POST /v1/clock/advance` or equivalent to trigger gossip tick. Confirm graph
panel shows new KNOWS_ABOUT edges appearing. Walk through scripted demo flow
(war event → gossip spread → NPC dialogue reflects war) from the demo game UI.

---

## P2.6 — Docs + handoff

Evolve `docs/DEMO.md`. Fill in `phase2_demo_game/handoff.md`. Replace
`project/NEXT_SESSION.md`.
