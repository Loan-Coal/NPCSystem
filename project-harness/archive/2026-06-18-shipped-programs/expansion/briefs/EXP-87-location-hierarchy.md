# EXP-87 — Location hierarchy (PART_OF edge + location_writer.py)

**Goal / rationale:** Locations are currently flat nodes with no parent-child relationship.
Adding a `PART_OF` edge gives the graph a geographic hierarchy (tavern → city → region → world)
that enables region-scoped gossip spread, travel-time aware events, and area-of-effect world
changes. **DEC-071 approved.** This is a Phase 4 / "world richness" item that requires a schema
addition but is self-contained and unblocks demo expansion (more location-aware scenarios).

**⚠️ Schema change:** adds `PART_OF` edge type to `type_registry/base_edges/`. This is
🔶 schema-gated but **pre-approved via DEC-071**. No additional DECISIONS call needed.

**⚠️ Dependency:** KE-6 (stable-id seeding) must be merged first if demo re-seeding
will be run afterward; otherwise EXP-87 can land independently since it only adds new edges
and a new writer, it does not break existing seed data.

**Architecture fit:** New-file-add (`type_registry/` YAML + new `graph/location_writer.py`).
Edits are minimal: `demo_game/seed.py` gains a `_seed_location_hierarchy()` call;
`graph/location_graph_queries.py` gains ancestor/descendant helpers. No layer violations.

---

## Current state

- `src/npc_engine/type_registry/base_edges/` — no `part_of.yaml` exists.
  `grep -r "PART_OF" src/` → 0 hits.
- `src/npc_engine/graph/location_graph_queries.py` — exists; handles location reads.
  No `location_writer.py` exists yet: `ls src/npc_engine/graph/location_writer.py` → missing.
- `demo_game/seed.py:44-70` — `build_location_payload` defines location nodes. Locations
  seeded: `loc_tavern`, `loc_market_square`, `loc_guard_barracks`. No hierarchy wired.
- `src/npc_engine/graph/generic_node_service.py` — `upsert_edge` already handles generic
  edge creation. `location_writer.py` will delegate to this.

## Files to create / edit

### Step 1 — Type registry YAML

- **NEW `src/npc_engine/type_registry/base_edges/part_of.yaml`**:

```yaml
edge_type: PART_OF
description: >
  Directed edge from a child Location to its parent Location.
  Represents geographic containment: a tavern is PART_OF a city,
  a city is PART_OF a region.
source_node_type: Location
target_node_type: Location
properties:
  hierarchy_level:
    type: integer
    description: "Depth level — 0=venue, 1=district, 2=city, 3=region, 4=world"
    required: true
  established_at:
    type: string
    description: "ISO-8601 timestamp when the containment relationship was recorded"
    required: false
```

### Step 2 — location_writer.py

- **NEW `src/npc_engine/graph/location_writer.py`** — single writer module.
  Functions:
  - `async def write_part_of(session: AsyncSession, child_id: str, parent_id: str, hierarchy_level: int) -> None`
    Uses `MERGE (c:Location {id: $child_id})-[r:PART_OF]->(p:Location {id: $parent_id}) ON CREATE SET r.hierarchy_level = $level, r.established_at = $now`.
  - `async def delete_part_of(session: AsyncSession, child_id: str, parent_id: str) -> None`
    Removes a specific containment edge (for administrative use).
  - Inject `AsyncSession` as parameter (per session-ownership rule: graph_writer.py is the
    only file that opens/commits; sub-writers receive the session).
  - Module docstring: `Layer: graph`, `Does NOT: open transactions, call LLM`, `Dependencies injected: AsyncSession`.

### Step 3 — location_graph_queries.py additions

- **EDIT `src/npc_engine/graph/location_graph_queries.py`** — add:
  - `async def get_ancestors(session, location_id: str) -> list[str]`
    Returns ordered list of ancestor location IDs from immediate parent to root.
    Cypher: `MATCH (n:Location {id: $id})-[:PART_OF*]->(a:Location) RETURN a.id ORDER BY size((n)-[:PART_OF*]->(a))`.
  - `async def get_descendants(session, location_id: str) -> list[str]`
    Returns all descendant location IDs (flattened).

### Step 4 — Admin API surface

- **NEW `src/npc_engine/api/routes/locations.py`** (or edit existing if it exists):
  - `POST /v1/admin/locations/{child_id}/part_of` — body: `{"parent_id": str, "hierarchy_level": int}`.
    Calls `location_writer.write_part_of`. Auth: `graph_admin` scope.
  - `DELETE /v1/admin/locations/{child_id}/part_of/{parent_id}` — calls `delete_part_of`.
  - `GET /v1/locations/{location_id}/ancestors` — calls `get_ancestors`. Auth: standard.
  - Register routes in `main.py`.

### Step 5 — Demo seed wiring

- **EDIT `demo_game/seed.py`** — add `_seed_location_hierarchy(client)` function called at
  the end of `seed()`. Wire the flat demo locations into a city:
  ```
  loc_tavern        → PART_OF → loc_city (hierarchy_level=0)
  loc_market_square → PART_OF → loc_city (hierarchy_level=0)
  loc_guard_barracks → PART_OF → loc_city (hierarchy_level=0)
  ```
  Seed `loc_city` as a new Location node first (name="The City", location_tag="city").
  Use `_seed_edge` to guard idempotency.

### Step 6 — Tests

- **NEW `tests/unit/test_location_writer.py`** — mock session; assert MERGE Cypher called
  with correct params; assert `write_part_of` is idempotent (second call doesn't create duplicate).
- **NEW `tests/unit/test_location_graph_queries_hierarchy.py`** — mock session returning
  a path chain; assert `get_ancestors` returns ordered IDs; assert `get_descendants` flattens.
- **EDIT `tests/unit/test_locations_route.py`** (if exists) — add tests for the new
  `POST /v1/admin/locations/{child_id}/part_of` endpoint.

## Graph/API surface

New edge type: `PART_OF (Location → Location)`. New routes:
- `POST /v1/admin/locations/{child_id}/part_of`
- `DELETE /v1/admin/locations/{child_id}/part_of/{parent_id}`
- `GET /v1/locations/{location_id}/ancestors`

## Test plan

Write tests first:
```bash
pytest tests/unit/test_location_writer.py -q   # must fail first
```
Then implement, then:
```bash
make check
make demo-seed   # verify loc_city + PART_OF edges appear in graph
```

## Effort: L  |  Value: med  |  Business-fit: med
## Prerequisite enablers: KE-6 (soft — for idempotent re-seeding); DEC-071 (approved)
## Unblocks: EXP-92, EXP-95 (richer location hierarchy in scenario picker)
