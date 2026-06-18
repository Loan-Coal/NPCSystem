# Phase 2 Handoff

<!-- Fill in this document at the end of Phase 2. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [x] YES — 107 demo_game tests green (84 from P2.3 + 23 new from test_fetcher.py).
   Engine test suite baseline unchanged: 20 failed / 951 passed / 17 skipped.

2. New tests pass (demo_game/ unit tests):
   [x] YES — 23 tests in test_fetcher.py, all green. Covers fetch_snapshot (16 tests:
   structural node/edge calls, Belief + Goal synthesis, correct field extraction) and
   compute_delta (7 tests: None prev, new node, new edge, no-change, only-new cases).

3. E2E baseline:
   [x] NO REGRESSION — demo_game/tests/ suite runs in isolation; engine suite not touched.

4. Manual sign-off:
   [x] SIGNED OFF 2026-05-22 — `make demo` with seeded world: graph renders live after ~5s,
   Belief/Goal satellite nodes visible, KNOWS_ABOUT edges dashed. W key → "War declared!"
   overlay, graph updates on next poll. C key → "Clock advanced" overlay, gossip tick fires.

5. LLM judge (HARD gate):
   [x] PASS 2026-05-22 — `make eval-llm-demo` (qwen2.5:14b, 2 tests):
   - test_war_epoch_captain_sorn_acknowledges_war: PASS
     captain_sorn: "The northern armies have crossed our borders, starting a conflict we
     were trying to avoid. The situation is tense and resources are being redirected to
     fortify our defenses." Judge: YES — explicit war/conflict reference.
   - test_gossip_propagates_after_clock_advance: PASS
     Event node northern_war_begins present after advance_clock(1). Judge: YES.

6. Coverage on demo_game/ (excluding UI rendering):
   dialogue.py: 100%. fetcher.py: 100% (fetch_snapshot + compute_delta).
   client.py + seed.py + config.py covered by prior suites.
   renderer.py + poller.py excluded from coverage (matplotlib/pygame rendering + threading).
   [x] PASS

---

## What Shipped

- [x] demo_game/ package scaffold — P2.1 done 2026-05-21
      EngineClient (8 methods), DemoConfig, stubs for seed/ui/graph_panel,
      GraphNode/GraphEdge/GraphSnapshot/GraphDelta dataclasses, 20 tests green,
      make demo / demo-seed / test-demo targets, .env.demo gitignored
- [x] seed.py — demo world created via API calls — P2.2 done 2026-05-21
      EngineClient extended to 20 methods (graph reads, writes, typed endpoints,
      `put_world_state`, `put_npc_reputation`, `get_beliefs`). test_seed.py: 20
      tests. Full demo world: 3 locations, 3 factions, 5 NPCs (mira_innkeeper,
      aldric_merchant, captain_sorn, lira_fence, old_henryk), per-NPC beliefs/
      goals/memories/secrets, 1 event (northern_war_begins), world_state
      (epoch=peace), MEMBER_OF + STANDS_WITH (faction-faction) + RELATES_TO
      (NPC-NPC) + OPPOSES + KNOWS_ABOUT edges. Idempotent: `python -m demo_game.seed`
      re-run → created=0 skipped=53. Test suite: 67 tests, all pass.
- [x] Dialogue UI — player input, NPC response display  ← P2.3 done 2026-05-22
      dialogue.py (pure logic), constants.py (world layout), ui/widgets.py (4 widget
      classes), ui/game_window.py (GameWindow + run(), threading via queue.Queue).
      84 tests green. make demo functional. pygame-ce required (Python 3.14 has no
      pygame wheel — see ISSUE-021 / requirements.txt comment).
- [x] Graph visualization panel — live-updating, faction-colored  ← P2.4 done 2026-05-22
      graph_panel/fetcher.py (fetch_snapshot + compute_delta), graph_panel/renderer.py
      (networkx→matplotlib→pygame), graph_panel/poller.py (GraphPoller daemon thread,
      delta-highlight countdown), game_window.py wired. client.py extended with
      get_goals(). 107 tests green. Awaiting manual sign-off (make demo + demo-seed).
- [x] Gossip trigger UI — W/C keys wired; status overlay implemented  ← P2.5 done 2026-05-22
- [x] LLM judge scenario — `make eval-llm-demo` PASS (qwen2.5:14b, 2/2 tests)  ← P2.5 done 2026-05-22
- [x] make demo target (functional) — docker-compose up -d + Pygame window  ← P2.3 done
- [x] docs/DEMO.md updated  ← P2.6 done 2026-05-22

---

## What Was Deferred

- **ISSUE-019**: 20 pre-existing test failures — `consume()` missing on mock Neo4j result
  stubs in `tests/unit/`. Not introduced by P2.1. Logged in `ISSUES.md`. Defer to Phase 4+.
- `make test` accurate baseline: **20 failed, 951 passed, 17 skipped (988 total)** —
  the "964/965" figure in NEXT_SESSION.md (written post-Phase 1) was incorrect.

**P2.2 schema discoveries (for decisions.md + next sessions):**
- `STANDS_WITH` is Faction→Faction only (not Character→Character). NPC-NPC positive
  trust uses `RELATES_TO` (fields: trust 0–100, affection, fear, relevance_score,
  interaction_count, last_updated_at).
- `KNOWS_ABOUT` is Character→Event only (not Character→Character).
- `OPPOSES` is Character→Character only (fields: intensity, reason, established_tick).
- Faction nodes require `created_at` and `last_graph_updated_at`.
- `MEMBER_OF` requires `joined_at` and `status` fields.
- `world_state` requires `faction_standings`, `time_of_day`, `weather`,
  `last_updated_at`, `last_graph_updated_at` in addition to `epoch`/`active_conditions`.
- Typed endpoints (beliefs/goals/memories/secrets) do NOT create BELIEVES/PURSUES/etc.
  generic graph edges — idempotency check must use `GET /v1/admin/beliefs/{character_id}`
  not the graph edge endpoint.
- `RELATES_TO` trust field is 0–100 (no negative values).

These corrections are logged in `phase2_demo_game/decisions.md`.

---

## Top 5 Rough Edges Identified (for Phase 4)

1. **`pygame` has no Python 3.14 wheel.** `pygame-ce` (community edition, drop-in
   compatible) was installed instead. `requirements.txt` updated. If upstream pygame
   ships a 3.14 wheel, switch back — but track as ISSUE-021.
2. **`ScrollableLog` wraps long NPC responses badly.** Single-line blit means long
   responses overflow the widget width. Word-wrap should be added before the demo.
3. **No session continuity between dialogue turns.** Each call to `post_dialogue`
   is stateless (session_id not threaded through). The engine supports session_id
   for context persistence; the game window discards it.
4. **`BELIEVES` / `PURSUES` graph edges are NOT populated by typed admin endpoints.**
   P2.4 fetcher must read beliefs/goals via `GET /v1/admin/beliefs/{id}` and synthesize
   virtual edges for the visualisation, not fetch from `GET /v1/graph/edges/BELIEVES`.
5. **`RELATES_TO` edge not in P2.4 spec but needed for NPC-NPC trust visualisation.**
   The seeded world has RELATES_TO edges (mira→old_henryk, lira→aldric, etc.).
   fetcher.py must add RELATES_TO to its edge-fetch list.

---

## What Phase 3 Needs to Know

Phase 3 (QLoRA Adapter) does not depend on the demo game UI, but the following
observations from P2.2 engine interactions are relevant:

1. **Inner life is served via typed admin endpoints, not graph edges.**
   `GET /v1/admin/beliefs/{id}` returns the full belief list. The BELIEVES graph
   edge is NOT populated by the typed endpoint — fetcher.py (P2.4) must use
   the admin endpoints to read NPC beliefs/goals, not `GET /v1/graph/edges/BELIEVES`.

2. **Edge schema corrections vs. subphases.md** (critical for P2.4 fetcher):
   - `STANDS_WITH` is **Faction→Faction only** (standing: int). NPC-NPC positive
     trust uses `RELATES_TO` (fields: trust 0–100, affection, fear, relevance_score,
     interaction_count, last_updated_at).
   - `KNOWS_ABOUT` is **Character→Event only** (not Character→Character).
   - `OPPOSES` is **Character→Character only** (intensity, reason, established_tick).
   - `MEMBER_OF` requires `joined_at` and `status` fields.
   - Subphases.md planned `mira STANDS_WITH old_henryk` and `lira KNOWS_ABOUT aldric`
     — both were wrong type/direction and have been corrected to `RELATES_TO` and
     `KNOWS_ABOUT northern_war_begins` respectively.

3. **world_state required fields**: faction_standings (dict), time_of_day, weather,
   last_updated_at, last_graph_updated_at — in addition to epoch/active_conditions.

4. **Dialogue UI (P2.3) enters with a fully seeded world**: 5 NPCs across 3 locations,
   all with beliefs/goals/memories/secrets. The `make demo-seed` idempotency check
   confirms `created=0 skipped=53` on re-run — safe to run before every demo session.

---

## Decisions Graduated to project/DECISIONS.md

- **Standalone seeder pattern** (2026-05-22) — `demo_game/seed.py` as a separate seeder
  from `src/npc_engine/data/api_seeder.py`. Establishes the pattern for any future phase
  that needs a self-contained world via HTTP. See `project/DECISIONS.md`.

---

## NEXT_SESSION.md Update

```
Phase 2.4 — Graph visualization panel (next session entry point)

Entry criteria (all must be true before starting P2.4):
- Engine running and world seeded: `make demo-seed` → created=0 skipped=53
- 84 demo_game tests green: `pytest demo_game/tests/ -q`
- `make demo` launches window; NPCs respond at all 3 locations (P2.3 verified)

Key context:
- demo_game/ at repo root — zero imports from src/npc_engine/
- Pygame runs on host via pygame-ce (not pygame — no Python 3.14 wheel)
- EngineClient: 20 methods in demo_game/client.py — all reads/writes/typed admin
- graph_panel/fetcher.py: dataclasses defined (GraphNode/Edge/Snapshot/Delta),
  fetch_snapshot() and compute_delta() are NotImplementedError stubs — implement these
- graph_panel/renderer.py: render_snapshot() is a NotImplementedError stub — implement this
- game_window.py: _draw_right_panel() currently draws grey placeholder — replace with renderer

P2.4 goal: Replace the grey right panel with a live networkx+matplotlib graph that
polls the engine every DEMO_GRAPH_POLL_INTERVAL seconds and delta-highlights new edges.

TDD order for P2.4:
1. Write demo_game/tests/test_fetcher.py (failing):
   - fetch_snapshot(client) calls correct node + edge endpoints
   - GraphSnapshot contains typed node and edge lists
   - compute_delta(None, curr) → all nodes/edges are new
   - compute_delta(prev, curr) → only genuinely new items appear in delta
2. Implement fetch_snapshot() + compute_delta() in graph_panel/fetcher.py
3. Implement render_snapshot() in graph_panel/renderer.py (networkx layout → matplotlib → pygame surface)
4. Wire polling thread + renderer into game_window.py right panel

CRITICAL schema facts for P2.4 fetcher (discovered in P2.2 — DO NOT get wrong):
- BELIEVES / PURSUES graph edges are NOT populated by typed admin endpoints.
  Read beliefs via GET /v1/admin/beliefs/{id} — synthesize virtual edges for display.
- RELATES_TO (not in original spec, but seeded) — must fetch for NPC-NPC trust display.
- STANDS_WITH is Faction→Faction only (standing: int).
- KNOWS_ABOUT is Character→Event only.
- OPPOSES is Character→Character only.
- Memory/Belief/Goal nodes: visible via typed admin endpoints, not GET /v1/graph/nodes/Memory.

Node types to fetch in fetcher: Character, Location, Faction, Event, world_state
Edge types to fetch: KNOWS_ABOUT, STANDS_WITH, OPPOSES, MEMBER_OF, RELATES_TO
(skip BELIEVES/PURSUES — empty in graph; synthesize from admin endpoints if needed)

Rendering decisions (logged in decisions.md):
- Option A chosen: networkx layout → matplotlib FigureCanvasAgg → pygame surface
- Node colours: Character=blue, Faction=red, Event=orange, Location=green
- Edge weight → line thickness; KNOWS_ABOUT → dashed arrow
- Delta new edges: yellow highlight for 2 poll cycles then fade
- Falls back to "Waiting for data..." until first fetch completes
```

---

## P2.4 Completion Notes (2026-05-22)

**What shipped:**
- `graph_panel/fetcher.py` — fetch_snapshot (5 structural node types + Belief/Goal synthesis),
  compute_delta (set-key diff). Fixed frozen-dataclass hash flaw (`properties` field).
- `graph_panel/renderer.py` — render_snapshot returns new pygame.Surface (fixed wrong stub
  signature). Kamada-Kawai layout, matplotlib Agg, node colors by type, KNOWS_ABOUT dashed,
  delta highlights yellow.
- `graph_panel/poller.py` — GraphPoller daemon thread. Immediate first fetch; then interval loop.
  2-cycle highlight countdown. Thread-safe get_surface() via Lock.
- `demo_game/client.py` — added get_goals(character_id) method.
- `demo_game/ui/game_window.py` — wired GraphPoller; _draw_right_panel now blits live surface
  or "Waiting for data…"; timestamp overlay bottom-right.
- 23 new tests in test_fetcher.py. 107 total, all green.

**P2.4 Manual sign-off (2026-05-22):**
- `make demo-seed` ran successfully: `created=53 skipped=0` (fresh world).
  Re-run: `created=0 skipped=53` (idempotent). ✅
- `make demo` launched Pygame window. Right panel rendered live graph after ~5s.
  Belief/Goal satellite nodes visible. KNOWS_ABOUT edges dashed.
  "Updated: HH:MM:SS" timestamp in bottom-right corner. ✅
- P2.4 gate 4 (manual sign-off): **SIGNED OFF 2026-05-22.**

**Next session entry point: P2.5** — Gossip trigger UI + LLM judge scenario.
Entry criteria for P2.5:
- Engine running + world seeded: `make demo-seed` → skipped=53
- 107 demo_game tests green: `pytest demo_game/tests/ -q`
- `make demo` → graph renders after ~5s; Belief/Goal nodes visible; KNOWS_ABOUT dashed

---

## P2.5 Completion Notes (2026-05-22)

**What shipped:**
- `demo_game/ui/game_window.py` — W key → `put_world_state("war", ["northern_war"])`;
  C key → `advance_clock(delta_ticks=1)`; `_handle_key`/`_set_status`/`_draw_status_overlay`
  private methods; 2s status overlay bottom-left (yellow text). 326 lines — DECISIONS.md
  exception logged.
- `e2e/scenarios/scenario_demo_game_judge.py` — 2 LLM judge tests:
  `test_war_epoch_captain_sorn_acknowledges_war` and `test_gossip_propagates_after_clock_advance`.
  Ollama skip pattern added (`_ollama_reachable()` check). Uses `ws_main` (not `world`).
- `Makefile` — `eval-llm-demo` target added.
- `project/ISSUES.md` — ISSUE-021 logged (gossip test weakness).
- `project/roadmap3/phase2_demo_game/decisions.md` — 300-line exception entry added.

**Post-fix note:** `_JUDGE_MODEL` default corrected `qwen2.5:7b` → `qwen2.5:14b`;
`_ollama_reachable()` now checks model presence in `/api/tags`, not just liveness.

**Next: P2.6 (docs + handoff close-out).**

---

## P2.5 Context (for planning session)

### What P2.5 Must Ship

1. **War trigger key binding in game_window.py** — pressing `W` calls
   `client.put_world_state(epoch="war", active_conditions=["northern_war"])`.
   Pressing `C` calls `client.advance_clock(delta_ticks=1)` (one gossip tick).
   Visual feedback: brief on-screen status message so the audience sees the
   action was taken (e.g. "⚡ War declared!" overlay for 2s).
   Both must be wired from `_handle_event` → `_handle_key(event.key)`.

2. **LLM judge scenario** — `e2e/scenarios/scenario_demo_game_judge.py`.
   Two tests minimum:
   - `test_war_epoch_captain_sorn_acknowledges_war`: advance to war epoch, ask
     `captain_sorn` "What is happening in the north?", judge: "does the NPC
     response reference war, conflict, or the north?"
   - `test_gossip_propagates_to_npc_graph`: trigger clock advance, then
     `GET /v1/graph/nodes/Event` should include `northern_war_begins`; judge:
     presence of the event node.
   Follow existing pattern in `e2e/scenarios/scenario_llm_judge.py` exactly
   (same imports, same `_make_judge()` helper, `@pytest.mark.llm_eval`,
   `@pytest.mark.asyncio`).

3. **Makefile target `eval-llm-demo`** — runs only
   `e2e/scenarios/scenario_demo_game_judge.py -m llm_eval`.
   `eval-llm` stays unchanged (runs `scenario_llm_judge.py`).

4. **Transcript** — `e2e/transcripts/demo_war_baseline.md` (gitignored).
   Record one manually-triggered gossip propagation run.

### Critical Schema / API Facts for P2.5

- **world_state node id in the DEMO world is `ws_main`**, NOT `world`.
  `world` is used by `e2e/scenarios/scenario_llm_judge.py` (Phase 1 seed).
  Do NOT conflate the two. The demo seed creates: `upsert_node("world_state",
  "ws_main", {...})`.
- `client.put_world_state(epoch, active_conditions)` wraps
  `PUT /v1/admin/world_state` — see `EngineClient.put_world_state` in
  `demo_game/client.py`.
- `client.advance_clock(delta_ticks=1)` wraps `POST /v1/clock/advance` with
  body `{"delta_ticks": 1}` — see `EngineClient.advance_clock`.
  **Name is `advance_clock`, NOT `post_clock_advance`.**
- Demo world NPC IDs (exact strings used in all API calls):
  `mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`,
  `old_henryk`.
- Demo player ID: `"player_demo"` (from `DemoConfig.DEMO_PLAYER_ID`).
- `captain_sorn` KNOWS_ABOUT `northern_war_begins` — the NPC most likely
  to respond to war-epoch dialogue with thematic content.
- CLOCK_MODE is `game_driven` in docker-compose.yml — the gossip engine only
  ticks when `advance_clock` is explicitly called. The demo needs `C` to
  be a manual clock-advance button for the presenter.

### Existing LLM Judge Infrastructure (DO NOT DUPLICATE)

- `e2e/helpers/llm_judge.py` — `llm_judge(content, criteria, llm_client)
  -> JudgeVerdict(passed, reasoning)`. Parses YES/NO from LLM output.
- `e2e/scenarios/conftest.py` — `api_post(client, path, payload)`,
  `api_get(client, path)`, `Narrator`, `char_props`, `CANNED_PHRASES`.
- `e2e/scenarios/scenario_llm_judge.py` — 4 existing tests against Phase 1
  world (`guard_1`, `npc_1`, `world`). Do NOT touch these. New demo tests
  go in `scenario_demo_game_judge.py`.
- `_make_judge()` helper: creates `OllamaAdapter(model="llama3.2:1b")`.
  Copy this pattern exactly.

### 300-Line Constraint Status

- `demo_game/ui/game_window.py`: 290 lines after P2.4. W/C key binding adds
  ~15 lines max (handler + status overlay state + _draw_status_overlay).
  **Final estimate: ~305 lines.** Will need a DECISIONS.md exception entry,
  or extract `_handle_key` block + overlay into a helper (preferred).
- Option: extract `_draw_status_overlay(rect)` as a private method
  (self-evident name, <10 lines → no docstring required per CLAUDE.md).
- If key-binding logic grows, extract to `demo_game/ui/key_bindings.py`.

### Files to Create / Modify in P2.5

| Action | File | Notes |
|--------|------|-------|
| MODIFY | `demo_game/ui/game_window.py` | W/C key handlers + status overlay |
| CREATE | `e2e/scenarios/scenario_demo_game_judge.py` | LLM judge for demo world |
| MODIFY | `Makefile` | Add `eval-llm-demo` target |
| CREATE | `e2e/transcripts/demo_war_baseline.md` | Manual run transcript (gitignored) |
| MODIFY | `project/roadmap3/phase2_demo_game/handoff.md` | Gate 4 + LLM judge gate |
| MODIFY | `project/roadmap3/phase2_demo_game/decisions.md` | Any non-obvious choice |

### TDD Order for P2.5

1. Write `e2e/scenarios/scenario_demo_game_judge.py` (failing — engine not
   in war epoch yet). Confirm import errors resolve, marks parse correctly.
2. Wire W key in `game_window.py` — calls `put_world_state`. Manual test:
   press W, observe graph update (world_state node epoch changes).
3. Wire C key — calls `advance_clock(delta_ticks=1)`. Manual: press C,
   observe KNOWS_ABOUT edge or Belief node appear on next graph poll.
4. Add status overlay rendering for W/C actions (2s timeout).
5. Run `make eval-llm-demo` against live engine in war epoch — confirm PASS.
6. Record `demo_war_baseline.md` transcript.

### Gate 5 (LLM Judge) Requirements

- All tests in `scenario_demo_game_judge.py` must pass with
  `make eval-llm-demo`.
- Model: `llama3.2:1b` via Ollama (same as existing judge tests).
- Ollama must be running locally (`ollama serve`) for the eval to pass.
- If Ollama is not running, tests should be skipped (not failed) via a
  `pytest.skip` check matching the existing pattern in `scenario_llm_judge.py`.
