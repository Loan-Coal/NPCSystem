# FIX-SEV-20 — `investigation_service` writers: `CREATE` → `MERGE` on stable keys

**Severity:** HIGH · **Decision:** DEC-118 (MERGE on stable keys) · Builds on SEV-05 tests

## Problem
The six `investigation_service.py` writers use raw `CREATE`, so a retried/replayed call silently creates
duplicate nodes/edges. DEC-118: switch to `MERGE` keyed on stable identity so the writes are idempotent,
matching the knowledge/scheme writers.

## Current shape (verify against code now)
- `src/npc_engine/graph/investigation_service.py` — 6 public `async` writers, each `... CREATE ...`.
- Tests already exist (SEV-05): `tests/unit/test_investigation_service.py` (asserts current CREATE Cypher +
  params + error propagation) — these will need updating to MERGE.

## Steps
1. For each writer, identify the node/edge stable key (e.g. `investigation_id`, `clue_id`, or the
   (subject, object, kind) tuple for edges). Replace `CREATE (n {...})` with
   `MERGE (n {<key>}) SET n += {<non-key props>}` so re-runs are idempotent and update-in-place.
2. Keep created-timestamp / immutable fields under `ON CREATE SET` if they must not change on re-run.
3. Update `test_investigation_service.py`: assert the MERGE Cypher + an **idempotency** test (calling the
   writer twice with a fake tx issues a MERGE, not two CREATEs).

## Verification
- `pytest tests/unit/test_investigation_service.py -q` (+ integration if a graph harness exists — a real
  double-write must yield one node).
- `make check`.

## Blast radius
`graph/investigation_service.py` + its tests. **Behavior change** (dedup) — verify no caller relied on
duplicate-node semantics. Graph node/edge keys unchanged (no migration).
