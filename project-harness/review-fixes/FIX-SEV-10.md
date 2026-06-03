# FIX-SEV-10 — Add core-node uniqueness constraints at startup; make the seeder idempotent

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** M
**Category:** data-integrity · **Absorbs:** GRAPH-03, GRAPH-04
**Note:** adds graph constraints (schema enforcement) — per CLAUDE.md "ask before changing the schema of a graph node/edge," confirm the constraint set with a human, then implement.

## Problem
No uniqueness constraints exist for core node labels in any auto-run path, so concurrent MERGEs can duplicate `Character`/`Event`/etc. The canonical `api_seeder.py` is non-idempotent and three seeders use three different idempotency contracts.

## Current shape
- `main.py:154-163` ensures only tick-lease + idempotency constraints.
- `rg "Character.*IS UNIQUE"` → no matches. Core-label constraints exist only in manual `scripts/migrations/`.
- `graph/generic_node_service.py:128` `MERGE (n:Character {id:$id})` with no backing constraint → MERGE race duplicates.
- `data/api_seeder.py:12-14` docstring: re-running "will create duplicate beliefs, goals, items, secrets, and memories" (typed endpoints auto-generate IDs); Phase-3 loops at `:343-420`.
- `seeds/worlds/seed_village_world.py:159,187` get-then-skip (idempotent); `demo_game/seed.py:235,255,287` returns "skipped".

## Target shape
A single startup bootstrap creates `IS UNIQUE` constraints for all core labels; all seeders share one idempotency contract.

## Steps
1. Create `graph/schema_bootstrap.py` with `async def ensure_core_constraints(session)` issuing, for each of `Character, Event, Location, WorldState, Item, Quest, Faction`:
   `CREATE CONSTRAINT <name> IF NOT EXISTS FOR (n:<Label>) REQUIRE n.id IS UNIQUE`.
2. `await ensure_core_constraints(...)` in the `main.py` lifespan alongside the lease/idempotency calls. Consolidate the relevant `scripts/migrations/` constraints into this path.
3. Make `api_seeder.py` idempotent: either (a) `get_*`-then-skip mirroring the village seeder, or (b) make typed admin endpoints accept a client-supplied stable id and MERGE. Pick one and apply the same contract to all three seeders; update the `api_seeder` docstring.

## Verification
- Fresh `docker-compose up` + startup → `SHOW CONSTRAINTS` lists all core labels.
- Integration test: attempt duplicate-id node creation → fails.
- `make seed-api` run twice → belief/goal/item/secret/memory counts unchanged.

## Blast radius
Entire core graph; all downstream reads/retrieval/gossip. Constraints are additive and safe (`IF NOT EXISTS`).
