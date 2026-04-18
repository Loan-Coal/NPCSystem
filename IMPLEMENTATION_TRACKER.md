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
Status: TODO
Started: 
Completed: 
Checkpoint: CP4_CONTRACTS_SIM

Tasks:
- [ ] Add contract tests for dialogue, quest, and currency engines.
- [ ] Add CI guard that contract YAML changes require matching test updates.
- [ ] Add deterministic scenario test suite for PR runs.
- [ ] Add `scripts/simulate_world_flow.py` with stable JSON summary output.

Verification:
```bash
cd npc_engine
make check-contracts
pytest -q tests/engine_contract_tests
python -m scripts.simulate_world_flow
```

### P5 - Observability and Dashboards
Status: TODO
Started: 
Completed: 
Checkpoint: CP5_OBSERVABILITY

Tasks:
- [ ] Add v1.4 metrics for context, LLM, graph writes, currency, and validation failures.
- [ ] Add structured logs with request correlation and bounded-cardinality labels.
- [ ] Add alert rules and dashboard definitions for staging profile.

Verification:
```bash
cd npc_engine
make lint
make type
pytest -q tests/unit -k "metrics or observability"
```

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

## v1.3 Archive
- M6, M7, M8, M9 were completed on 2026-04-15 to 2026-04-16.
- Details are preserved in git history prior to this tracker migration.
