# FIX-SEV-05 — `investigation_service.py` is 0% tested

**Severity:** HIGH · **Lens:** L4 (L4-09)

## Problem
`src/npc_engine/graph/investigation_service.py` exposes six public Neo4j graph-write functions using raw
`CREATE`, with **no unit and no integration tests**. CLAUDE.md requires every public function to have at
least one happy-path and one failure test; Neo4j-touching code needs real integration tests. The raw
`CREATE` (vs `MERGE`) dedup concern is tracked separately as **DEC-118** — do not change the write
semantics here; test the current behavior.

## Current shape (verify against code now)
- `src/npc_engine/graph/investigation_service.py` — 6 public `async def` writers, each `tx.run(... CREATE ...)`.
- 0% coverage confirmed by L4 running `make test-cov`.

## Steps
1. Add `tests/unit/test_investigation_service.py`: for each of the 6 writers, a happy-path test with a fake
   `AsyncTransaction`/session that records the cypher + params (assert correct query constant + param keys),
   and a failure test (writer propagates a `Neo4jError`/`GraphUnavailableError` rather than swallowing).
2. If an integration harness for graph writers already exists (check `tests/integration/`), add one
   integration test per writer against the test DB asserting the node/edge is created.
3. Mocks must satisfy LSP — the fake tx must match the real `AsyncTransaction.run` contract (await, returns a result).

## Verification
- `pytest tests/unit/test_investigation_service.py -q` (+ integration if added).
- `make test-cov` — `investigation_service.py` coverage must rise from 0% toward the module norm; `make check` green.

## Blast radius
New test file(s) only. No source change (semantics deferred to DEC-118).
