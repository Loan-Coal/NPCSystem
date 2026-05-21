# Phase 2 Handoff

<!-- Fill in this document at the end of Phase 2. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass (demo_game/ unit tests):
   [ ] YES  [ ] NO — details: ...

3. E2E baseline:
   [ ] NO REGRESSION  [ ] REGRESSION
   details: ...

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [describe the demo game walkthrough — what was visible in the
   graph panel, what the NPC said, whether gossip was visibly propagating]

5. LLM judge (HARD gate):
   [ ] PASS  [ ] FAIL
   Verdict: [judge run on at least one demo-game-initiated dialogue turn]

6. Coverage on demo_game/ (excluding UI rendering):
   __% — [ ] PASS (≥78%)  [ ] SOFT FAIL — explanation: ...

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
- [ ] Dialogue UI — player input, NPC response display  ← P2.3
- [ ] Graph visualization panel — live-updating, faction-colored  ← P2.4
- [ ] Gossip trigger flow — event seeded → graph updates visible  ← P2.5
- [ ] LLM judge scenario — `e2e/scenarios/scenario_demo_game_judge.py` PASS  ← P2.5
- [ ] make demo target (functional, not stub)  ← P2.3
- [ ] docs/DEMO.md updated  ← P2.6

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

1. ...
2. ...
3. ...
4. ...
5. ...

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

---

## NEXT_SESSION.md Update

```
Phase 2.3 — Dialogue UI (next session entry point)

Entry criteria (all must be true before starting P2.3):
- P2.2 seeded world verified: `python -m demo_game.seed` → created=0 skipped=53
- Engine running: `docker-compose up -d` → http://localhost:8000 healthy
- 67 demo_game tests green: `pytest demo_game/tests/ -q`

Key context:
- demo_game/ location: demo_game/ (repo root, NOT src/)
- Zero imports from src/npc_engine/ — calls engine via HTTP only
- Seeded world: 5 NPCs (mira_innkeeper, aldric_merchant, captain_sorn,
  lira_fence, old_henryk), 3 locations (loc_tavern, loc_market_square,
  loc_guard_barracks), 3 factions, event northern_war_begins, ws_main epoch=peace
- EngineClient has 20 methods (client.py) — all reads + writes + typed admin
- NPC locations: mira + lira → loc_tavern; aldric + old_henryk → loc_market_square;
  captain_sorn → loc_guard_barracks

P2.3 goal: Pygame game window with location nav, NPC list, text input, scrollable
response log, and degradation badge. Right panel is a placeholder surface (filled
by P2.4). Entry file: demo_game/ui/game_window.py.

TDD order for P2.3:
1. Write demo_game/tests/test_dialogue_logic.py (failing):
   - build_dialogue_payload(npc_id, player_input) -> dict
   - parse_dialogue_response(raw: dict) -> DialogueTurn
   - degradation_level → badge color mapping
2. Implement demo_game/ui/game_window.py (Pygame)
3. Wire dialogue (Enter key → client.post_dialogue → render response + badge)
4. Wire location navigation (buttons → reload NPC list from config)

Schema corrections to keep in mind for P2.3–P2.4:
- NPC-NPC trust: RELATES_TO (not STANDS_WITH). STANDS_WITH is Faction→Faction only.
- Event links: KNOWS_ABOUT is Character→Event only (not Character→Character).
- Inner life (beliefs/goals): read via GET /v1/admin/beliefs/{id} — NOT graph edges.
- MEMBER_OF edges require joined_at + status fields.

make demo target: still a stub — becomes functional at end of P2.3.
```
