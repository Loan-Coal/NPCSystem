# Phase 2 Decisions

<!-- Append entries here as decisions are made during Phase 2 execution. -->
<!-- Never edit or delete prior entries. This is an append-only log. -->
<!-- Format for each entry is shown below. -->

<!--
## [YYYY-MM-DD] Decision title

**Context:** What prompted this decision.
**Options considered:** Brief list.
**Decision:** What was chosen.
**Consequences:** What this commits to or forecloses.
**Cross-phase?** Yes — graduate to project/DECISIONS.md | No — stays here
-->

---

## [2026-05-21] Game window framework — Pygame on host

**Context:** P2.3 requires an interactive window with text input, NPC response
log, degradation badge, and an embedded graph panel. Need to pick the host
process framework before any UI code is written.

**Options considered:**
- Pygame (host process, no Docker) — simple, cross-platform, single process
- Tkinter — no smooth surface blitting for graph panel
- Web app (Flask/FastAPI frontend) — over-engineered for a hackathon demo

**Decision:** Pygame, running as a host-side Python process. Calls
`http://localhost:8000` only. Zero imports from `src/npc_engine/`.

**Consequences:**
- `demo_game/` lives at repo root, not inside `src/`.
- `make demo` invokes `python -m demo_game`, not a Docker service.
- Dependencies (`pygame`, `httpx`, `python-dotenv`) go into
  `demo_game/requirements.txt`, NOT the engine's `requirements.txt`.
- Running on host avoids Docker display forwarding (X11/Wayland on Linux).

**Cross-phase?** No — demo game is a Phase 2 artefact only.

---

## [2026-05-21] Graph panel rendering — Option A (networkx + matplotlib → Pygame surface)

**Context:** P2.4 needs a live graph visualisation in the right panel of the
Pygame window. Three options were on the table (see subphases.md P2.0 step 4).

**Options considered:**
- Option A: networkx layout + matplotlib figure blitted to Pygame surface
- Option B: manual Pygame drawing (manual node/edge coordinates)
- Option C: pyvis HTML file opened in system browser (two windows)

**Decision:** Option A. Use `networkx` spring/Kamada-Kawai layout, render with
`matplotlib.backends.backend_agg.FigureCanvasAgg`, convert the canvas buffer to
a Pygame surface via `pygame.image.frombuffer`, and blit on each poll tick.

**Rationale:**
- Automatic layout is essential: 30–50 nodes across 7 types makes manual
  coordinate assignment impractical.
- matplotlib makes faction-coloured nodes, edge thickness by weight, and dashed
  `KNOWS_ABOUT` arrows trivial.
- Single window is better for a 90-second live demo than two windows (Option C).
- Redraw on poll tick (not every game-loop frame) keeps CPU usage low.

**Consequences:**
- Add `networkx` and `matplotlib` to `demo_game/requirements.txt`.
- `renderer.py` takes a `GraphSnapshot` and returns a `pygame.Surface`.

**Cross-phase?** No — graph panel is demo game only.

---

## [2026-05-21] Corrected graph API type names (P2.0 smoke-test findings)

**Context:** P2.0 smoke-tested all graph endpoints the fetcher (P2.4) and seed
script (P2.2) plan to call. Several names used in `subphases.md` do not match
registered registry names and return HTTP 500.

**Options considered:** N/A — this is a factual correction, not a design choice.

**Decision:** Use the actual registered names in all Phase 2 code. Do not add
registry stubs for the old names — the real types already exist under different
names.

| subphases.md name (planned) | Actual registered name | Verified |
|---|---|---|
| `WorldEvent` (node) | `Event` | `GET /v1/graph/nodes/Event` → 200 ✅ |
| `WorldState` (capital S, node) | `world_state` (lowercase) | `GET /v1/graph/nodes/world_state` → 200 ✅ |
| `TRUSTS` (edge) | `STANDS_WITH` | `GET /v1/graph/edges/STANDS_WITH` → 200 ✅ |
| `FEARS` (edge) | `OPPOSES` | `GET /v1/graph/edges/OPPOSES` → 200 ✅ |
| `HAS_BELIEF` (edge) | `BELIEVES` | `GET /v1/graph/edges/BELIEVES` → 200 ✅ |
| `HAS_GOAL` (edge) | `PURSUES` | `GET /v1/graph/edges/PURSUES` → 200 ✅ |

Confirmed working without correction: `Character`, `Location`, `Faction`,
`Memory`, `Belief`, `Goal` nodes; `KNOWS_ABOUT`, `MEMBER_OF` edges;
`POST /v1/clock/advance` (body: `{}` uses defaults).

Side-finding: unregistered type requests return HTTP 500 (plain text) instead of
404/422 JSON — root cause filed as ISSUE-017.

**Consequences:**
- P2.2 seed.py uses `Event` (not `WorldEvent`) and `world_state` (lowercase).
- P2.4 fetcher uses `STANDS_WITH`, `OPPOSES`, `BELIEVES`, `PURSUES` instead of
  the planned names. Node color mapping updates accordingly.
- No stub routes needed in P2.1 — all required types already exist.

**Cross-phase?** No — type name clarification only. Registry names are stable.
