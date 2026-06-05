# FIX-SEV-12 — Introduce multi-tenant / world isolation

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** XL (multi-session)
**Category:** product / data-integrity · **Absorbs:** GAME-03
**BLOCKER:** this is a graph-schema + auth change. Per CLAUDE.md you MUST write a `DECISIONS.md` proposal and get human approval BEFORE implementing.

## Problem
There is no `world_id`/tenant dimension anywhere. Two studios integrating against one deployment share one Neo4j namespace; same-named nodes collide, seeds overwrite each other, gossip/reputation cross-contaminate. The "license to studios, integrate with one API call" premise has no isolation behind it.

## Current shape
- `rg "world_id" src/npc_engine/graph` → **no files**. All reads/writes MERGE on `(label, id)` only.
- `api/routes/graph.py` node/edge CRUD keyed only on `node_type` + `id`.
- `auth/middleware.py` resolves a `granted_scope`, no tenant.
- Stable IDs like `mira_innkeeper` (`demo_game/constants.py:33-39`) are global.

## Target shape
`world_id` (a.k.a. `tenant_id`) is a first-class component of node identity, derived from the auth token, and present in every Cypher MATCH/MERGE and every API route.

## Steps (after DECISIONS approval)
1. **DECISIONS proposal**: choose the isolation mechanism — composite key (`MERGE (n:Character {world_id:$world_id, id:$id})`) vs per-world label namespace vs separate Neo4j databases per tenant. Composite key is the least-disruptive; document trade-offs.
2. **Auth**: map each API token → a `world_id`; expose it on the request scope (`auth/middleware.py` + `auth` scope model).
3. **Graph layer**: thread `world_id` into every MATCH/MERGE/constraint (this rides on SEV-04's "all Cypher in graph/" and SEV-10's constraints — composite unique constraint `(world_id, id)`).
4. **API**: add `world_id` resolution to every route from the token (not a client-supplied body field) so a studio cannot read another's world.
5. **Seeders**: parameterize by `world_id`.
6. Migration/back-compat: existing single-world data gets a default `world_id`.

## Verification
- Two seeded worlds with overlapping IDs (`mira_innkeeper` in both) remain fully isolated across every read (dialogue, gossip, reputation, graph CRUD).
- A token scoped to world A cannot read or mutate world B (test returns 404/empty, never B's data).

## Blast radius
Every node, edge, engine, route, and seeder. This is the largest single item; sequence it after SEV-04 and SEV-10 so the Cypher and constraints are already centralized.
