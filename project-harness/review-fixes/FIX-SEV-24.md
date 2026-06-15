# FIX-SEV-24 — GraphRepository facade (engines depend on graph by interface)

**Severity:** LARGE (architecture) · **Decision:** DEC-122 · **Multi-phase** · **Follow-on to SEV-21**

## Problem
After SEV-21 the graph layer owns transactions, but engines still import concrete graph functions and
receive an `AsyncSession` per `run_tick` — 68 engine files reference `neo4j`. The graph layer is therefore
not a swappable boundary: you cannot interpose a cache, swap the DB, or split graph into a microservice
without touching every engine. Goal: engines depend on a small abstraction; the Neo4j implementation owns
the session.

## Pattern (per engine domain — one domain per commit)
1. **Port Protocol** in the engines layer (e.g. `engines/<domain>/<domain>_graph_port.py`): small,
   domain-typed methods, **no Neo4j types**. The engine imports the Port and depends on it.
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

## Reference slice (DONE 2026-06-15)
`need` domain: `engines/need/need_graph_port.NeedGraphPort`, `graph/repositories/need_repository.Neo4jNeedRepository`,
`NeedDecayEngine` migrated (imports no `neo4j`/graph symbol), wired in `dependencies_advanced/social.py`.
Tests: `test_need_decay_engine.py` (mocks the port), `test_need_repository.py` (adapter).

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
