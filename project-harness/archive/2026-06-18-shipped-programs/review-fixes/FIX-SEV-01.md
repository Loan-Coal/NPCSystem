# FIX-SEV-01 — Scheme writer transaction safety + missing test

**Severity:** HIGH · **Lens:** L2 (L2-05, L2-07, L2-08), L4 (L4-08)

## Problem
The new scheme write path violates the engine's transaction discipline three ways:
1. `mark_scheme_discovered` runs a **WRITE** (`SET s.status='discovered'`) via bare `session.run` — Neo4j
   auto-commits it with no explicit transaction (L2-05).
2. `scheme_advance_tick` mints an Event in one committed transaction, then links the `SCHEME_STEP` edge in
   a **second independent** transaction. A failure between leaves an orphan Event and a scheme that never
   advances (L2-07).
3. `upsert_scheme` / `add_scheme_step` each call `session.begin_transaction()` internally, violating the
   CLAUDE.md rule that only `graph_writer.py` opens/commits (L2-08).
4. `mark_scheme_discovered` has no unit test (L4-08).

## Current shape (verify against code now)
- `src/npc_engine/graph/scheme_writer.py:149` — `await session.run(_CYPHER_MARK_SCHEME_DISCOVERED, ...)`.
- `src/npc_engine/graph/scheme_writer.py:82,118` — `tx = await session.begin_transaction()` inside `upsert_scheme` / `add_scheme_step`.
- `src/npc_engine/engines/scheming/scheme_advance_tick.py:107-115` — `run_in_tx(_emit)` then a separate `add_scheme_step(session=...)`.
- Correct pattern to mirror: `transaction_coordinator.run_in_tx` (used by `upsert_event`).

## Steps
1. Wrap `mark_scheme_discovered` in an explicit transaction (or accept a `tx: AsyncTransaction` param and let the caller use `run_in_tx`).
2. Add a tx-scoped variant of `add_scheme_step` (and `upsert_scheme` if its caller is also in a tx) that accepts `AsyncTransaction` instead of opening its own.
3. In `scheme_advance_tick`, combine the Event mint **and** the `SCHEME_STEP` link into a single `run_in_tx` so they commit atomically.
4. Keep the broad 14-file session-ownership refactor OUT of scope — that is DEC-119. Touch only scheme files here.

## Verification
- New unit test `tests/unit/test_scheme_writer.py::test_mark_scheme_discovered_*` (happy + the write actually persists via a fake tx that records `tx.run`/`tx.commit` calls — assert commit IS called, not just that the cypher constant exists).
- New unit/integration test asserting `scheme_advance_tick` rolls back the Event when the step link fails (inject a failing `add_scheme_step`, assert no orphan Event).
- Run: `pytest tests/unit/test_scheme_writer.py tests/unit/test_scheme_advance_tick.py -q` then `make check`.

## Blast radius
`graph/scheme_writer.py`, `engines/scheming/scheme_advance_tick.py`, their callers in `dependencies_engines.py` (signature change if a `tx` param is added). Scheme-only; no schema change.
