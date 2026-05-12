# NPC Engine v1.4 Implementation Tracker

This file tracks iterative implementation for PROJECT_PLAN_v1.4.xml and supports interruption/resume.

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

### Phase 3 — World Depth
Status: IN_PROGRESS
Started: 2026-05-11
Completed:

#### Feature 3.1 — Time as a first-class concept
Status: DONE
Started: 2026-05-11
Completed: 2026-05-11
Commit: feat: structured game time (Phase 3.1)

#### Feature 3.2 — Memories vs Knowledge
Status: DONE
Started: 2026-05-11
Completed: 2026-05-12
Commit: feat: memory nodes and formation (Phase 3.2)
Tasks:
- [x] `type_registry/base_nodes/memory.yaml` — Memory node schema
- [x] `type_registry/base_edges/remembers.yaml` — REMEMBERS edge schema
- [x] `type_registry/base_edges/about.yaml` — ABOUT edge schema
- [x] `graph/memory_queries.py` — Cypher strings + read accessor
- [x] `graph/memory_service.py` — create/get/decay (≤200 lines)
- [x] `engines/memory/__init__.py` + `engines/memory/memory_engine.py` (≤150 lines)
- [x] `engines/dialogue/dialogue_handler.py` — high-arousal hook
- [x] `retrieval/context_builder.py` — Tier A memories hook
- [x] `tests/unit/test_memory_service.py` — 7 unit tests
- [x] `e2e/scenarios/scenario_memory_formation.py`
Tasks:
- [x] `world/world_state.py` — add `year`, `season`, `day` fields
- [x] `world/world_writer.py` — persist all time fields in CYPHER + upsert
- [x] `engines/events/event_handler.py` — sync CYPHER copy
- [x] `world/time_utils.py` — `TimePoint`, `how_long_ago` (new, ≤80 lines)
- [x] `world/world_time_service.py` — `advance_time` (new, ≤120 lines)
- [x] `api/routes/clock.py` — extend with `advance_time_field`
- [x] `tests/unit/test_world_time_service.py` — 15 cases (all green)
- [x] `e2e/scenarios/scenario_time_passage.py`
- [x] `project/DECISIONS.md` — how_long_ago gap entry
- [x] `project/ISSUES.md` — ISSUE-012 (fixed), ISSUE-013 (open)

Verification:
```bash
pytest tests/unit/test_world_time_service.py -v
pytest tests/ -q
python e2e/scenarios/scenario_time_passage.py
```

---

### Phase 2 — Routine Engine
Status: DONE
Started: 2026-05-11
Completed: 2026-05-11

#### Feature 2.1 — Schedule nodes and edges
Status: DONE
Started: 2026-05-11
Completed: 2026-05-11
Commit: routine schedule (6623c3b)
Tasks:
- [x] `type_registry/base_nodes/schedule.yaml`
- [x] `type_registry/base_edges/follows_schedule.yaml`
- [x] `WorldState.time_of_day` field added to `world/world_state.py`
- [x] `Character.routine_override` JSON field added to Character schema
- [x] `graph/schedule_service.py` (≤300 lines)
- [x] `graph/schedule_queries.py` (Cypher strings)
- [x] `tests/unit/test_schedule_service.py`
- [ ] `tests/integration/test_schedule_service.py` — deferred (requires test Neo4j)
- [x] `api/routes/schedules.py` wired into main.py
- [x] `e2e/scenarios/scenario_daily_life.py` (query-only stage)
- [x] `docs/DATA_MODELS.md` updated

#### Feature 2.2 — Routine engine
Status: DONE
Started: 2026-05-11
Completed: 2026-05-11
Tasks:
- [x] `engines/routine/__init__.py`
- [x] `engines/routine/routine_engine.py` (≤300 lines)
- [x] `engines/routine/routine_queries.py`
- [x] `scheduler/tick_scheduler.py` updated to call `RoutineEngine.run_tick`
- [x] `api/dependency_singletons.py` updated with `get_routine_engine`
- [x] `tests/unit/test_routine_engine.py` (8 tests)
- [ ] `tests/integration/test_routine_engine.py` — deferred (requires test Neo4j)
- [x] `e2e/scenarios/scenario_daily_life.py` extended (tick advance + location assert)
- [ ] Integration test: gossip pairs reflect schedule-driven LOCATED_AT — deferred

Verification:
```bash
pytest tests/unit/test_routine_engine.py -v
pytest tests/integration/test_routine_engine.py -v
python e2e/scenarios/scenario_daily_life.py
pytest tests/ -q && make lint && make type
```

#### Feature 2.3 — Routine disruption
Status: DONE
Started: 2026-05-11
Completed: 2026-05-11
Commit: feat: routine disruption rules (Phase 2.3)
Tasks:
- [x] `engines/events/disruption_rules.yaml`
- [x] `engines/events/disruption_loader.py`
- [x] `engines/routine/routine_queries.py` — `set_routine_override` added
- [x] Disruption trigger wired into `engines/events/event_handler.py`
- [x] Emotion valence < -60 → stay-home override wired in `engines/dialogue/dialogue_handler.py`
- [x] Override expiry handled atomically in routine engine (pre-existing, Phase 2.2)
- [x] `tests/unit/test_routine_disruption.py` (11 tests)
- [x] E2E disruption scenario added to `scenario_daily_life.py`

Verification:
```bash
pytest tests/unit/test_routine_disruption.py -v
python e2e/scenarios/scenario_daily_life.py
pytest tests/ -q && make lint && make type
```

---

### P0 - Config and Contract Foundations
Status: DONE
Started: 2026-04-16
Completed: 2026-04-16
Checkpoint: CP0_FOUNDATION

Tasks:
- [x] Add `config/llm_config.yaml` and typed `LLMConfig` model/loader.
- [x] Wire `LLM_CONFIG_PATH` startup fail-fast validation in app lifespan.
- [x] Add v1.4 idempotency header preflight contract in middleware (`X-Idempotency-Key` missing/invalid).
- [x] Add stable idempotency error payloads (`IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_KEY_INVALID`).
- [x] Add initial engine contract schema/models and contract YAMLs (`dialogue`, `quest`, `currency`).
- [x] Add `make check-contracts` and v1.4 P0 verification target.
- [x] Add Neo4j idempotency record schema and persistence behavior (`pending`, `completed`, `failed_terminal`).
- [x] Add `engines/idempotency/cleanup_scheduler.py` with periodic expiry cleanup.
- [x] Add optional Redis runtime integration for non-idempotency caches.
- [x] Add write-path convergence design document (P0 deliverable).

Verification:
```bash
cd npc_engine
make verify-v14-p0
make test-v13-contracts
make test-v13-graph-admin
```

Notes:
- Current enforcement toggle is config-driven (`IDEMPOTENCY_ENFORCE_HEADER`) for safe rollout.
- P0 now includes persistent idempotency replay semantics backed by Neo4j `IdempotencyRecord` nodes.
- Write-path convergence design deliverable added at `WRITE_PATH_CONVERGENCE_P0.md`.
- Existing v1.3 behavior validated with regression smoke targets after P0 changes.

### P1 - Context Relevance and Budget Pipeline
Status: DONE
Started: 2026-04-17
Completed: 2026-04-17
Checkpoint: CP1_CONTEXT_BUDGET

Tasks:
- [x] Add deterministic `ContextRelevanceEngine` scoring with tie-break rules.
- [x] Add `retrieval/context_budget_enforcer.py` tier-aware budget policy.
- [x] Add compression integration and cache keyed by `(node_id, node_type, prompt_schema_version, compression_prompt_version)`.
- [x] Enforce Tier A/session turns never compressed.
- [x] Raise typed context budget error when Tier A exceeds budget.

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/unit -k "relevance or budget"
```

Notes:
- `engines/dialogue/context_relevance_engine.py` provides deterministic weighted scoring + tie-break ordering.
- `retrieval/context_budget_enforcer.py` enforces tier budgets, Tier A/session non-compression, and compression cache behavior.
- Dialogue REST and WebSocket flows now pass typed `LLMConfig` into context building.
- P1 hardening verification completed: final serialized overflow trimming now drops Tier C before Tier B, and compression cache reuse requires source-hash match even when graph timestamp is unchanged.

### P2 - Currency Safety and Trading Atomicity
Status: DONE
Started: 2026-04-17
Completed: 2026-04-17
Checkpoint: CP2_CURRENCY

Tasks:
- [x] Add `engines/economy/currency_verification_engine.py`.
- [x] Add `graph/currency_writer.py` with atomic debit/credit + audit edge writes.
- [x] Route buy/sell through single transaction coordinator path.
- [x] Enforce per-transaction and per-session bounds from config.
- [x] Add idempotency replay safety for currency writes.

Verification:
```bash
cd npc_engine
make verify-v14-p2
```

Notes:
- Added `engines/economy/currency_verification_engine.py` for strict amount and bounds validation.
- Added `graph/currency_writer.py` for atomic debit/credit write + `TRANSFERRED_TO` audit edge persistence.
- Added `graph.graph_writer.apply_buy_sell_currency_transfer(...)` as single buy/sell coordinator path.
- Extended `api/routes/action.py` and `api/schemas.py` to route buy/sell actions through the coordinator.
- Added P2 unit tests: currency verification, atomic writer, coordinator routing, and action route coverage.

### P3 - Quest Lifecycle Integration
Status: DONE
Started: 2026-04-17
Completed: 2026-04-17
Checkpoint: CP3_QUESTS

Tasks:
- [x] Add quest lifecycle methods (offer/accept/update/evaluate/reward).
- [x] Route item rewards via trading path and currency rewards via currency engine.
- [x] Enforce event provenance fields on quest lifecycle events.
- [x] Complete write-path convergence for quest reward writes.

Verification:
```bash
cd npc_engine
make verify-v14-p3
```

Notes:
- Added `engines/quest/quest_lifecycle_engine.py` and `engines/quest/models.py` to implement quest lifecycle transitions with typed state.
- Added `api/routes/quest.py` + quest request models and registered `/v1/quest/*` routes in app wiring.
- Added `engines/economy/trading_engine.py` and `graph/item_writer.py` so item rewards route through a dedicated trading path.
- Extended `graph/graph_writer.py` with `apply_currency_transfer(...)` and `apply_item_transfer(...)` coordinator entrypoints; buy/sell now delegates through generic currency coordinator.
- Extended `graph/event_writer.py` + registry-generated event models to enforce quest event provenance payload fields.
- Added `graph/quest_writer.py` for persisted quest state records.
- Added P3 unit/integration tests and `make test-v14-p3` / `make verify-v14-p3` targets.

### P4 - Contracts, Tests, and Simulation
Status: DONE
Started: 2026-04-18
Completed: 2026-04-18
Checkpoint: CP4_CONTRACTS_SIM

Tasks:
- [x] Add contract tests for dialogue, quest, and currency engines.
- [x] Add CI guard that contract YAML changes require matching test updates.
- [x] Add deterministic scenario test suite for PR runs.
- [x] Add `scripts/simulate_world_flow.py` with stable JSON summary output.

Verification:
```bash
cd npc_engine
make check-contracts
pytest -q tests/engine_contract_tests
python -m scripts.simulate_world_flow
pytest -q tests/unit/test_simulate_world_flow_v14.py tests/unit/test_guard_contract_test_sync_v14.py
make check-contract-sync
make lint
make type
```

Notes:
- Added `tests/engine_contract_tests/test_dialogue_contract.py`, `test_quest_contract.py`, and `test_currency_contract.py` for engine contract conformance.
- Added `scripts/guard_contract_test_sync.py` and `tests/unit/test_guard_contract_test_sync_v14.py` for contract-YAML/test-sync CI enforcement.
- Added `scripts/simulate_world_flow.py` and `tests/unit/test_simulate_world_flow_v14.py` with deterministic JSON summary assertions.
- Added `test-v14-p4`, `check-contract-sync`, and `verify-v14-p4` targets in `npc_engine/Makefile`.
- Added `v14-p4-gates` job in `.github/workflows/ci.yml` to run contract validation, PR sync guard, and P4 tests.

### P5 - Observability and Dashboards
Status: DONE
Started: 2026-04-18
Completed: 2026-04-18
Checkpoint: CP5_OBSERVABILITY

Tasks:
- [x] Add v1.4 metrics for context, LLM, graph writes, currency, and validation failures.
- [x] Add structured logs with request correlation and bounded-cardinality labels.
- [x] Add alert rules and dashboard definitions for staging profile.

Verification:
```bash
cd npc_engine
make test-v14-p5
make lint
make type
make verify-v14-p5
```

Notes:
- Added in-memory observability registry and bounded label helpers in `npc_engine/utils/metrics.py`.
- Extended JSON structured logging in `npc_engine/utils/logging.py` to include request correlation and extra fields.
- Instrumented `auth/middleware.py` for request-level observability metrics/logs and validation-failure counters.
- Instrumented `retrieval/context_builder.py` for context tier selection tokens, budget errors, and compression metrics.
- Instrumented `engines/dialogue/llm_client.py` and `engines/dialogue/dialogue_handler.py` for LLM calls/tokens and validation failure metrics.
- Instrumented `graph/graph_writer.py` for graph write throughput/latency and currency transfer outcome metrics.
- Added P5 observability tests:
	- `tests/unit/test_metrics_observability_v14.py`
	- `tests/unit/test_auth_observability_middleware_v14.py`
	- `tests/unit/test_context_metrics_observability_v14.py`
	- `tests/unit/test_llm_metrics_observability_v14.py`
	- `tests/unit/test_graph_writer_metrics_observability_v14.py`
- Added staging observability artifacts in `npc_engine/observability/`:
	- `staging_dashboard.json`
	- `staging_alert_rules.yaml`
	- `README.md`
- Added `test-v14-p5` and `verify-v14-p5` targets in `npc_engine/Makefile` and `v14-p5-gates` job in `.github/workflows/ci.yml`.

### P6 - Migration and Cutover Validation
Status: TODO
Started: 
Completed: 
Checkpoint: CP6_MIGRATION

Tasks:
- [ ] Add migration scripts for event provenance backfill.
- [ ] Add migration scripts for currency initialization.
- [ ] Add dry-run report and rollback drill scripts.
- [ ] Validate cutover checklist on staging snapshot.

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/integration -k "migration"
```

## Decisions Needed
- [ ] Should `IDEMPOTENCY_ENFORCE_HEADER` default to true once P0 idempotency storage is implemented?
- [ ] Confirm Redis deployment profile and health-check strategy for optional non-idempotency caches in local docker-compose.
- [x] Approve exact location/format for write-path convergence design doc deliverable (`WRITE_PATH_CONVERGENCE_P0.md`, Markdown at repo root).

## Change Log
- 2026-04-16: Tracker migrated from v1.3 stages (M6-M9) to v1.4 stages (P0-P6).
- 2026-04-16: P0 slice implemented: idempotency header preflight contract, llm_config typed loader + startup validation, contract schema/YAML/checker, and verification targets.
- 2026-04-16: Verified `make verify-v14-p0`, `make test-v13-contracts`, and `make test-v13-graph-admin`.
- 2026-04-16: P0 completed with idempotency persistence/finalization, cleanup scheduler, optional Redis runtime wiring, and write-path convergence document.
- 2026-04-17: P1 completed with deterministic relevance ranking, tier-aware budget enforcement, compression cache, and pipeline integration tests.
- 2026-04-17: P1 hardening verified and fixed (tier drop order + compression cache source-hash guard).
- 2026-04-17: P2 completed with currency verification engine, atomic currency writer, buy/sell coordinator routing, idempotency replay-safe transfer behavior, and `make verify-v14-p2` green.
- 2026-04-18: P4 completed with engine contract conformance tests, deterministic world-flow simulation script, contract/test sync guard, CI wiring, and verification passes.
- 2026-04-18: P5 completed with bounded observability metrics, structured request correlation logs, staging dashboard+alert definitions, and `make verify-v14-p5` green.

## v1.3 Archive
- M6, M7, M8, M9 were completed on 2026-04-15 to 2026-04-16.
- Details are preserved in git history prior to this tracker migration.

## Codebase Trimming Initiative (Module-by-Module)
Status: IN_PROGRESS
Started: 2026-04-18
Completed:
Checkpoint: TRIM_MODULAR_P0

Guardrails (User Confirmed):
- Public compatibility freeze: none.
- Uncertain deletions: ask case-by-case before removal.
- Shared helper location: `common/` package.
- Tradeoff policy: readability wins when size impact is small.
- Logging policy: ask per module before removing redundant logs.
- Validation cadence: targeted tests per module, one full-suite pass at the end.
- Ambiguity policy: stop and ask immediately.

Module Progress Table:

| Priority | Module | Status | Scan Done | Dedupe Done | Dead Code Removed | Module Tests | Ambiguities | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | utils | DONE | Yes | Yes | No (deferred by decision) | Passed | GraphUnavailableError kept by user decision | Centralized dataclass error string formatting and simplified route-prefix label mapping in metrics. |
| 2 | world | DONE | Yes | Yes | No | Passed | None | Added shared `common/json_utils.py` and removed duplicated JSON coercion logic in world reader/writer. |
| 3 | cache | DONE | Yes | No changes needed | No changes needed | Not Run | None | Module already minimal; no safe dedupe/dead-code trims found. |
| 4 | mutation | DONE | Yes | Yes | No | Passed | None | Reused shared structured error base for bounds exception and removed duplicate __str__ logic. |
| 5 | schema | DONE | Yes | Yes | No | Passed | None | Extracted shared YAML loader and semantic-field resolver helpers; reduced duplicate loader/resolver logic. |
| 6 | auth | DONE | Yes | Yes | Yes | Passed | None | Removed unused `validate_bearer_token`/`verify_api_key` (user-approved) and consolidated repeated validation-failure observability logic in middleware. |
| 7 | engines.contracts | DONE | Yes | Yes | No | Passed | None | Contract loader now reuses shared YAML mapping helper and removes duplicated parse/root-check code. |
| 8 | engines.llm | DONE | Yes | Yes | Yes (unused arg cleanup) | Passed | None | Replaced duplicated Llama adapter implementation with thin subclass over Mistral adapter; cleaned unused factory arg. |
| 9 | engines.emotion | DONE | Yes | No changes needed | No changes needed | Not Run | None | Module already concise; no safe dedupe/dead-code trims identified. |
| 10 | engines.economy | DONE | Yes | No changes needed | No changes needed | Not Run | None | Validation logic is compact and explicit; no safe dedupe/dead-code trims identified. |
| 11 | engines.quest | DONE | Yes | Yes | No | Passed | None | Extracted shared quest lifecycle helpers for transaction-session checks and event construction. |
| 12 | engines.events | DONE | Yes | Yes | Yes | Passed | None | Reused shared JSON helpers in event world-state updates and removed unused `seed_awareness` function (user-approved). |
| 13 | engines.gossip | DONE | Yes | Yes | Yes | Passed | None | Reused shared JSON helpers in edge log updates and removed unused `_apply_template` parameter. |
| 14 | scheduler | DONE | Yes | Yes | No | Passed | None | Extracted shared distributed-lease engine tick runner to remove duplicated gossip/event lease flow. |
| 15 | retrieval | DONE | Yes | Yes | No | Passed | None | Added shared retrieval context utils (token estimate, identity parse, deterministic JSON serialize) and removed duplicated logic across builder/budget/subgraph/serializer. |
| 16 | graph | DONE | Yes | Yes | Yes (unused helper removed) | Passed | Preserved defensive JSON safety by user decision | Added shared provenance-field serializer and shared idempotent replay helper; removed unused graph_edit_service helper. |
| 17 | engines.dialogue | DONE | Yes | Yes | No | Passed | Kept handler fallback by user decision | Reused shared token estimator in llm_client and preserved handler-level validation fallback contract. |
| 18 | api | DONE | Yes | Yes | No | Passed | Kept action ignored semantics by user decision | Standardized quest errors to HTTPException with typed envelope detail, wrapped batch/clock/system success payloads in canonical envelope, and deduped graph route not-found checks with shared helper. |
| 19 | config+main composition | TODO | No | No | No | Not Run | None | |
| 20 | scripts | TODO | No | No | No | Not Run | None | |

Recommendation Backlog (Ask Before Applying):

| Rec ID | Recommendation | Expected Size Impact | Risk | User Decision | Status |
|---|---|---|---|---|---|
| R-01 | Introduce shared JSON-safe serialization/parsing helpers under `common/` | Medium | Low | Accepted | Applied in utils/world |
| R-02 | Consolidate repeated API error/response wrapping helpers | Medium | Medium | Accepted | Applied in api routes/helpers |
| R-03 | Consolidate repeated graph query fragments/constants | Medium | Medium | Pending | Proposed |
| R-04 | Consolidate request/session/time helper logic where duplicated | Low-Medium | Low | Pending | Proposed |

Final Verification (Run Once After All Modules):

| Check | Status | Notes |
|---|---|---|
| Global lint | Pending | |
| Global type check | Pending | |
| Full test suite | Pending | |
| Coverage check | Pending | |
| Runtime smoke checks | Pending | |
| One-time full code review | Pending | |

## Graph Type Registry Refactor (Generic Graph API)
Status: IN_PROGRESS
Started: 2026-04-19
Completed:
Checkpoint: REGISTRY_R0

Goal:
- Replace typed graph CRUD surface with a schema-registry-driven generic node/edge API.
- Keep non-removable base attributes for base node/edge types.
- Allow additive extensions only (add fields, add node types, add edge types).

Confirmed Constraints (User):
- Runtime safety > developer ergonomics > speed of adding content.
- No backward compatibility requirement; legacy routes can be removed.
- Extension fields are metadata-only for now (no engine behavior coupling yet).
- No schema migration tooling required.
- Extension fields should be queryable by default; NOT indexable by default.
- Edge definitions are the single source of truth for topology (src_type/dst_type). Node-side edge allow-lists are not used.
- Extension identifiers (node types, edge types, field names) are developer-defined and unrestricted by pattern; collisions are rejected.

Package Naming: `type_registry` (decided).

### R0 - Contract and Registry Format Decisions
Status: TODO
Started:
Completed:
Checkpoint: REGISTRY_R0

Tasks:
- [x] Finalize package/folder naming → `type_registry`.
- [x] Freeze external extension file format → YAML only.
- [x] Decide deploy-time-only vs hot reload → deploy-time-only.
- [x] Decide per-field byte cap value → 512 bytes per attribute, enforced independently per field.
- [x] Decide config location for byte caps → per-type definition file.
- [x] Define warning contract schema for API metadata + logs (stable warning_code/message/type + optional context fields).
- [x] Decide LIST endpoint pagination baseline → offset-first with default `limit=50`.
- [x] Decide pagination architecture → isolated pagination module, easily swappable strategy, no strategy-specific branching outside pagination module.
- [x] Decide LIST pagination remaining knobs → max page size `200`, default sort `id ASC`.

Verification:
```bash
cd npc_engine
pytest -q tests/unit -k "schema or registry"
```

### R1 - Registry Foundation
Status: DONE
Started: 2026-04-19
Completed: 2026-04-19
Checkpoint: REGISTRY_R1

Tasks:
- [x] Add registry package skeleton (base contracts, extension loader, merge rules).
- [x] Enforce additive-only merges and non-removable base attributes.
- [x] Enforce constraints frozen once declared (no post-declaration constraint mutation).
- [x] Build one immutable registry singleton at startup.
- [x] Fail-fast startup when extension files are invalid or contain duplicate field names.

Increment Notes (2026-04-19):
- Added `npc_engine/type_registry/` package with contracts, extension loader, merge rules, and build facade.
- Added config-driven extension source setting: `TYPE_REGISTRY_EXTENSION_SOURCES`.
- Startup now builds and caches one immutable registry singleton in app lifespan before runtime service startup.
- Added unit coverage for additive merge behavior, duplicate-name collision, constraint mutation, invalid extension file shape, and singleton immutability.

Verification:
```bash
cd npc_engine
pytest -q tests/unit/test_type_registry_foundation.py tests/unit/test_main_reconciler_lifespan.py tests/unit/test_schema_loader.py tests/unit/test_graph_v13_routes.py tests/unit/test_v1_route_versioning.py
# Result: 13 passed
```

### R2 - Topology and Validation Engine
Status: DONE
Started: 2026-04-19
Completed: 2026-04-19
Checkpoint: REGISTRY_R2

Tasks:
- [x] Enforce edge endpoint compatibility (`src_type`, `dst_type`) via registry — edge definitions are the sole topology authority.
- [x] Add generic payload validator for create/update operations.
- [x] Enforce base required attributes as hard requirements (null forbidden for base fields).
- [x] Enforce extension field type/range/shape validation.
- [x] Implement PATCH semantics: omitted fields = keep existing; explicit null forbidden for base fields, allowed for extension fields.

Increment Notes (2026-04-19):
- Added package-internal base contract folders: `type_registry/base_nodes/*.yaml` and `type_registry/base_edges/*.yaml` (one file per base type).
- Added startup loader for package-internal base contracts and merged these into immutable `TypeRegistry` runtime state.
- Added generic validation module for topology and payload checks: endpoint compatibility, unknown fields, required/base-null rules, type/range checks, and PATCH merge semantics.
- Kept external extension source format comma-delimited (`TYPE_REGISTRY_EXTENSION_SOURCES`) as requested.

Verification:
```bash
cd npc_engine
pytest -q tests/unit/test_type_registry_validator.py tests/unit/test_type_registry_foundation.py tests/unit/test_main_reconciler_lifespan.py tests/unit/test_schema_loader.py tests/unit/test_graph_v13_routes.py tests/unit/test_v1_route_versioning.py
# Result: 19 passed
```

### R3 - Warnings and Limits
Status: DONE
Started: 2026-04-19
Completed: 2026-04-19
Checkpoint: REGISTRY_R3

Tasks:
- [x] Emit warnings for missing extension values in API response metadata.
- [x] Emit corresponding structured warning logs with request correlation (reuse existing P5 observability infrastructure).
- [x] Add warning metrics by warning code (reuse existing in-memory metrics registry from P5).
- [x] Enforce 512-byte per-field UTF-8 byte cap and produce typed limit warnings/errors.
- [x] Enforce 16 extension fields max per object type and produce typed limit errors.

Increment Notes (2026-04-19):
- Added graph warning pipeline helpers to attach warnings into API response metadata and emit structured warning logs/metrics (`graph_warnings_total`) with request correlation ids.
- Added per-field `max_bytes` contracts (default `512`) in schema/base/runtime field models and enforced byte budgets in runtime payload validation.
- Added startup-time extension field count enforcement (`max 16`) in registry merge rules for core/custom object types.

Verification:
```bash
cd npc_engine
pytest -q tests/unit/test_type_registry_limits.py tests/unit/test_graph_warning_pipeline.py
# Result: 2 passed, 1 skipped
```

### R4 - Generic Graph Endpoints
Status: DONE
Started: 2026-04-19
Completed: 2026-04-19
Checkpoint: REGISTRY_R4

Tasks:
- [x] Add generic node endpoints (`POST/GET/PATCH/LIST /v1/graph/nodes/{node_type}`).
- [x] Add generic edge endpoints (`POST/GET/DELETE/LIST /v1/graph/edges/{edge_type}`).
- [x] Implement LIST pagination per R0 pagination policy decision.
- [x] Implement pagination via a self-contained pagination module so future cursor migration does not require endpoint/service rewrites.
- [x] Add schema introspection endpoint for clients (`/v1/schema/registry`).
- [x] Enforce Cypher safety via value parameterization + registry allow-list validation for dynamic labels/edge-types/property names (security acceptance criterion — must pass before R4 closes).
- [x] Remove legacy typed graph CRUD routes after parity verification.

Increment Notes (2026-04-19):
- Replaced typed graph routes with one generic route surface in `api/routes/graph.py`.
- Added `GenericGraphService` and `generic_graph_utils` for registry-driven node/edge CRUD and safe dynamic Cypher identifiers.
- Added isolated pagination strategy module (`api/pagination.py`) and wired generic list endpoints through it.
- Added registry introspection serializer and endpoint (`GET /v1/schema/registry`).
- Removed legacy typed service path (`graph/graph_edit_service.py`) and obsolete typed graph request models from `api/schemas.py`.
- Updated dependency wiring to use `get_generic_graph_service` only.
- Updated route/version/auth/metrics tests for generic route contracts and replaced typed service tests with `test_generic_graph_service.py`.

Verification:
```bash
cd npc_engine
pytest -q tests/unit/test_pagination_strategy.py tests/unit/test_registry_serializer.py tests/unit/test_graph_v13_routes.py tests/unit/test_v1_route_versioning.py tests/unit/test_type_registry_validator.py tests/unit/test_generic_graph_service.py tests/unit/test_system_registry_route.py
# Result: 14 passed, 5 skipped
```

### R5 - Indexing and Queryability
Status: TODO
Started:
Completed:
Checkpoint: REGISTRY_R5

Tasks:
- [ ] Build index/constraint plan from registry definitions (base fields only; extension fields not indexed).
- [ ] Apply startup index plan and report applied/skipped indexes.
- [ ] Verify extension fields are queryable but NOT indexed by default.

Verification:
```bash
cd npc_engine
pytest -q tests/integration -k "index or query"
```

### R6 - Hardening and Cutover
Status: TODO
Started:
Completed:
Checkpoint: REGISTRY_R6

Tasks:
- [ ] Remove obsolete route/service/validator paths superseded by registry.
- [ ] Run full verification loop (lint, type, unit, integration).
- [ ] Update architecture docs and developer extension authoring guide (highlight: constraints are frozen once declared; no migration tooling; edge definitions are topology authority).

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q
```

Open Decisions (Needs User Confirmation):
- [x] Generic endpoints only vs hybrid surface (chosen: generic-only).
- [x] Deploy-time-only schema loading vs hot reload (chosen: deploy-time-only).
- [x] Default indexing strategy for extension fields (chosen: not indexable by default).
- [x] Limit semantics for text budgets (chosen: UTF-8 bytes, 512 bytes per field, enforced independently).
- [x] Topology authority (chosen: edge definition wins; node-side allow-lists removed).
- [x] PATCH omission semantics (chosen: omitted fields keep existing value; explicit null forbidden for base fields).
- [x] Constraint mutability (chosen: frozen once declared).
- [x] LIST pagination remaining knobs (chosen: max page size `200`, default sort `id ASC`).

Decision Log (2026-04-18):
- [x] Unknown fields policy: fail hard when field is neither base nor declared extension.
- [x] Extension merge policy: additive-only (no removal of base attributes/types, no constraint updates after declaration).
- [x] Delivery channels for extension warnings: API metadata + structured logs.
- [x] Schema loading policy: deploy-time-only (no hot reload in initial design).
- [x] Registry package name: `type_registry`.
- [x] Topology validation policy: edge endpoint type validation only (`src_type`/`dst_type` on edge definitions). Node-side edge allow-lists are not used — edge definitions are the sole topology authority.
- [x] Extension file format: YAML only.
- [x] Create behavior for missing extension fields: do not autofill; warn and persist null for extension fields only.
- [x] Unknown field strictness across environments: always hard-fail.
- [x] Extension constraint scope (initial): primitive types + range only.
- [x] Constraint mutability: constraints are frozen once declared; no post-declaration updates allowed.
- [x] Queryability policy: extension fields should be queryable.
- [x] Extension indexing policy (default): extension fields should NOT be indexable by default.
- [x] Missing extension values on create: persist null and emit warnings.
- [x] Schema introspection scope: keep initial output simple; do not expose full internal policy metadata yet.
- [x] Query guardrails policy (initial): do not add query guardrails yet.
- [x] Write-time payload limits: enforce 512 bytes per-field UTF-8 byte cap, applied independently per attribute, for both base and extension fields.
- [x] Config location policy: per-type max byte caps live in the same type definition file.
- [x] Schema introspection minimum fields: field_name, field_type, field_origin (base|extension).
- [x] Query endpoint scope (initial): storage and return only; no extension-filter query operators yet.
- [x] Extension count policy: enforce one global hard max of 16 extension fields per object type.
- [x] Missing value persistence policy: null allowed for extension fields only; null forbidden for base fields.
- [x] Expensive extension query behavior: return warning and continue.
- [x] Warning payload contract: stable `warning_code` + `message` + `type`, with optional context fields (for example `duration_ms`, `scanned_record_count`, `node_type`, `edge_type`, `field_name`).
- [x] Field naming policy: developer-defined identifier names allowed; uniqueness enforced via collision checks.
- [x] Duplicate field-name collision policy: fail hard when extension field name collides with existing base/extension name.
- [x] Missing extension values on PATCH: explicit null allowed for extension fields only; explicit null forbidden for base fields.
- [x] PATCH omission semantics: omitted fields keep their existing value (standard PATCH semantics); explicit null on a base field is a validation error.
- [x] Expensive query warning trigger: query duration > 100 ms. Include scanned_record_count in warning payload when available.
- [x] Cypher security policy: parameterize all values; dynamic labels/edge-types/property names may be any developer-defined names declared in registry, with collision checks and safe query construction. Verified as R4 acceptance criterion before milestone closes.
- [x] Base contract source policy: package-internal immutable contract files under `type_registry/base_nodes/` and `type_registry/base_edges/`, one YAML file per base type.
- [x] External extension source format policy: keep `TYPE_REGISTRY_EXTENSION_SOURCES` comma-delimited.
- [x] Base contract shape policy: allow typed non-primitive list/dict field shapes in package-internal base contract files.
