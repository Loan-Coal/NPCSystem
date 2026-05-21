# Next Session Instructions

## Current state

Roadmap V3 — **Phase 2: Demo Game Skeleton + Graph Visualization.**
**P2.1 (scaffold + EngineClient) is complete.** Entry point for this session is **P2.2 (seed script)**.

Run tests before touching any code:

```bash
pytest demo_game/tests/ -q    # 20 pass — demo_game unit tests
pytest tests/unit/ -q         # expect ~20 pre-existing failures (ISSUE-019), do not investigate
```

---

## Entry criteria

| Criterion | Status |
|---|---|
| Phase 1 handoff signed off | YES |
| P2.1 scaffold + EngineClient shipped | YES (2026-05-21) |
| demo_game/tests/ — 20 pass | YES |
| .env.demo gitignored | YES |
| make demo, demo-seed, test-demo targets added | YES |
| ISSUE-019 (pre-existing consume() mock failures) logged | YES |

---

## Known test count (corrected)

`pytest tests/ -q` baseline at start of P2.2: **20 failed, 951 passed, 17 skipped (988 total)**.
The 20 failures are all pre-existing `consume()` mock stubs — see ISSUE-019. Do not treat
these as regressions introduced during P2.1. NEXT_SESSION.md previously said "964/965" which
was inaccurate.

---

## P2.2 goal — Seed script

Implement `demo_game/seed.py` to replace the `NotImplementedError` stub. The seeder must:

1. Create the demo world via HTTP only — zero direct Neo4j/npc_engine imports.
2. Use `EngineClient` (from `demo_game.client`) for all API calls.
3. Be **idempotent**: POST to create; treat 409 (Conflict) as "already exists", skip cleanly.
   Mirror the `_Counter` / `_call` pattern from `src/npc_engine/data/api_seeder.py`.
4. Seed the exact world described in `subphases.md` P2.2 (using corrected type names from
   `decisions.md` DEC-P2-03):
   - 3 locations: `tavern`, `market_square`, `guard_barracks`
   - 3 factions: `merchants_guild`, `city_guard`, `thieves_guild`
   - 5 NPCs: `mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`, `old_henryk`
   - Per-NPC: beliefs, goals, secrets, memories
   - 1 Event: `northern_war_begins` (type `Event`, not `WorldEvent`)
   - WorldState: epoch=peace (node type `world_state`, lowercase)
   - Relations: `mira STANDS_WITH old_henryk`, `lira KNOWS_ABOUT aldric`,
     `captain_sorn OPPOSES lira` (corrected edge types from DEC-P2-03)
5. Add `make demo-seed` to actually call `seed()` (currently the target just prints "not implemented").
6. Write **TDD tests first** — `demo_game/tests/test_seed.py`. Test the data-builder functions
   independently of HTTP; test `seed()` with a mock EngineClient.

TDD discipline (CLAUDE.md): write failing tests → confirm failure reason → implement → green.

---

## Key context

- **EngineClient**: `demo_game/client.py` — synchronous httpx client. All methods raise
  `EngineClientError` on 4xx/5xx. DI pattern: `_http_client` kwarg for test injection.
- **Reference seeder**: `src/npc_engine/data/api_seeder.py` — exact request shapes for nodes
  (`POST /v1/graph/nodes/{type}` with `{"properties": {...}}`), edges
  (`POST /v1/graph/edges/{type}` with `{"src_id": ..., "dst_id": ..., "properties": {...}}`),
  and typed admin endpoints (`POST /v1/admin/beliefs/{char_id}`, etc.).
- **Type name corrections** (DEC-P2-03, `decisions.md`):
  - `WorldEvent` → `Event`
  - `WorldState` (capital S) → `world_state` (lowercase)
  - `TRUSTS` → `STANDS_WITH`
  - `FEARS` → `OPPOSES`
  - `HAS_BELIEF` → `BELIEVES` (edge type, but typed endpoint is `POST /v1/admin/beliefs/{id}`)
  - `HAS_GOAL` → `PURSUES` (edge type, but typed endpoint is `POST /v1/admin/goals/{id}`)
- **Faction membership**: use `POST /v1/admin/factions/{faction_id}/members` with
  `{"character_id": ..., "role": ..., "status": "active"}` — see api_seeder.py line ~299.
- **Beliefs/goals/secrets/memories**: use typed admin endpoints (`POST /v1/admin/beliefs/{char_id}`,
  etc.) with `game_time` dict — NOT the generic graph node endpoint. See api_seeder.py line ~344+.
- **Re-seed idempotency**: typed admin endpoints (beliefs, goals, etc.) auto-generate IDs so
  re-seeding creates duplicates. Comment in seed.py must say "wipe DB before re-seeding".
  Match this note from api_seeder.py line 12–14.
- **Config**: `from demo_game.config import config` — has `NPC_BASE_URL`, `NPC_API_KEY`.
- **make demo-seed**: must be updated from the stub message to actually call `seed()`.
- **Coverage gate**: `pytest demo_game/tests/ -q --cov=demo_game --cov-report=term-missing`
  must hit ≥78% on `demo_game/` (excluding UI rendering) by end of Phase 2.

---

## Phase 2 open items (carry forward)

- ISSUE-019: 20 pre-existing `consume()` mock failures — defer to Phase 4+
- ISSUE-018: subphases.md uses wrong type names — fix in P2.6 cleanup pass
- ISSUE-017: Unregistered type → HTTP 500 — defer to Phase 4+
