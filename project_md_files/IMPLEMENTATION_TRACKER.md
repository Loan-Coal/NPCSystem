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
- Extended `graph/event_writer.py` + `graph/node_schemas.py` to enforce quest event provenance payload fields.
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
