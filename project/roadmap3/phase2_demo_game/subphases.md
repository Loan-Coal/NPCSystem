# Phase 2 Subphases (Full Detail)

<!-- Fleshed out per planning session 2026-05-21.
     Covers P2.0–P2.6. Commit this file before starting P2.1. -->

---

## P2.0 — Flesh out subphases + decisions (0.5 half-day)

**Goal:** Confirm API surface, make and log the two key design decisions (game
window framework, graph panel approach), and smoke-test the graph read endpoints
before any code is written.

**Steps:**

1. Read `project/ISSUES.md`. Note any open items relevant to Phase 2.

2. Read `phase1_prompting_and_retrieval/handoff.md`. Confirm every API route the
   demo game will call and verify each is marked working:
   - `POST /v1/dialogue` ✅ (Phase 1 confirmed)
   - `POST /v1/clock/advance` (requires `CLOCK_MODE=game_driven` — already set in
     `docker-compose.yml` line 70)
   - `GET /v1/graph/nodes/{node_type}` — **must smoke-test**
   - Graph edge read endpoints — **must smoke-test**
   - `POST /v1/admin/...` write endpoints used by seed script

3. Start the engine: `docker-compose up -d`. Then smoke-test the graph read
   endpoints that P2.4 depends on:
   ```
   curl -H "Authorization: Bearer local_dev_secret_changeme" \
        http://localhost:8000/v1/graph/nodes/Character
   ```
   Repeat for: `Location`, `Faction`, `WorldEvent`, `Memory`, `Belief`, `Goal`.
   Also test edge read endpoints (`KNOWS_ABOUT`, `TRUSTS`, `FEARS`, `MEMBER_OF`).
   If any return 404 or are missing, file `ISSUES.md` entry and plan a stub route
   addition in P2.1 before P2.4 begins.

4. **Decide and log in `phase2_demo_game/decisions.md`:**
   - **Game window:** Pygame, running as a host process (not in Docker).
     Calls `http://localhost:8000` only. Zero imports from `src/npc_engine/`.
   - **Graph panel approach** — choose one and log rationale:
     - Option A: networkx layout + matplotlib figure rendered to Pygame surface
       (pure Python, no extra serving layer)
     - Option B: minimal pygame drawing (manual node/edge positions, no layout lib)
     - Option C: pyvis HTML file exported on each poll, opened in system browser
       (side-by-side with Pygame window; simpler render code but two windows)

5. Commit `subphases.md` (this file) before starting P2.1.

**Files to read:**
- `project/ISSUES.md`
- `project/roadmap3/phase1_prompting_and_retrieval/handoff.md`
- `docker-compose.yml` (confirm CLOCK_MODE=game_driven present)

**Files to write:**
- `project/roadmap3/phase2_demo_game/decisions.md` — game window + graph panel
  decisions logged immediately

**Exit check:** `decisions.md` has two entries. Graph endpoint smoke tests all
return 200. `subphases.md` committed.

---

## P2.1 — Project scaffold (0.5–1 half-day)

**Goal:** Create the `demo_game/` package skeleton with a working HTTP client
and test stubs. No real game logic yet.

**TDD discipline:** Write failing `test_client.py` stub tests (import checks,
method signatures) *before* implementing `client.py`.

**Steps:**

1. Create the `demo_game/` package at repo root:
   ```
   demo_game/
     __init__.py
     client.py
     config.py
     seed.py              # empty stub
     ui/
       __init__.py
       game_window.py     # empty stub
     graph_panel/
       __init__.py
       fetcher.py         # empty stub
       renderer.py        # empty stub
     tests/
       __init__.py
       test_client.py
       test_seed.py       # empty stub
       test_fetcher.py    # empty stub
   ```
   Every `__init__.py` must have a module docstring (layer: demo).

2. Write `demo_game/tests/test_client.py` first (failing):
   - Test import succeeds
   - Test `EngineClient` can be instantiated with a base URL
   - Test each public method exists and has correct type signature
   Run `pytest demo_game/tests/test_client.py` — confirm failure is import error,
   not something else.

3. Implement `demo_game/client.py`:
   - Class `EngineClient(base_url: str, api_key: str)`
   - Uses `httpx` (or `requests` if httpx is not installed)
   - Public methods (all return typed dataclasses or dicts):
     - `post_dialogue(npc_id, player_input, explicit_node_ids=()) -> dict`
     - `get_graph_nodes(node_type: str) -> list[dict]`
     - `get_graph_edges(edge_type: str) -> list[dict]`
     - `post_clock_advance() -> dict`
     - `put_world_state(epoch: str, active_conditions: list[str]) -> dict`
     - `put_npc_reputation(char_id: str, faction: str, standing: float) -> dict`
   - All HTTP calls raise `EngineClientError` (custom exception) on 4xx/5xx.
   - Unit tests mock all HTTP calls — no real server needed.

4. Implement `demo_game/config.py`:
   - Loads `.env.demo` via `python-dotenv`
   - Exports: `NPC_BASE_URL`, `NPC_API_KEY`, `DEMO_GRAPH_POLL_INTERVAL`

5. Create `demo_game/.env.demo`:
   ```
   NPC_BASE_URL=http://localhost:8000
   NPC_API_KEY=local_dev_secret_changeme
   DEMO_GRAPH_POLL_INTERVAL=5
   ```
   Add `.env.demo` to `.gitignore` (contains dev key).

6. Add to `Makefile`:
   ```makefile
   demo:          ## Start the demo game (engine must be running: docker-compose up -d)
       python -m demo_game

   demo-seed:     ## Seed the demo world (engine must be running, DB must be empty)
       python demo_game/seed.py
   ```

7. `pytest demo_game/tests/ -q` — all stub tests pass.

**Files to create:**
- `demo_game/` (full structure above)
- `demo_game/.env.demo`

**Files to modify:**
- `Makefile` — add `demo` and `demo-seed` targets
- `.gitignore` — add `demo_game/.env.demo`

**Exit check:** `pytest demo_game/tests/ -q` passes. `python -c "from demo_game.client import EngineClient"` succeeds.

---

## P2.2 — Seed script (1 half-day)

**Goal:** `demo_game/seed.py` creates a rich demo world via HTTP API that
exercises all node types and engines. Idempotent on re-run.

**TDD discipline:** Write failing unit tests for each data-builder function
*before* implementing them. All HTTP calls mocked.

**Steps:**

1. Write `demo_game/tests/test_seed.py` first (failing):
   - Test `build_location_payload(name, description) -> dict` returns correct shape
   - Test `build_faction_payload(...)` returns correct shape
   - Test `build_npc_payload(...)` returns correct shape
   - Test `build_belief_payload(...)` returns correct shape
   - Test `build_goal_payload(...)` returns correct shape
   - Test `seed_all(client)` calls client methods in dependency order
     (factions before NPCs; NPCs before beliefs/goals/memories)
   Run — confirm failures.

2. Implement `demo_game/seed.py` — seeds via `EngineClient` only.
   Zero imports from `src/npc_engine/`. Idempotent: GET-before-POST each entity;
   skip (log a note) if already exists.

   Demo world contents (exercises all engines):
   - **3 locations:** `tavern` (neutral), `market_square` (merchant territory),
     `guard_barracks` (guard territory)
   - **3 factions:** `merchants_guild`, `city_guard`, `thieves_guild` — with
     pairwise trust/fear relations seeded (merchants distrust thieves; guard
     fears thieves; merchants and guard have neutral trust)
   - **5 NPCs:**
     - `mira_innkeeper` — neutral, tavern, archetype `innkeeper`
     - `aldric_merchant` — merchants_guild, market_square, archetype `merchant`
     - `captain_sorn` — city_guard, guard_barracks, archetype `guard_captain`
     - `lira_fence` — thieves_guild, tavern, archetype `fence`
     - `old_henryk` — neutral, market_square, archetype `elder`
   - **Per NPC:** 2 beliefs, 1–2 goals, 1 secret, 2 memories
     (exercises Memory engine and inner-life prompt Rule 7)
   - **1 WorldEvent:** `northern_war_begins` (type=conflict, initially inactive)
   - **WorldState:** `epoch=peace`, `active_conditions=[]`
   - **NPC-to-NPC relations:** mira TRUSTS old_henryk; lira KNOWS_ABOUT aldric;
     captain_sorn FEARS lira (exercises Gossip engine graph state)

   Sync comment at top of file:
   ```python
   # SYNC NOTE: Keep aligned with src/npc_engine/data/api_seeder.py.
   # When either seeder adds a new node type or resource, review the other.
   # See project/DECISIONS.md for the standalone-seeder decision.
   ```

3. Unit tests pass: all data builders, dependency-order check, HTTP mocked.

4. Manual run: `python demo_game/seed.py` on a fresh DB → full world created.
   Re-run → idempotent (no duplicates, no errors).

**Files to create/modify:**
- `demo_game/seed.py` (implement)
- `demo_game/tests/test_seed.py` (implement)

**Exit check:** `pytest demo_game/tests/test_seed.py -q` passes. Manual seed run
creates 5 NPCs, 3 locations, 3 factions, beliefs/goals/memories in Neo4j.

---

## P2.3 — Dialogue UI (1–1.5 half-days)

**Goal:** Pygame game window: location view, NPC list, text input, scrollable
response log, degradation indicator, click-to-navigate.

**TDD discipline:** Write failing tests for dialogue-request wiring
*before* building Pygame widgets.

**Steps:**

1. Write `demo_game/tests/test_dialogue_logic.py` first (failing):
   - Test `build_dialogue_payload(npc_id, player_input) -> dict` returns correct shape
   - Test `parse_dialogue_response(raw: dict) -> DialogueTurn` extracts:
     `npc_text`, `degradation_level`, `emotion`
   - Test degradation level maps to correct badge color
   Run — confirm failures.

2. Implement `demo_game/ui/game_window.py` — Pygame window, split layout:
   - **Left panel (game):** ~60% of width
     - Location bar (top): location name, background tint per location
     - NPC list (middle): clickable rows, highlight active NPC
     - Text input (bottom): typing area, submit on Enter
     - Response log (scrollable): alternating player/NPC messages with names
     - Degradation badge (bottom-right of response area): colored label
       (`FULL` green, `GRAPH ONLY` amber, `CANNED` red)
   - **Right panel (graph):** ~40% of width — placeholder surface for P2.4
   - **Bottom bar:** location navigation buttons

3. Wire dialogue to engine:
   - On Enter: call `client.post_dialogue(npc_id, player_input)`
   - Render NPC response in log
   - Update degradation badge
   - Show spinner/disabled input while waiting (async or threaded call)

4. Wire navigation:
   - Location buttons update active location and reload NPC list
   - NPC list shows NPCs seeded for that location

5. Unit tests for logic layer pass (Pygame rendering excluded from coverage).

**Files to create/modify:**
- `demo_game/ui/game_window.py` (implement)
- `demo_game/tests/test_dialogue_logic.py` (new)

**Exit check:** `python -m demo_game` opens a Pygame window. Player can type a
message to an NPC and see a response. Clicking a location button changes the
active location and NPC list. Degradation badge shows on each response.

---

## P2.4 — Graph visualization panel (1–2 half-days)

**Goal:** Right panel in Pygame window shows the live knowledge graph, updated
on a configurable poll interval. Delta-highlights new edges.

**TDD discipline:** Write failing tests for `fetcher.py` (mock responses, delta
detection) *before* building the renderer.

**Steps:**

1. Write `demo_game/tests/test_fetcher.py` first (failing):
   - Test `fetch_snapshot(client) -> GraphSnapshot` calls correct endpoints
   - Test `GraphSnapshot` contains typed node and edge lists
   - Test `compute_delta(prev, curr) -> GraphDelta` identifies new nodes/edges
     and changed edge weights
   - Test empty → populated snapshot delta
   Run — confirm failures.

2. Implement `demo_game/graph_panel/fetcher.py`:
   - `GraphNode(id, type, label, faction=None)`
   - `GraphEdge(source_id, target_id, type, weight=None)`
   - `GraphSnapshot(nodes: list[GraphNode], edges: list[GraphEdge], fetched_at: datetime)`
   - `GraphDelta(new_nodes, new_edges, changed_edges)`
   - `fetch_snapshot(client: EngineClient) -> GraphSnapshot`:
     - Calls `client.get_graph_nodes(type)` for each: `Character`, `Location`,
       `Faction`, `WorldEvent`, `Memory`, `Belief`, `Goal`
     - Calls `client.get_graph_edges(type)` for each: `KNOWS_ABOUT`, `TRUSTS`,
       `FEARS`, `MEMBER_OF`, `HAS_BELIEF`, `HAS_GOAL`
   - `compute_delta(prev: GraphSnapshot | None, curr: GraphSnapshot) -> GraphDelta`
   - Background polling thread: calls `fetch_snapshot` every
     `DEMO_GRAPH_POLL_INTERVAL` seconds, stores latest snapshot + delta.

3. Implement `demo_game/graph_panel/renderer.py` (using approach decided in P2.0):
   - Renders `GraphSnapshot` onto a Pygame surface
   - Node color by type: Character=blue, Faction=red, WorldEvent=orange,
     Location=green, Memory/Belief/Goal=light grey
   - Edge thickness by weight (trust/fear value where available; else thin)
   - New edges from `GraphDelta`: highlighted yellow for 2 poll cycles then fade
   - "Last updated: HH:MM:SS" text in bottom corner of panel
   - Falls back to "Waiting for data..." if first fetch not yet complete

4. Wire renderer into `game_window.py`: right panel surface updated on each
   game loop tick with the latest rendered snapshot.

5. Unit tests for fetcher + delta detection pass. Renderer excluded from coverage.

**Files to create/modify:**
- `demo_game/graph_panel/fetcher.py` (implement)
- `demo_game/graph_panel/renderer.py` (implement)
- `demo_game/tests/test_fetcher.py` (implement)
- `demo_game/ui/game_window.py` (wire in renderer)

**Exit check:** `pytest demo_game/tests/test_fetcher.py -q` passes. Running the
game with a seeded DB shows nodes in the right panel. After advancing the clock
and triggering gossip, new `KNOWS_ABOUT` edges appear within
`DEMO_GRAPH_POLL_INTERVAL` seconds.

---

## P2.5 — Gossip trigger + end-to-end demo flow + LLM judge (1 half-day)

**Goal:** Wire war/gossip trigger controls, verify the complete scripted demo
flow end-to-end, and write + pass the Phase 2 LLM judge test.

**Steps:**

1. **Add trigger controls to the game UI** (bottom bar or keyboard shortcuts):
   - **"Trigger War" button (or `W` key):**
     Calls `client.put_world_state(epoch="war", active_conditions=["northern_war"])`.
     Shows a brief status overlay: "War epoch activated."
   - **"Advance Clock" button (or `C` key):**
     Calls `client.post_clock_advance()`.
     (`CLOCK_MODE=game_driven` is set in `docker-compose.yml` — no demo-side config needed.)
     Shows: "Clock advanced — gossip tick triggered."
   - Graph panel refreshes on next poll; new `KNOWS_ABOUT` edges should appear.

2. **Write `e2e/scenarios/scenario_demo_game_judge.py`** (new file):
   - Seeds the demo world via API (calls the same endpoints as `seed.py`)
   - Triggers war: sets `WorldState epoch=war`
   - Advances clock once
   - Calls `POST /v1/dialogue` for `captain_sorn` asking about road safety
   - LLM judge asserts: response reflects danger/war state (reuse criteria
     from `test_war_epoch_reflects_danger` in Phase 1)
   - Gate: `JUDGE_MODEL=qwen2.5:14b make eval-llm` must show PASS for this
     test before proceeding to P2.6.

3. **Manual scripted demo run** (record in handoff):
   - `docker-compose up -d` → `python demo_game/seed.py` → `python -m demo_game`
   - Press `W` → press `C` × 2–3
   - Observe graph panel: new `KNOWS_ABOUT` edges appearing
   - Click `captain_sorn` → type "Is it safe to travel north?"
   - Capture response text in `e2e/transcripts/demo_war_baseline.md`
   - Confirm: response reflects war danger; graph panel shows updated edges

**Files to create/modify:**
- `e2e/scenarios/scenario_demo_game_judge.py` (new)
- `demo_game/ui/game_window.py` (add trigger controls)

**Exit check:** `JUDGE_MODEL=qwen2.5:14b make eval-llm` passes including
`scenario_demo_game_judge.py`. Manual demo run transcript saved.

---

## P2.6 — Docs + handoff (0.5 half-day)

**Goal:** Update `docs/DEMO.md`, fill `handoff.md`, close all tracking documents.

**Steps:**

1. **`docs/DEMO.md`** — replace the existing `make demo-video` pytest-scenario
   flow with the new demo game:
   - Prerequisites: Docker Compose, Ollama with `qwen2.5:14b` pulled, Python venv
   - Setup:
     ```bash
     docker-compose up -d
     python demo_game/seed.py     # fresh DB only
     python -m demo_game          # or: make demo
     ```
   - Scripted flow (90-second mentor demo):
     1. Point to the graph panel: "This shows the NPC knowledge graph in real time."
     2. Press `W` → "I just injected a war event."
     3. Press `C` × 2 → "Gossip is spreading — watch the edges appear."
     4. Talk to `captain_sorn` → "He knows about the war. Watch his tone change."
     5. Talk to `old_henryk` → "He heard it through the network — two hops away."
   - Side panel legend: Character=blue, Faction=red, WorldEvent=orange,
     `KNOWS_ABOUT` = dashed arrow (knowledge propagation)
   - Troubleshooting: LLM timeout, graph not updating, seed duplicates

2. **`phase2_demo_game/handoff.md`** — fill all 6 gates (see handoff template).
   Include transcript excerpt from P2.5 manual run. Record LLM judge verdict.

3. **`project/ISSUES.md`** — append any deferred work found during Phase 2.

4. **`phase2_demo_game/decisions.md`** — confirm all decisions logged. Identify
   any that are cross-phase (e.g., standalone seeder pattern, Pygame-on-host
   run model) and copy to `project/DECISIONS.md`.

5. **`project/NEXT_SESSION.md`** — replace entirely with Phase 3 entry point:
   - Entry criteria status
   - Key context: model, prompt version, `demo_game/` location, top rough edges
   - Open items from ISSUES.md relevant to Phase 3

**Files to modify:**
- `docs/DEMO.md`
- `project/roadmap3/phase2_demo_game/handoff.md`
- `project/ISSUES.md`
- `project/roadmap3/phase2_demo_game/decisions.md`
- `project/DECISIONS.md` (cross-phase decisions only)
- `project/NEXT_SESSION.md`

**Exit check:** All 6 handoff gates recorded. `docs/DEMO.md` reflects new game
flow. `NEXT_SESSION.md` replaced. `ISSUES.md` updated.
