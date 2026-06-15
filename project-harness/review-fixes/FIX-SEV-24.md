# FIX-SEV-24 — GraphRepository facade (engines depend on graph by interface)

**Severity:** LARGE (architecture) · **Decision:** DEC-122 · **Multi-phase** · **Follow-on to SEV-21**

## Problem
After SEV-21 the graph layer owns transactions, but engines still import concrete graph functions and
receive an `AsyncSession` per `run_tick` — 68 engine files reference `neo4j`. The graph layer is therefore
not a swappable boundary: you cannot interpose a cache, swap the DB, or split graph into a microservice
without touching every engine. Goal: engines depend on a small abstraction; the Neo4j implementation owns
the session.

## Port granularity: per graph-DOMAIN repositories (DEC-122, decided 2026-06-15)
Ports are organized by **graph domain** and live together in `engines/ports/<domain>_port.py`; engines
compose the domain Ports they need. Shared readers (`world_state_reader` x8, `relation_reader`,
`player_location_reader`, `character_reader`) become a single shared domain Port reused across engines.

## Pattern (one engine/cluster per commit)
1. **Port Protocol** in `engines/ports/<domain>_port.py`: small, domain-typed methods, **no Neo4j types**.
   The engine imports the Port and depends on it.
2. **Neo4j adapter** in `graph/repositories/<domain>_repository.py`: holds the injected `GraphDB`, opens a
   session per operation (`await graph_db.connect(); async with graph_db.get_session() as session: …`),
   delegates to existing query/writer functions, and (for multi-write atomic ops) uses
   `transaction_coordinator.run_in_tx`. Conforms to the Port **structurally** (no import of the engine Port —
   keeps graph from importing engines).
3. **Engine**: take the Port via `__init__` (DIP); replace direct graph calls with `self._<repo>.method(...)`;
   drop the `session` usage. Keep `run_tick(..., **_)` so the scheduler's `session=` kwarg is accepted and
   ignored during migration.
4. **Composition root** (`api/dependencies*.py`): construct the adapter from `get_graph_db()` and inject it;
   mypy verifies structural conformance here.
5. **Tests**: engine tests mock the Port (no session); add an adapter unit test with a fake `GraphDB`.

## Migrated slices
- **need** (DONE, `c96476e`): `engines/ports/need_port.NeedGraphPort` +
  `graph/repositories/need_repository.Neo4jNeedRepository`; `NeedDecayEngine` migrated. (Port relocated from
  `engines/need/need_graph_port.py` → `engines/ports/` when the shared package was established.)
- **mood** (DONE): `engines/ports/mood_port.MoodGraphPort` + `graph/repositories/mood_repository.Neo4jMoodRepository`;
  `MoodContagionEngine` migrated (`run_tick`/`initialize` drop `session`), wired in `dependencies_advanced/social.py`.
- Tests pattern: `test_<engine>.py` mocks the Port; `test_<domain>_repository.py` covers the adapter with a fake `GraphDB`.

## Wave order (simple → hard)
Wave 1: need ✓, mood ✓, clique, memory(+decay_tick), reputation(+tick; builds RelationReadPort),
player_model(+tick). Wave 2: planning, economy/trade, emotion, agenda, routine, story_pacing, skill,
deception, knowledge_learning, director, chapter, succession, proactive_dialogue, interaction, investigation.
Wave 3 (defer — `run_in_tx` coordinators / large clusters): events, quest, quest_generation, gossip, dialogue,
military, scheming, oath, treaty, faction_politics, idempotency.

## Final step (only after all domains migrated)
Remove `session` from the `BaseEngine.run_tick` protocol and from `tick_scheduler.advance()` so the session
no longer threads through the engine layer at all.

## Verification
- `grep -rn "AsyncSession\|AsyncTransaction\|from neo4j" src/npc_engine/engines/` shrinks toward empty.
- Per slice: `make check` (lint/rules/layers/docstrings/type) + unit suite green.
- `make demo-seed && make demo-run ARGS=--dry-run` smoke after larger batches.

## Blast radius
~68 engine files + their composition-root factories. **Large — phase by engine domain across many sessions.**
Realizes DEC-122 and the engine/graph decoupling goal behind SEV-21.
