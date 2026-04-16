# NPC Engine v1.3 Implementation Tracker

This file tracks iterative implementation for PROJECT_PLAN_v1.3.xml and supports interruption/resume.

## How to Resume
1. Find the first stage marked IN_PROGRESS or TODO.
2. Continue from the first unchecked task in that stage.
3. Run the listed verification commands.
4. Update status, dates, and notes before stopping.

## Status Legend
- TODO: not started
- IN_PROGRESS: partially complete
- DONE: complete and verified
- BLOCKED: waiting on decision/input

## Stages

### M6 - Schema Layer and Route Versioning
Status: DONE
Started: 2026-04-15
Completed: 2026-04-15
Checkpoint: CP6_SCHEMA_ROUTING

Tasks:
- [x] Add schema layer (`schema_loader`, `schema_models`, `model_factory`, resolvers, enum validator)
- [x] Add `game_schema.example.yaml`
- [x] Add v1 route prefix support (`API_V1_PREFIX`) and move non-health routes under `/v1/*`
- [x] Add `/v1/schema` endpoint
- [x] Wire schema loading in startup and fail fast on invalid schema
- [x] Add/adjust tests for schema loading and route prefix behavior

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/unit
```

Notes:
- Iterative mode enabled: implementation proceeds in small verified slices.
- Verified with targeted tests: `tests/unit/test_schema_loader.py` and `tests/unit/test_v1_route_versioning.py`.

### M7 - Graph Edit Contracts and Services
Status: DONE
Started: 2026-04-15
Completed: 2026-04-15
Checkpoint: CP7_GRAPH_EDIT

Tasks:
- [x] Add typed graph patch/request models
- [x] Implement graph edit validator with immutable field checks and extension field validation
- [x] Implement graph edit service orchestration (node/edge create/patch/delete) (core resources)
- [x] Add referential integrity checks inside write transactions
- [x] Add `last_graph_updated_at` updates on graph writes (core models/services)
- [x] Add GET routes for graph resources

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/unit tests/integration -k graph_edit
```

### M8 - Admin, Soft Delete, Reindex, Movement
Status: DONE
Started: 2026-04-15
Completed: 2026-04-15
Checkpoint: CP8_ADMIN_OPS

Tasks:
- [x] Implement scope inheritance (`graph_admin` includes `graph_write`)
- [x] Implement soft delete for characters and engine-side active filtering (reader filters + route/service)
- [x] Implement admin hard-delete cascade routes/services (core character/event/location)
- [x] Implement admin absolute and unbounded delta relation routes/services
- [x] Implement async reindex submission + job polling routes (in-memory job store)
- [x] Implement admin audit log read endpoint (placeholder response)
- [x] Implement atomic character move endpoint
- [x] Implement world state PATCH endpoint (full-replace JSON semantics)

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/integration -k "admin or cascade or reindex or move"
```

### M9 - Hardening, Docs, CI, Coverage
Status: DONE
Started: 2026-04-16
Completed: 2026-04-16
Checkpoint: CP9_RELEASE

Tasks:
- [x] Add embedding reconciler and startup task wiring
- [x] Update docs (`ARCHITECTURE.md`, `DATA_MODELS.md`, `README.md`)
- [x] Update CI targets/workflow for v1.3 test matrix
- [x] Ensure coverage remains >= 80%
- [x] Run full verification suite

Verification:
```bash
cd npc_engine
make check
pytest --cov=. --cov-report=term-missing
```

## Decisions Needed
- [x] Auth key-to-scope mapping format (`graph_write` vs `graph_admin`) in config/env.
- [x] Location hard-delete behavior when residents exist: reject or require replacement location. (Chosen: cascade delete residents)
- [ ] Reindex job state persistence mode: Neo4j-backed persistent jobs (recommended) vs in-memory temporary jobs.

## Change Log
- 2026-04-15: Tracker reset for v1.3 and M6 started.
- 2026-04-15: M6 completed (schema layer foundation + v1 route prefix + /v1/schema + startup fail-fast).
- 2026-04-15: M7/M8 foundation implemented (typed patch models, graph services, graph/admin routes, scope inheritance, soft delete, move, admin relation ops).
- 2026-04-15: Completed edge create/delete routes, typed move body, referential-integrity edge writes, and async in-memory reindex job states.
- 2026-04-15: Verification slice passed: `tests/unit/test_graph_v13_routes.py`, `tests/unit/test_graph_edit_service_edges.py`, `tests/unit/test_graph_admin_reindex_jobs.py`, `tests/unit/test_v1_route_versioning.py`, `tests/unit/test_schema_loader.py`, `tests/unit/test_auth_permissions_v13.py`.
- 2026-04-15: Final verification rerun passed for current v1.3 slice: `ruff check .`, `mypy .`, and the focused unit suite (12 passed).
- 2026-04-16: M9 completed. Verified `make lint`, `make type`, `make test-v13-contracts`, `make test-v13-graph-admin`, `make test-v13-retrieval`, `make test-cov-v13` (87.21%), `make check`, and `make test-cov-full-report`.
