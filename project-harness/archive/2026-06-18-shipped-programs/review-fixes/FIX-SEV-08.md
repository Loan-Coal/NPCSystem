# FIX-SEV-08 — `location_graph` route 422 guards are 0% covered

**Severity:** MEDIUM · **Lens:** L4 (L4-10). Asserted-not-measured.

## Problem
`src/npc_engine/api/routes/location_graph.py` is 0% covered even though the underlying query module has 16
tests. The route-level 422 validation guards (`kind not in _VALID_KINDS`, `from_id == to_id`) are
unreachable by any current test — the validation exists but is never exercised.

## Current shape (verify against code now)
- `src/npc_engine/api/routes/location_graph.py` — 0% in `make test-cov`; guards: `kind not in _VALID_KINDS`, `from_id == to_id` → 422.

## Steps
1. Add `tests/.../test_location_graph_route.py` using the FastAPI test client (mirror an existing route
   test for auth + dependency override): 
   - happy path → 200/expected envelope;
   - invalid `kind` → 422 with the validation triggered;
   - `from_id == to_id` → 422.
2. Use the existing graph-writer dependency override pattern so the test is unit-fast (no real Neo4j) yet
   reaches the route guard lines.

## Verification
- `pytest tests/ -k location_graph_route -q`.
- `make test-cov` — `location_graph.py` coverage rises off 0%; `make check` green.

## Blast radius
New test file only.
