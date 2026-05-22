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

---

## [2026-05-21] client.py exceeds 300-line limit — single-class cohesion exception

**Context:** P2.2 adds 10 new methods to `EngineClient` (write, typed-write, and
convenience wrappers). The file grows from 273 to ~530 lines, exceeding the 300-line
hard limit in `CLAUDE.md`.

**Options considered:**
- Option A: Keep all methods in `client.py` — single class, single file.
- Option B: Split into `client.py` (reads) + `client_write.py` (writes) with inheritance.
- Option C: Composition — `EngineClient` holds a `_WriteClient` sub-object.

**Decision:** Option A. Single class in one file. Add this DECISIONS.md entry as
required by CLAUDE.md for exceptions.

**Rationale:** `EngineClient` has exactly one cohesive purpose — wrap every NPC Engine
HTTP endpoint used by the demo game. Splitting it would force callers (seed.py, game_window.py,
fetcher.py) to import two types for what is conceptually one thing. The CLAUDE.md exception
clause exists precisely for this case ("if a split would be artificial").

**Consequences:**
- `demo_game/client.py` stays a single file even as it grows beyond 300 lines.
- If it exceeds 600 lines, revisit and consider a domain-based split (graph/ vs typed/).

**Cross-phase?** No — demo game only.

---

## [2026-05-21] put_world_state / put_npc_reputation added in P2.2 (not P2.1)

**Context:** The P2.1 spec listed `put_world_state` and `put_npc_reputation` as
`EngineClient` methods but they were not implemented. P2.2 does not strictly need them
(seed.py uses `upsert_node` and `upsert_edge` directly), but P2.5 needs them for the
war-trigger UI button.

**Decision:** Add in P2.2 as thin wrappers over the general write methods. This closes
the P2.1 spec gap and leaves P2.5 with a clean named API to call.

**Consequences:** P2.5 can call `client.put_world_state("war", ["northern_war"])` without
importing or knowing about the underlying graph endpoint shape.

**Cross-phase?** No — the methods are convenience wrappers; the underlying endpoints are stable.

---

## [2026-05-21] Edge type corrections discovered during P2.2 live seed run

**Context:** `subphases.md` specified NPC-NPC relations and faction-faction antagonism
using edge types that turned out to be wrong schema (wrong node type constraints).
Discovered via HTTP 404/422 errors during the P2.2 live seed run against the engine.

**Options considered:** N/A — factual schema corrections, not design choices.

**Decision:** Use the actual enforced schema. Correct seed.py and document for P2.3–P2.4.

| subphases.md plan | Actual schema | Change made |
|---|---|---|
| `mira STANDS_WITH old_henryk` (NPC-NPC trust) | `STANDS_WITH` is Faction→Faction only | Changed to `RELATES_TO` (trust/affection/fear/relevance_score/interaction_count/last_updated_at) |
| `lira KNOWS_ABOUT aldric` (NPC-NPC knowledge) | `KNOWS_ABOUT` is Character→Event only | Changed to `lira RELATES_TO aldric` + `captain_sorn KNOWS_ABOUT northern_war_begins` |
| `merchants_guild OPPOSES thieves_guild` (faction antagonism) | `OPPOSES` is Character→Character only | Changed to `STANDS_WITH` with negative standing integer (e.g. -60) |
| `RELATES_TO trust: -20` (negative trust) | `trust` field is 0–100 (no negatives) | Changed to `trust: 10, fear: 30` for lira→aldric |

Additional schema facts confirmed during P2.2 (inform P2.4 fetcher.py):
- `MEMBER_OF` requires `joined_at` (ISO timestamp) and `status` (str) fields.
- `world_state` requires `faction_standings` (dict), `time_of_day`, `weather`,
  `last_updated_at`, `last_graph_updated_at` in addition to `epoch`/`active_conditions`.
- Typed admin endpoints (`/v1/admin/beliefs/{id}` etc.) do NOT create BELIEVES/PURSUES
  graph edges — idempotency for typed nodes must use `GET /v1/admin/beliefs/{id}`.

**Consequences:**
- P2.4 fetcher.py must use `RELATES_TO` for NPC-NPC trust, `KNOWS_ABOUT` only for
  Character→Event, `STANDS_WITH` only for Faction→Faction. Node color mapping stays the same.
- `EngineClient.put_npc_reputation(character_id, faction_id, standing)` wraps `STANDS_WITH`
  with int standing — correct for faction-NPC reputation, NOT for NPC-NPC trust.

**Cross-phase?** No — schema is stable; corrections only affect P2.2–P2.4 code.

---

## [2026-05-21] seed.py exceeds 300-line limit — data-heavy single-purpose exception

**Context:** `seed.py` is 589 lines. CLAUDE.md requires a DECISIONS.md entry when
a file exceeds 300 lines and splitting would be artificial.

**Options considered:**
- Option A: Keep all content in seed.py — builders, helpers, data, seed_all.
- Option B: Split `_seed_data.py` (inline dicts) from `seed.py` (logic).

**Decision:** Option A. The inline NPC data (beliefs, goals, memories, secrets)
is inseparable from `_seed_npc_inner_life` — separating them into a second file
creates an import just to pass the same dicts back into the same module. The bulk
is data, not logic. Future maintainers editing the world will want to see data and
calls in one place.

**Consequences:** seed.py stays a single file. If it exceeds 800 lines (e.g., more
NPCs added), extract `_seed_data.py` as a pure data module at that point.

**Cross-phase?** No — demo game seeder only.

---

## [2026-05-22] game_window.py split into game_window.py + widgets.py (P2.3)

**Context:** The P2.3 spec required all of: location bar, NPC list, text input,
scrollable response log, degradation badge, right-panel placeholder, threading,
spinner, and location nav buttons. A single-file implementation would exceed 500
lines — well over CLAUDE.md's 300-line limit, and the split is natural (reusable
widget types vs. application wiring).

**Options considered:**
- Option A: Single `game_window.py` with an exception entry (artificial split avoided).
- Option B: Split into `widgets.py` (widget classes) + `game_window.py` (wiring).
- Option C: Further split into `layout.py` (rects/constants), `widgets.py`, `game_window.py`.

**Decision:** Option B. `demo_game/ui/widgets.py` (277 lines) contains
`InputBox`, `ScrollableLog`, `NpcListWidget`, `DegradationBadge` — four cohesive
widget types with no inter-dependencies. `demo_game/ui/game_window.py` (273 lines)
contains `GameWindow` (event loop, state, wiring to client + dialogue module) and
the module-level `run()` entrypoint.

**Rationale:** The split is along a real seam (reusable presentation primitives
vs. application-specific wiring). Both files are under 300 lines. Option C was
rejected because layout constants are small and belong next to the code that uses them.

**Consequences:**
- `demo_game/ui/widgets.py` is excluded from unit test coverage (Pygame rendering).
- `demo_game/ui/game_window.py` is excluded from unit test coverage (same reason).
- If either file grows beyond 300 lines in P2.4 (graph panel wiring), re-evaluate.

**Cross-phase?** No — demo game UI only.

---

## [2026-05-22] P2.3 spec field-name corrections (dialogue response schema)

**Context:** P2.3 spec text used field names that do not match the actual engine
`DialogueResponse` schema. Discovered by reading the engine source before writing
the TDD tests.

**Options considered:** N/A — factual corrections, not design choices.

**Decision:** Use actual engine field names throughout. Map to readable names in
`DialogueTurn` dataclass.

| Spec text | Actual engine field | Resolution |
|---|---|---|
| `npc_text` (extract) | `npc_response: str` | `parse_dialogue_response` reads `raw["npc_response"]` → `DialogueTurn.npc_text` |
| `emotion` (extract) | No `emotion` field | Map from `mood_update: str \| None`; fall back to `facial_expression["type"]`. Logged as ISSUE-020. |
| `FULL / GRAPH_ONLY / CANNED` (badge) | `"full" / "graph_only" / "canned"` (lowercase) | Colour map uses lowercase keys. Badge label uppercased for display only. |
| `post_dialogue(npc_id, player_input)` | `post_dialogue(player_id, npc_id, player_message, ...)` | Added `DEMO_PLAYER_ID = "player_demo"` to `DemoConfig`. Used in all dialogue calls. |

**Consequences:** `dialogue.py` and `test_dialogue_logic.py` use actual field
names. `build_dialogue_payload` includes `player_id` and `location_id` (not in
original spec) for richer NPC context.

**Cross-phase?** No — field name corrections are stable. Engine schema is frozen.

---

## [2026-05-22] P2.4 — GraphPoller extracted to graph_panel/poller.py

**Context:** P2.4 adds ~60 lines of polling thread logic (fetch, delta countdown, render, lock).
Adding this to `game_window.py` would push it from 273 to ~340 lines, violating the 300-line limit.

**Options considered:**
- Option A (chosen): Extract `GraphPoller` class to `demo_game/graph_panel/poller.py`. game_window.py creates and starts it; the split follows a real seam (reusable polling logic vs. app-specific UI wiring).
- Option B: Inline everything into game_window.py and log a DECISIONS.md exception. Rejected — the seam is real and the extraction is clean.

**Decision:** Option A. `GraphPoller` in `poller.py`. game_window.py stays at 290 lines.

**Consequences:** `graph_panel/__init__.py` public surface now includes `GraphPoller`. Same pattern as the game_window → widgets split in P2.3.

**Cross-phase?** No.

---

## [2026-05-22] P2.4 — render_snapshot returns pygame.Surface, does not accept one

**Context:** The P2.4 stub had signature `render_snapshot(snapshot, surface: object, delta=None) -> None`. Option A rendering (FigureCanvasAgg → buffer → pygame surface) *creates* a surface from the matplotlib canvas; it does not paint onto an existing one.

**Options considered:**
- Option A (chosen): `render_snapshot(snapshot, width, height, *, highlighted_edges) -> pygame.Surface`. Caller blits the returned surface; renderer is stateless and has no coupling to the caller's screen.
- Option B: Pass an existing surface as a target (old stub signature). Requires the caller to pre-allocate the right size, adds coupling, doesn't match the frombuffer conversion pattern.

**Decision:** Option A. Stub was wrong; corrected for implementation.

**Cross-phase?** No.

---

## [2026-05-22] P2.5 — game_window.py exceeds 300 lines after W/C key binding

**Context:** P2.5 adds W/C key handlers + status overlay to `GameWindow`. File grows
from 290 lines to 326 lines, exceeding CLAUDE.md's 300-line hard limit.

**Options considered:**
- Option A (chosen): Keep everything in `game_window.py` with this DECISIONS.md entry.
- Option B: Extract `_handle_key`, `_set_status`, `_draw_status_overlay`, and overlay state
  into `demo_game/ui/key_bindings.py`. Rejected — extracting two private methods, one private
  draw helper, and two state fields into a separate file is more artificial than the overage.
  `GameWindow` is still one cohesive class with one responsibility.

**Decision:** Option A. Same justification as P2.2 (seed.py at 589 lines), P2.3 (client.py),
and P2.4 (GraphPoller extracted only because it was a natural full class). The 300-line spirit
is "avoid unrelated code in one file" — not the case here. All added lines belong to GameWindow.

**Consequences:** `game_window.py` stays a single file. If it exceeds 400 lines, extract all
drawing helpers (`_draw_location_bar`, `_draw_right_panel`, `_draw_nav_bar`,
`_draw_status_overlay`) to `demo_game/ui/drawing.py`.

**Cross-phase?** No — demo game only.

---

## [2026-05-22] P2.4 — Belief + Goal nodes synthesized via admin endpoints

**Context:** `GET /v1/graph/edges/BELIEVES` and `GET /v1/graph/edges/PURSUES` return empty (confirmed P2.2). Both `GET /v1/admin/beliefs/{char_id}` and `GET /v1/admin/goals/{char_id}` return 200 with data.

**Decision:** `fetch_snapshot` calls `get_beliefs(char_id)` and `get_goals(char_id)` for each fetched Character node, synthesizing virtual `GraphNode(node_type="Belief"/"Goal")` and virtual `GraphEdge(edge_type="BELIEVES"/"PURSUES")`. `get_goals()` added to `client.py` (thin wrapper matching `get_beliefs` pattern).

**Consequences:** Each poll makes 5 extra GET calls (one per NPC). On a 5-second interval this is negligible. Inner life appears in the graph as gold (Belief) and amber (Goal) satellite nodes.

**Cross-phase?** Affects P2.5 demo — belief/goal changes will be visible in the live graph.
