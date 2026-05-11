# Status

## Project Health

| | |
|---|---|
| **Current phase** | Phase 2 — Routine engine |
| **Phase 1** | ✅ Complete — Faction nodes (1.1), Faction-aware gossip (1.2), Faction reputation (1.3) |
| **Foundation** | ✅ Phase 0 complete — 27 services refactored, all layer violations resolved |
| **Open issues** | 4 — see [ISSUES.md](ISSUES.md) (all P3, none block Phase 2) |
| **Next action** | Read [NEXT_SESSION.md](NEXT_SESSION.md) then start Feature 2.1 |

### CI / Coverage Badges

> Badges are not yet active. To enable them:
> 1. Confirm `.github/workflows/ci.yml` runs on push (it exists — verify the trigger).
> 2. Register the repo with [Codecov](https://codecov.io) and add `CODECOV_TOKEN` as a repository secret.
> 3. Replace the placeholder lines below with the real badge URLs from Codecov and GitHub Actions.

```
[![CI](https://github.com/YOUR_ORG/npc-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/npc-engine/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/YOUR_ORG/npc-engine/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_ORG/npc-engine)
```

---

## Phase 1 — Faction vertical slice
**Status:** ✅ Complete
**Date completed:** 2026-05-11
**Commits:** faction node and membership / faction aware gossip / faction reputation

### What was done
- **1.1**: Faction node + MEMBER_OF, STANDS_WITH, CONTROLS edges; `graph/faction_service.py`; admin API routes under `/v1/admin/factions/`; `e2e/scripts/faction_setup.py`; `docs/DATA_MODELS.md` updated
- **1.2**: Faction-aware gossip pair selection + distortion weights; `engines/gossip/gossip_config.py`; property tests; `e2e/scenarios/scenario_factional_rumor.py`
- **1.3**: `HAS_REPUTATION_WITH` edge; reputation service; context Tier A integration; `e2e/scenarios/scenario_reputation_drift.py`

### Open deferred items
- ISSUE-005: `adjust_reputation_for_event` not wired into event engine (P3, not a Phase 2 blocker)
- ISSUE-006: pre-existing `Character.faction` string field not migrated to `MEMBER_OF` edge (P3)

---

## Phase 0.5 — Stability cleanup (ISSUES 001–003)
**Status:** ✅ Complete
**Date completed:** 2026-05-06
**Tests:** run after session to confirm green

### What was done
- **ISSUE-001**: Added `top_p: float | None = None` and `stop_sequences: list[str] | None = None` to `LLMClientProtocol.generate`, `generate_structured`, and `stream`. All three adapters (Ollama, Mistral, Mock) accept and forward both params. `DialogueLLMClient` stores and forwards them; `DialogueHandler` passes them from `engine_model_config.llm`. New adapter payload-forwarding tests added.
- **ISSUE-002**: Renamed `engines/economy/` → `engines/currency/` to match `_engine_dir_from_contract_name("currency_engine")` convention. Directory was a namespace stub only; no import changes needed.
- **ISSUE-003**: Removed `create_llm_client()`, `BACKEND_BUILDERS`, and all `_create_*` helpers from `factory.py` (zero callers confirmed). Removed `LLM_BACKEND` and `OLLAMA_MODEL` from `config.py`. Rewrote `test_llm_factory.py` to cover `create_llm_client_for_engine` with per-engine config fixtures.

---

## Phase 0.4 — Per-engine LLM Config
**Status:** ✅ Complete
**Date completed:** 2026-05-05
**Tests:** 325 passed, 2 skipped, 0 failed

### What was done
- Added `uses_llm: bool` field to `EngineContract`; set `true` in `dialogue_engine.yaml`, `false` in `quest_engine.yaml` and `currency_engine.yaml`
- New `src/npc_engine/engines/llm_config_models.py`: `EngineModelParams`, `EnginePromptRef`, `EngineFallbackPolicy`, `EngineTimeoutsMs`, `EngineModelConfig` — all Pydantic v2, `frozen=True, extra="forbid", strict=True`
- New `src/npc_engine/engines/llm_config_loader.py`: `get_config(engine_name)` loads and validates per-engine YAML; `validate_all_engine_llm_configs(contracts)` called at startup to fail fast on missing/invalid configs
- New `src/npc_engine/engines/dialogue/llm_config.yaml`: mock backend defaults, per-engine timeouts, fallback tiers
- `engines/llm/factory.py`: added `create_llm_client_for_engine(engine_config, settings)` — for Ollama, uses `engine_config.llm.model` rather than `settings.OLLAMA_MODEL`
- `engines/dialogue/llm_client.py`: removed `MAX_TOKENS`/`DEFAULT_TEMPERATURE` module constants; `DialogueLLMClient.__init__` now requires `max_tokens` and `temperature` parameters
- `engines/dialogue/dialogue_handler.py`: added `engine_model_config: EngineModelConfig` to `__init__`; timeouts now sourced exclusively from per-engine config
- `config.py`: removed `DIALOGUE_FULL_TIMEOUT_SECONDS` and `DIALOGUE_GRAPH_ONLY_TIMEOUT_SECONDS`
- `api/dependency_singletons.py`: added `get_dialogue_engine_model_config()` singleton
- `api/dependencies.py` + `api/routes/dialogue_ws.py`: wired `engine_model_config` through dependency chain
- `main.py` lifespan: loads contracts → `validate_all_engine_llm_configs` → pre-warms dialogue config singleton
- New `tests/unit/test_engine_llm_config_loader.py`: 13 tests (happy path, all backends, missing file, missing field, unknown field, invalid backend, strict mode, I/O error, validate_all pass/fail/skip, uses_llm contract field)
- New `tests/integration/test_engine_llm_config_integration.py`: 3 tests (real config loads, independent max_tokens, independent timeouts)
- Updated `tests/unit/test_dialogue_handler_fallback_v14.py`, `test_llm_metrics_observability_v14.py`, `test_engine_contract_schema_checker_v14.py`
- Logged 3 deferred issues in `ISSUES.md` (001–003)

---

## Phase 0.3 — Route Audience Split + Hardening
**Status:** ✅ Complete
**Date completed:** 2026-05-05
**Tests:** run after this session to confirm green

### What was done
- Split routes into `/v1/` (game-engine public) and `/v1/admin/` (designer/tooling):
  - `/v1/batch/*` → `/v1/admin/batch/*`
  - `/v1/graph/admin/*` → `/v1/admin/graph/*`
  - `/v1/schema`, `/v1/schema/registry`, `/v1/protected` → `/v1/admin/schema`, etc.
  - `/v1/graph/*` (generic CRUD) stays at `/v1/graph/*` — game-engine facing
- `system.py` split into `router` (health) + `admin_router` (schema, protected)
- `graph_admin.py` prefix changed from `/graph/admin` to `/graph`
- `main.py` updated: new `admin_prefix`, admin routers mounted separately
- `auth/middleware_helpers._required_scope_for_path`: unified — all `/v1/admin/*` → `graph_admin`
- `utils/metrics.ROUTE_PREFIX_LABELS`: updated for new admin path prefixes
- Added `RateLimitMiddleware` (token bucket, per API key, 50 rps default, burst 100)
  - `src/npc_engine/api/rate_limit.py`
  - Middleware ordering: ApiKeyMiddleware (outer) → RateLimitMiddleware (inner)
  - `/health` always exempt; disabled with `RATE_LIMIT_ENABLED=false`
- Added `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_SECOND`, `RATE_LIMIT_BURST_SIZE` to `config.py`
- Updated 4 existing tests (`test_auth_permissions_v13`, `test_v1_route_versioning`, `test_system_registry_route`, `test_metrics_observability_v14`)
- New `tests/unit/test_rate_limit_middleware.py` (7 tests: bucket unit + middleware integration)
- `docker-compose.yml`: internal/public Docker networks with security posture comment
- `docs/API.md` created — public surface with curl examples
- `docs/ARCHITECTURE.md` updated — route audience split diagram + rate-limit section
- `project/DECISIONS.md` — two new entries (no gateway, route split)
- `e2e/scripts/gateway_smoke.py` — smoke test hitting new route layout
- `make smoke` target added
- `project/proposals/route_audience_improvements.md` — 6 improvements/flaws found

---

## Phase 0.2 — src/ Layout Move with pyproject.toml (was labeled 0.3)
**Status:** ✅ Complete  
**Date completed:** 2026-05-04  
**Tests:** 294 passed, 2 skipped, 0 failed (run from repo root via `pytest tests/`)

### What was done
- Created `pyproject.toml` at repo root with all deps, setuptools `src/` layout, and `[tool.pytest.ini_options]`
- Moved all source from `npc_engine/` → `src/npc_engine/` (editable install via `pip install -e .[dev]`)
- Rewrote ~174 files: all bare `from api.xxx import` → `from npc_engine.api.xxx import` (and all other sub-packages)
- Added `check_package_data_path()` validator + `@field_validator` for `LLM_FALLBACK_PATH` and `EVENT_POOL_PATH` in `config.py` to resolve package-relative data paths regardless of CWD
- Deleted old `npc_engine/` directory (source was copied to `src/`)
- Deleted `pytest.ini` (superseded by pyproject.toml `[tool.pytest.ini_options]`)
- Moved `.env`, `.env.example`, `mypy.ini`, `Dockerfile`, `docker-compose.yml` to repo root
- Updated Makefile: `pip install -e .[dev]`, `uvicorn npc_engine.main:app`, `python -m npc_engine.scripts.xxx`
- Updated CI: `pip install -e .[dev]` everywhere; removed lingering `cd npc_engine` step
- Updated 4 test path constants: `/ "npc_engine"` → `/ "src" / "npc_engine"` in conformance/provenance/fallback/metrics tests
- Fixed `from main import` and `import scripts.xxx` in 4 test files (not covered by batch rewrite)
- Fixed `CONTRACTS_DIR` in `tests/contract/contract_test_support.py`
- Fixed contract test imports: `tests.engine_contract_tests.xxx` → `tests.contract.xxx`

---

## Phase 0.2 — Repository Reorganization
**Status:** ✅ Complete  
**Date completed:** 2026-05-05  
**Tests:** 291 passed, 0 failed (run from repo root via `pytest tests/unit/`)

### What was done
- Created `tests/` at root (moved from `npc_engine/tests/`), `e2e/scenarios/`, `project/`, `docs/`, `project/proposals/`, `project/interfaces/`, `project/audit_reports/`
- Root `pytest.ini` added with `pythonpath = npc_engine` so tests run from root without CWD dependency
- Root `conftest.py` sets required env vars
- All working markdown consolidated to `project/`: CLAUDE.md, ISSUES.md, ROADMAP.md, DECISIONS.md, PATTERNS.md, STATUS.md, NEXT_SESSION.md, SKILLS_QUEUE.md, interfaces/, proposals/
- Reference docs moved to `docs/`: ARCHITECTURE.md, DATA_MODELS.md, BUSINESS_REQUIREMENTS.md, LLM_GENERATION_GUIDE.md, PROMPT_DESIGN.md, RELEVANCE_WEIGHTS.md
- `refactor/`, `proposals/`, `project_md_files/` deleted (emptied)
- Root `Makefile` is now canonical (merged npc_engine/Makefile in); all targets run from repo root
- CI updated: removed `working-directory: npc_engine`; all make targets work from root
- `.gitignore` updated with full standard set; `.vscode/settings.json` at root
- Cache directories deleted; `npc_engine/.gitignore` removed (merged to root)
- `npc_engine/pytest.ini` and `npc_engine/conftest.py` removed (superseded by root equivalents)
- `testing.docx` deleted (stale binary)
- **Deferred:** `src/` layout move; will use `pyproject.toml` when it happens (see DECISIONS.md)

### Three test files received path fixes (CWD-relative → `__file__`-relative)
- `tests/unit/test_architecture_conformance.py`: `PROJECT_ROOT = parents[2] / "npc_engine"`
- `tests/unit/test_quest_event_provenance_v14.py`: `game_schema.yaml` path anchored to `npc_engine/`
- `tests/unit/test_dialogue_handler_fallback_v14.py` and `test_llm_metrics_observability_v14.py`: fallback JSON and canned dir paths anchored to repo root

---

## Phase 0.1 — Stability Refactor

## Dependency Map

Each service bullet lists its direct project-module dependencies.

### Configuration & Infrastructure (Layer: config)
- **config** — no project deps

### Utilities (Layer: config)
- **utils.errors** — no project deps
- **utils.logging** — no project deps
- **utils.metrics** — no project deps
- **common.json_utils** — no project deps
- **common.yaml_utils** — no project deps

### Schema Loading (Layer: config)
- **schema.schema_models** — no project deps
- **schema.llm_config_models** — no project deps
- **schema.schema_loader** → common.yaml_utils, schema.schema_models, utils.errors
- **schema.llm_config_loader** → common.yaml_utils, schema.llm_config_models, utils.errors
- **schema.context_field_resolver** → schema.schema_models
- **schema.semantic_field_resolver** → schema.schema_models
- **schema.gossip_weight_resolver** → schema.schema_models
- **schema.enum_validator** → schema.schema_models
- **schema.model_factory** → schema.schema_models, type_registry.contracts

### Type Registry (Layer: config)
- **type_registry.contracts** — no project deps (pure dataclass)
- **type_registry.base_contract_models** — no project deps
- **type_registry.base_contract_loader** → type_registry.base_contract_models, common.yaml_utils
- **type_registry.extension_loader** → type_registry.contracts, common.yaml_utils
- **type_registry.merge_rules** → type_registry.contracts
- **type_registry.runtime_models** → type_registry.contracts, schema.schema_models
- **type_registry.validation** → type_registry.contracts, utils.errors
- **type_registry.serializer** → type_registry.contracts
- **type_registry.registry** → schema.schema_models, type_registry.{base_contract_loader, extension_loader, merge_rules, runtime_models, contracts}

### Mutation Tracking (Layer: services)
- **mutation.delta_log_manager** — no project deps
- **mutation.modifier_bounds_validator** → mutation.delta_log_manager, utils.errors

### World State (Layer: retrieval)
- **world.world_state** — no project deps
- **world.world_reader** → world.world_state
- **world.world_writer** → world.world_state

### Graph Database (Layer: graph)
- **graph.db** → config
- **graph.json_fields** — no project deps
- **graph.graph_reader** — no project deps (uses AsyncSession directly)
- **graph.delta_log_writer** → config, utils.logging
- **graph.relation_writer** → config, utils.logging
- **graph.character_writer** → config
- **graph.currency_writer** → config, utils.errors
- **graph.item_writer** → config, utils.errors
- **graph.event_writer** → config
- **graph.quest_writer** → config
- **graph.replay_helpers** → config
- **graph.graph_writer** → config, graph.{currency_writer, item_writer, relation_writer, delta_log_writer}, mutation.{delta_log_manager, modifier_bounds_validator}, engines.economy.{trading_engine, currency_verification_engine}, utils.{errors, metrics}
  ⚠️ LAYER VIOLATION: graph.graph_writer imports engines.economy — graph/ must not depend on engines/
- **graph.generic_graph_utils** → type_registry.contracts
- **graph.graph_edit_validator** → type_registry.{contracts, validation}
- **graph.generic_graph_service** → graph.generic_graph_utils, graph.graph_edit_validator, type_registry.{contracts, validation}, utils.errors
- **graph.graph_admin_service** → graph.{graph_reader, graph_writer, generic_graph_service}, type_registry.contracts
- **graph.reindex_job_service** → graph.db, utils.logging

### LLM Adapters (Layer: engines)
- **engines.llm.protocols** — no project deps
- **engines.llm.mock_adapter** → engines.llm.protocols
- **engines.llm.mistral_adapter** → engines.llm.protocols
- **engines.llm.llama_adapter** → engines.llm.protocols
- **engines.llm.ollama_adapter** → engines.llm.protocols
- **engines.llm.factory** → config, engines.llm.{protocols, mock_adapter, mistral_adapter, llama_adapter, ollama_adapter}

### Currency Engines (Layer: engines)
- **engines.currency** — namespace stub only; implementations are in graph/transfer_validators.py

### Emotion Engine (Layer: engines)
- **engines.emotion.emotion_state** — no project deps
- **engines.emotion.emotion_store** → engines.emotion.emotion_state
- **engines.emotion.emotion_updater** → engines.emotion.{emotion_state, emotion_store}

### Idempotency Engine (Layer: engines)
- **engines.idempotency.models** — no project deps
- **engines.idempotency.store_protocol** — no project deps
- **engines.idempotency.neo4j_store** → engines.idempotency.{models, store_protocol}
- **engines.idempotency.service** → config, engines.idempotency.{models, store_protocol, neo4j_store}, graph.db
- **engines.idempotency.cleanup_scheduler** → engines.idempotency.service, utils.logging

### Retrieval / RAG (Layer: retrieval)
- **retrieval.vector_store_protocol** — no project deps
- **retrieval.vector_store_factory** → config, retrieval.vector_store_protocol
- **retrieval.embedding_index** → retrieval.vector_store_protocol
- **retrieval.embedding_reconciler** → graph.reindex_job_service, retrieval.embedding_index, utils.logging
- **retrieval.context_utils** — no project deps (token counting, serialization helpers)
- **retrieval.context_merger** → retrieval.context_utils
- **retrieval.context_serializer** → retrieval.context_utils
- **retrieval.token_budget_enforcer** → config
- **retrieval.context_budget_enforcer** → retrieval.{context_utils, token_budget_enforcer}, utils.errors
- **retrieval.subgraph_retriever** → graph.graph_reader, type_registry.contracts, schema.{schema_models, llm_config_models}
- **retrieval.dialogue_context_cache** → config
- **retrieval.context_builder** → config, graph.graph_reader, world.world_reader, retrieval.{subgraph_retriever, context_merger, context_serializer, context_budget_enforcer, context_utils, dialogue_context_cache, vector_store_protocol}, engines.dialogue.context_relevance_engine, schema.llm_config_models, utils.metrics
  ⚠️ LAYER VIOLATION: retrieval.context_builder imports engines.dialogue.context_relevance_engine — retrieval/ must not depend on engines/

### Dialogue Engine (Layer: engines)
- **engines.dialogue.context_relevance_engine** → schema.llm_config_models
  ⚠️ MISPLACEMENT: Used by retrieval.context_builder but lives in engines.dialogue — should move to retrieval/
- **engines.dialogue.session_store** → config
- **engines.dialogue.response_parser** — no project deps
- **engines.dialogue.action_resolver** → api.schemas
  ⚠️ LAYER VIOLATION: engines.dialogue.action_resolver imports api.schemas — engines/ must not depend on api/
- **engines.dialogue.degradation** → config, engines.llm.protocols, utils.logging
- **engines.dialogue.prompt_builder** → schema.llm_config_models, type_registry.contracts
- **engines.dialogue.llm_client** → engines.llm.protocols, utils.logging
- **engines.dialogue.relation_mutator** → graph.graph_writer, api.schemas, utils.errors
  ⚠️ LAYER VIOLATION: engines.dialogue.relation_mutator imports api.schemas — engines/ must not depend on api/
- **engines.dialogue.dialogue_handler** → config, api.schemas, engines.dialogue.{action_resolver, degradation, llm_client, prompt_builder, relation_mutator, response_parser, session_store}, engines.emotion.emotion_updater, engines.llm.protocols, retrieval.context_builder, retrieval.dialogue_context_cache, schema.llm_config_models, utils.metrics
  ⚠️ LAYER VIOLATION: dialogue_handler imports api.schemas — engines/ must not depend on api/

### Gossip Engine (Layer: engines)
- **engines.gossip.gossip_distort** — no project deps (or minimal)
- **engines.gossip.pair_selector** → graph.graph_reader, type_registry.contracts
- **engines.gossip.knowledge_propagator** → graph.{graph_reader, relation_writer}, type_registry.contracts
- **engines.gossip.edge_updater** → graph.delta_log_writer, utils.logging
- **engines.gossip.gossip_handler** → config, engines.embedding_invalidation, engines.gossip.{pair_selector, knowledge_propagator, gossip_distort, edge_updater}, retrieval.embedding_index

### Event Engine (Layer: engines)
- **engines.events.event_pool** → common.json_utils
- **engines.events.location_scoper** → graph.graph_reader
- **engines.events.awareness_seeder** → graph.event_writer
- **engines.events.event_handler** → config, common.json_utils, engines.embedding_invalidation, engines.events.{awareness_seeder, event_pool, location_scoper}, graph.event_writer, retrieval.embedding_index, type_registry.contracts, world.world_state

### Quest Engine (Layer: engines)
- **engines.quest.models** — no project deps
- **engines.quest.quest_lifecycle_engine** → config, engines.quest.models, graph.{event_writer, graph_writer, quest_writer}, type_registry.contracts, utils.errors

### Embedding Invalidation (Layer: engines)
- **engines.embedding_invalidation** → retrieval.embedding_index, utils.logging

### Scheduler (Layer: engines)
- **scheduler.game_clock** — no project deps
- **scheduler.tick_lease** — no project deps (uses AsyncSession directly)
- **scheduler.tick_scheduler** → scheduler.{game_clock, tick_lease}, engines.gossip.gossip_handler, engines.events.event_handler

### Auth (Layer: api)
- **auth.api_key** → config
- **auth.permissions** — no project deps
- **auth.middleware** → config, auth.{api_key, permissions}, engines.idempotency.{models, service}, utils.{errors, logging, metrics}

### Cache (Layer: api)
- **cache.redis_runtime** → config

### API (Layer: api)
- **api.schemas** — no project deps (Pydantic DTOs)
- **api.pagination** — no project deps
- **api.action_helpers** → api.schemas
- **api.route_helpers** → api.schemas
- **api.graph_warning_helpers** → api.schemas, type_registry.contracts
- **api.dependencies** → config, all engines, all graph, all retrieval, all schema, cache, scheduler
- **api.routes.*** → api.{schemas, dependencies, helpers}

### Data (Layer: config)
- **data.seed** → graph.{db, character_writer, event_writer, relation_writer}, config

---

## Refactor Order

Deepest dependencies (no inbound) first. At equal depth, demo path preferred: dialogue > gossip > events > rest.

| # | Service | Layer | Status |
|---|---------|-------|--------|
| 1 | **utils** (errors, logging, metrics) | config | ✅ Done |
| 2 | **common** (json_utils, yaml_utils) | config | ✅ Done |
| 3 | **config** (Settings) | config | ✅ Done |
| 4 | **schema** (all schema loading + models + resolvers) | config | ✅ Done |
| 5 | **type_registry** (all registry files) | config | ✅ Done |
| 6 | **mutation** (delta_log_manager, modifier_bounds_validator) | services | ✅ Done |
| 7 | **world** (world_state, world_reader, world_writer) | retrieval | ✅ Done |
| 8 | **graph.db** (db, json_fields, replay_helpers) | graph | ✅ Done |
| 9 | **graph.readers** (graph_reader) | graph | ✅ Done |
| 10 | **graph.writers** (all *_writer, graph_writer) | graph | ✅ Done |
| 11 | **graph.admin** (generic_graph_utils, graph_edit_validator, generic_graph_service, graph_admin_service, reindex_job_service) | graph | ✅ Done |
| 12 | **engines.llm** (factory, protocols, all adapters) | engines | ✅ Done |
| 13 | **engines.economy** (currency_verification_engine, trading_engine) | engines | ✅ Done |
| 14 | **engines.emotion** (emotion_state, emotion_store, emotion_updater) | engines | ✅ Done |
| 15 | **engines.idempotency** (models, store_protocol, neo4j_store, service, cleanup_scheduler) | engines | ✅ Done |
| 16 | **retrieval.embedding** (vector_store_protocol, vector_store_factory, embedding_index, embedding_reconciler) | retrieval | ✅ Done |
| 17 | **retrieval.context** (context_utils, context_merger, context_serializer, token_budget_enforcer, context_budget_enforcer, subgraph_retriever, dialogue_context_cache, context_builder) | retrieval | ✅ Done |
| 18 | **engines.embedding_invalidation** | engines | ✅ Done |
| 19 | **engines.dialogue** (all dialogue sub-modules incl. context_relevance_engine relocation) | engines | ✅ Done |
| 20 | **engines.gossip** (gossip_handler + sub-modules) | engines | ✅ Done |
| 21 | **engines.events** (event_handler + sub-modules) | engines | ✅ Done |
| 22 | **engines.quest** (quest_lifecycle_engine, models) | engines | ✅ Done |
| 23 | **scheduler** (game_clock, tick_lease, tick_scheduler) | engines | ✅ Done |
| 24 | **auth** (api_key, middleware, permissions) | api | ✅ Done |
| 25 | **cache** (redis_runtime) | api | ✅ Done |
| 26 | **api** (schemas, dependencies, routes, helpers) | api | ✅ Done |
| 27 | **data** (seed.py) | config | ✅ Done |

---

## Baseline Test State

**Run date:** 2026-04-30
**Command:** `pytest --tb=no -q`
**Results:**
- Total: 214 collected
- Passed: 207
- Failed: 5
- Skipped: 2

**Failing tests:**
1. `tests/unit/test_architecture_conformance.py::test_all_python_files_have_module_docstring_contract` — conformance check; will pass as refactor adds docstrings
2. `tests/unit/test_generic_graph_service.py::test_upsert_edge_enforces_endpoint_match_before_merge` — graph service logic bug
3. `tests/unit/test_generic_graph_service.py::test_upsert_edge_raises_when_nodes_missing` — graph service logic bug
4. `tests/unit/test_generic_graph_service.py::test_upsert_node_serializes_dict_fields_for_storage` — graph service logic bug
5. `tests/unit/test_type_registry_validator.py::test_validate_node_payload_accepts_list_dict_base_shapes` — type registry validation bug

**Note:** Tests cannot be run with a live Neo4j instance in CI; integration tests will require a test DB fixture.

---

## Layer Violations Detected (session 1)

These are structural violations of the layer model that must be resolved during the refactor of the relevant service.

| # | Violation | File | Must fix in |
|---|-----------|------|-------------|
| V1 | `graph.graph_writer` imports `engines.economy.*` — graph/ must not depend on engines/ | graph/graph_writer.py | ✅ Fixed (Service #10): moved builders to graph/transfer_validators.py; engines/economy/ files become thin re-exports |
| V2 | `retrieval.context_builder` imports `engines.dialogue.context_relevance_engine` — retrieval/ must not depend on engines/ | retrieval/context_builder.py | Service #17 (retrieval.context) |
| V3 | `engines.dialogue.context_relevance_engine` lives in engines/dialogue/ but is consumed by retrieval — should relocate to retrieval/ | engines/dialogue/context_relevance_engine.py | Service #17 (retrieval.context) |
| V4 | `engines.dialogue.action_resolver` imports `api.schemas` — engines/ must not depend on api/ | engines/dialogue/action_resolver.py | Service #19 (engines.dialogue) |
| V5 | `engines.dialogue.relation_mutator` imports `api.schemas` — engines/ must not depend on api/ | engines/dialogue/relation_mutator.py | Service #19 (engines.dialogue) |
| V6 | `engines.dialogue.dialogue_handler` imports `api.schemas` — engines/ must not depend on api/ | engines/dialogue/dialogue_handler.py | Service #19 (engines.dialogue) |

---

## Surprises

- **No `services/` layer exists.** The layer model in the refactor prompt specifies a `services/` layer between engines and retrieval, but the codebase has no such directory. The `mutation/` directory partially fills this role. This will need a DECISIONS.md entry when we first hit a service that belongs there.
- **No ARCHITECTURE.md, DATA_MODELS.md, or BUSINESS_REQUIREMENTS.md at repo root.** These docs were referenced but do not exist. The README.md is the primary documentation.
- **Multiple pre-existing test failures (5).** Three failures are in `generic_graph_service` tests — this service has known bugs that were not fixed before the refactor started. One is a type_registry validator bug.
- **`graph.graph_writer` is the most entangled file.** It reaches up into `engines.economy` and sideways into `mutation`, `graph.{currency,item,relation,delta_log}_writer`. This is the most complex file in the graph layer and the primary source of V1.
- **`engines.embedding_invalidation` lives in `engines/` root**, not in a sub-package. It is a single-file utility, not a full engine. Probably belongs in `retrieval/`.

---

---

## Service #1 — utils

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 18 (13 errors, 7 logging) / integration: 0 / property: 0
**Files:** utils/errors.py, utils/logging.py, utils/metrics.py

**What was fixed:**
- `ItemTransferValidationError`, `QuestTransitionError`, `QuestProvenanceError` made `frozen=True` (STRUCT-06 violation)
- `StructuredNPCSystemError.__str__` docstring added (DOC-02)
- `MetricsRegistry.__init__` — added `-> None`, docstring, and `_lock: Lock` type annotation (TYPE-01, DOC-02)
- `_serialize_key` docstring added (DOC-02)
- Comment block in errors.py documents future migration of misplaced exceptions

---

## Service #2 — common

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 5 (yaml_utils) + 5 pre-existing (json_utils) / integration: 0 / property: 0
**Files:** common/json_utils.py, common/yaml_utils.py

**What was fixed:**
- All public functions in json_utils.py given full DOC-02 docstrings (Args, Returns sections)
- `load_yaml_mapping` in yaml_utils.py given full DOC-02 docstring (Args, Returns, Raises sections)
- 5 new unit tests added in tests/unit/test_common_yaml_utils.py (no tests existed before)

---

## Service #4 — schema

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 32 new (6 schema_loader additions, 12 llm_config, 14 schema_resolvers) / integration: 0 / property: 0
**Files:** schema/llm_config_models.py, schema/schema_loader.py, schema/llm_config_loader.py, schema/context_field_resolver.py, schema/semantic_field_resolver.py, schema/gossip_weight_resolver.py, schema/enum_validator.py, schema/model_factory.py

**What was fixed:**
- All 8 public functions/methods across the schema layer received full DOC-02 docstrings (Args, Returns, Raises)
- schema_models.py had no public functions — models use frozen=True and default_factory throughout — no changes needed
- 3 new error-case tests added to test_schema_loader.py (SchemaValidationError for list root, wrong version, invalid field type)
- New test_llm_config.py — 12 tests covering RelevanceWeights validator, TierBudgetTokens constraints, LLMConfig extra-field rejection, and load_llm_config happy/error paths
- New test_schema_resolvers.py — 14 tests covering all 3 resolvers, enum_validator, and model_factory (including range constraint enforcement and naming convention)

---

## Service #3 — config

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 30 new (config_validators) / integration: 0 / property: 0
**Files:** config.py, config_validators.py (new)

**What was fixed:**
- Validator logic extracted to `config_validators.py` (STRUCT-01: file was borderline; adding full DOC-02 docstrings would have exceeded 200 non-blank lines)
- All 11 validator functions in `config_validators.py` have full DOC-02 docstrings (Args, Returns, Raises)
- `config.py` classmethods are now thin one-liner delegates (~130 non-blank lines, well under 200)
- `get_settings` received a `Returns:` section (DOC-02)
- `_PROJECT_ROOT` extracted as a module-level constant (avoids repeated `Path(__file__).resolve().parent` in two validators)
- 30 new unit tests cover all validation paths including happy-path and all error cases

---

## Service #5 — type_registry

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 0 new (pre-existing suite covers all paths); 1 bug fixed
**Files:** contracts.py, base_contract_models.py, base_contract_loader.py, extension_loader.py, merge_rules.py, merge_field_builders.py (new), runtime_models.py, validation.py, field_validators.py (new), serializer.py, registry.py, __init__.py

**What was fixed:**
- `test_validate_node_payload_accepts_list_dict_base_shapes` bug fixed: test payload was missing `last_updated_at` and `last_graph_updated_at`, both required in world_state YAML contract
- `merge_rules.py` split into `merge_rules.py` (orchestration) + `merge_field_builders.py` (primitive builders and enforcement helpers) — STRUCT-01 violation resolved (271 → ~130 + ~130 lines)
- `validation.py` split into `validation.py` (payload orchestration) + `field_validators.py` (per-field type/range/byte validators) — STRUCT-01 violation resolved (294 → ~160 + ~120 lines)
- `merge_registry` received full DOC-02 docstring (Args, Returns, Raises)
- `build_runtime_models`, `serialize_registry_snapshot`, `build_type_registry` received full DOC-02 docstrings (Args, Returns, Raises)
- `type_registry/__init__.py` module docstring brought into conformance (added Does NOT: and Dependencies injected: lines)
- Architecture conformance test now passes (was pre-existing failure)

**Test delta:** 5 failures → 3 failures (fixed type_registry_validator bug + fixed architecture conformance)

---

## Service #6 — mutation

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 0 new (no unit tests existed; contract verified by graph integration tests)
**Files:** mutation/__init__.py, mutation/delta_log_manager.py, mutation/modifier_bounds_validator.py

**What was fixed:**
- `RelationDeltaExceededError` migrated from `modifier_bounds_validator.py` to `utils/errors.py` (P1 deferred task completed); import updated in `modifier_bounds_validator.py`
- Comment in `utils/errors.py` updated to reflect completed migration (only TokenBudgetExceededError and ContextBudgetError remain deferred)
- Full DOC-02 docstrings (Args, Returns, Raises) added to `append_delta`, `compute_window_sum`, `validate_deltas`, `clamp_relation_values`

---

## Service #7 — world

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 0 new (existing world_reader tests cover happy/edge paths)
**Files:** world/__init__.py, world/world_state.py, world/world_reader.py, world/world_writer.py

**What was fixed:**
- Full DOC-02 docstrings (Args, Returns) added to `get_world_state` and `upsert_world_state`
- Missing blank line before `async def get_world_state` in world_reader.py corrected

---

## Service #8 — graph.db

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 0 new (infrastructure only; covered by integration suite)
**Files:** graph/__init__.py, graph/db.py, graph/json_fields.py, graph/replay_helpers.py

**What was fixed:**
- `GraphDB.__init__` annotated with `-> None` (TYPE-01)
- `GraphDB.connect` and `GraphDB.close` expanded to full DOC-02 (prior one-liners)
- `GraphDB.get_session` given Returns and Raises sections (DOC-02)
- `serialize_provenance_field` given full Args/Returns DOC-02
- `load_idempotent_replay_record` given full Args/Returns DOC-02

---

## Service #9 — graph.readers

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** unit: 0 new (read paths covered by existing context/retrieval tests)
**Files:** graph/graph_reader.py

**What was fixed:**
- Duplicate `from typing import` lines merged into one (`Any, cast`)
- Return annotations tightened: `dict` → `dict[str, Any]`, `list[dict]` → `list[dict[str, Any]]`, `dict | None` → `dict[str, Any] | None` (TYPE-01)
- Full DOC-02 docstrings (Args, Returns) added to all 5 public async functions

---

## Service #10 — graph.writers

**Status:** ✅ Done
**Date completed:** 2026-05-01
**Tests:** 288 passed, 3 failed (same pre-existing service #11 bugs; 0 new regressions)
**Files created:** graph/transfer_validators.py, graph/currency_queries.py, graph/item_queries.py, graph/write_metrics.py, graph/relation_delta_writer.py
**Files modified:** graph/graph_writer.py, graph/currency_writer.py, graph/item_writer.py, graph/delta_log_writer.py, graph/relation_writer.py, graph/character_writer.py, graph/event_writer.py, graph/quest_writer.py, engines/economy/trading_engine.py, engines/economy/currency_verification_engine.py

**What was fixed:**
- **V1 layer violation resolved**: `CurrencyTransferCommand`, `ItemTransferCommand`, `build_currency_transfer_command`, `build_item_transfer_command` moved down from `engines/economy/` into `graph/transfer_validators.py`. Both engine files now re-export from there for backward compat.
- **graph_writer.py STRUCT-01** (243 lines): split into `graph_writer.py` (transfer coordinator, ~170 lines) + `relation_delta_writer.py` (relation delta logic) + `write_metrics.py` (metric helpers). `graph_writer.py` re-exports `apply_relation_delta` for backward compat.
- **currency_writer.py STRUCT-01** (260 lines): Cypher strings extracted to `currency_queries.py`. Writer now ~183 lines.
- **item_writer.py STRUCT-01** (201 lines): Cypher strings extracted to `item_queries.py`. Writer now ~113 lines.
- **DOC-02 pass** on all writer files: `delta_log_writer`, `relation_writer`, `character_writer`, `event_writer`, `quest_writer`, `currency_writer`, `item_writer`, `graph_writer`, `relation_delta_writer`, `write_metrics`, `transfer_validators`
- **TYPE-01**: `_record_to_state_payload` and `_deep_copy_json` in quest_writer.py now have annotated signatures

---

## Service #11 — graph.admin

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (first fully-green run of the refactor)
**Files created:** graph/generic_graph_base.py, graph/generic_node_service.py, graph/generic_edge_service.py
**Files modified:** graph/generic_graph_service.py, graph/generic_graph_utils.py, graph/graph_edit_validator.py, graph/graph_admin_service.py, graph/reindex_job_service.py, utils/errors.py, tests/unit/test_generic_graph_service.py

**What was fixed:**
- **3 pre-existing test failures resolved** (service #11 target):
  - Root cause A: Frozen dataclass exceptions blocked pytest-asyncio's `__traceback__` assignment. Fixed by adding `__init_subclass__` hook to `StructuredNPCSystemError` that patches each frozen subclass's `__setattr__` to allow `__traceback__`, `__cause__`, `__context__` through while blocking all other field mutations.
  - Root cause B: Test payloads missing required fields (`interaction_count`, `last_updated_at`, `relevance_score` for RELATES_TO; `last_updated_at`, `last_graph_updated_at` for world_state). Test payloads updated.
- **generic_graph_service.py STRUCT-01** (251L → ~20L): split into `generic_graph_base.py` (shared `__init__` + `_run`), `generic_node_service.py` (node CRUD), `generic_edge_service.py` (edge CRUD); `generic_graph_service.py` becomes `GenericGraphService(GenericNodeService, GenericEdgeService)` shim — fully backward compatible
- **DOC-02 pass** on all 5 admin service files + `generic_graph_utils.py` + `graph_edit_validator.py`

---

## Service #12 — engines.llm

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change from baseline)
**Files modified:** engines/llm/protocols.py, engines/llm/mock_adapter.py, engines/llm/llama_adapter.py, engines/llm/mistral_adapter.py, engines/llm/ollama_adapter.py, engines/llm/factory.py

**What was fixed:**
- All 4 protocol methods in `protocols.py` given full DOC-02 docstrings (Args, Returns, Raises)
- `MockLLMAdapter.__init__` annotated `-> None` and given docstring (TYPE-01, DOC-02)
- All 4 public methods on `MockLLMAdapter` given full DOC-02 docstrings
- `LlamaAdapter.model_name` given DOC-02 docstring
- `MistralAdapter.__init__` annotated `-> None` and given docstring (TYPE-01, DOC-02)
- All 4 public methods on `MistralAdapter` given full DOC-02 docstrings (Args, Returns, Raises)
- `OllamaAdapter.__init__` annotated `-> None` and given docstring (TYPE-01, DOC-02)
- All 4 public methods on `OllamaAdapter` given full DOC-02 docstrings (Args, Returns, Raises)
- `create_llm_client` in `factory.py` expanded to full DOC-02 (Args, Returns, Raises)
- No STRUCT-01 violations — all files remained well under 200 lines after additions
- No STRUCT-06 violations found — no in-place mutation present

---

## Service #13 — engines.economy

**Status:** ✅ Done (no-op)
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files:** engines/economy/__init__.py, engines/economy/currency_verification_engine.py, engines/economy/trading_engine.py

**What was fixed:**
- Nothing. All three files are pure re-export stubs created in Service #10 (V1 fix).
  STRUCT-03, DOC-02, TYPE-01, and STRUCT-06 all already compliant — no public functions or
  methods are defined; all symbols are imported and re-exported via `__all__`.

---

## Service #14 — engines.emotion

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** engines/emotion/emotion_state.py, engines/emotion/emotion_store.py, engines/emotion/emotion_updater.py

**What was fixed:**
- `derive_label` given full DOC-02 docstring (Args, Returns)
- `EmotionStore.get` and `EmotionStore.set` given full DOC-02 docstrings (Args, Returns)
- `EmotionUpdater.__init__` annotated `-> None` and given docstring (TYPE-01, DOC-02)
- `EmotionUpdater.apply_dialogue_mood` and `get_state` given full DOC-02 docstrings

---

## Service #15 — engines.idempotency

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files created:** engines/idempotency/neo4j_queries.py, engines/idempotency/service_helpers.py
**Files modified:** engines/idempotency/neo4j_store.py, engines/idempotency/service.py, engines/idempotency/store_protocol.py, engines/idempotency/cleanup_scheduler.py

**What was fixed:**
- **neo4j_store.py STRUCT-01** (248L): Cypher constants extracted to `neo4j_queries.py`. Store now ~220 lines.
- **service.py STRUCT-01** (282L): Private helper functions extracted to `service_helpers.py`. service.py now ~175 lines.
- **DOC-02 pass** on all 6 public methods of `Neo4jIdempotencyStore`
- **DOC-02 pass** on all 6 protocol stubs in `IdempotencyStoreProtocol`
- **DOC-02 pass** on `GraphSessionProvider.get_session` protocol stub
- **DOC-02 pass** on `IdempotencyService.__init__`, `ensure_constraints`, `preflight`, `finalize`, `cleanup_expired`
- **TYPE-01**: `IdempotencyService.__init__` and `IdempotencyCleanupScheduler.__init__` annotated `-> None`
- **DOC-02** on `IdempotencyCleanupScheduler.__init__` and expanded `run_forever` docstring

---

## Service #18 — engines.embedding_invalidation

**Status:** ✅ Done (no-op with DOC-02)
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** engines/embedding_invalidation.py

**What was fixed:**
- `EmbeddingInvalidationTarget.invalidate` stub expanded to full docstring with `-> None` return annotation and Args section
- `invalidate_embedding_safely` one-liner expanded to full Args docstring

---

## Service #19 — engines.dialogue

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files created:** engines/dialogue/dialogue_models.py
**Files modified:** engines/dialogue/action_resolver.py, engines/dialogue/response_parser.py, engines/dialogue/degradation.py, engines/dialogue/prompt_builder.py, engines/dialogue/llm_client.py, engines/dialogue/relation_mutator.py, engines/dialogue/dialogue_handler.py, engines/dialogue/session_store.py, api/schemas.py

**What was fixed:**
- **V4/V5/V6 layer violations resolved**: `DialogueRequest`, `DialogueResponse`, `RelationDeltas`, `ActionModel`, `FacialExpressionModel`, `ActionType`, `ExpressionType` extracted from `api/schemas.py` into new `engines/dialogue/dialogue_models.py`; all dialogue engine files updated to import from `dialogue_models`; `api/schemas.py` re-exports all moved types via `__all__` using `FrozenApiModel = FrozenDialogueModel` alias — backward compat fully preserved
- **DOC-02 + TYPE-01** on `session_store.py`: `__init__ -> None`, full docstrings on `key`, `get_turns`, `append_turns`
- **DOC-02** on `action_resolver.py`: `resolve_action` expanded to full Args/Returns
- **DOC-02** on `response_parser.py`: `parse_dialogue_response` expanded to full Args/Returns/Raises
- **DOC-02** on `prompt_builder.py`: `build_dialogue_prompt` expanded to full Args/Returns
- **DOC-02** on `degradation.py`: `execute_with_degradation` expanded to full Args/Returns
- **DOC-02 + TYPE-01** on `llm_client.py`: `__init__ -> None` and docstring; `generate_response`, `fallback_response_payload`, `stream_text` all expanded to full Args/Returns
- **DOC-02** on `relation_mutator.py`: `apply_dialogue_relation_deltas` expanded to full Args
- **DOC-02 + TYPE-01** on `dialogue_handler.py`: `__init__ -> None` + full docstring; `embedding_index` parameter typed as `object`; `handle` and `stream` expanded to full Args/Returns

---

## Service #17 — retrieval.context

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files created:** retrieval/context_relevance_engine.py, retrieval/context_compression.py, retrieval/context_metrics.py, retrieval/context_scoring.py
**Files modified:** utils/errors.py, retrieval/token_budget_enforcer.py, retrieval/context_budget_enforcer.py, retrieval/context_builder.py, retrieval/context_utils.py, retrieval/context_merger.py, retrieval/context_serializer.py, retrieval/subgraph_retriever.py, retrieval/dialogue_context_cache.py, engines/dialogue/context_relevance_engine.py

**What was fixed:**
- **P1 — TokenBudgetExceededError migrated** from `retrieval/token_budget_enforcer.py` to `utils/errors.py`; re-exported via `__all__` in token_budget_enforcer for backward compat
- **P1 — ContextBudgetError migrated** from `retrieval/context_budget_enforcer.py` to `utils/errors.py`; re-exported via `__all__` in context_budget_enforcer for backward compat
- **V2/V3 layer violation resolved**: `context_relevance_engine.py` moved to `retrieval/context_relevance_engine.py`; `engines/dialogue/context_relevance_engine.py` replaced with re-export stub; `context_builder.py` updated to import from `retrieval`
- **context_budget_enforcer.py STRUCT-01** (223L → ~130L): compression primitives extracted to `context_compression.py` (`CompressionCacheEntry`, `ContextCompressionCache`, `build_compression_cache_key`, `_compress_text`, `_extract_graph_timestamp`); enforcer imports from compression module
- **context_builder.py STRUCT-01** (359L → ~185L): scoring helpers extracted to `context_scoring.py` (`rank_tier_items`, `_build_candidate`, `_extract_recency_score`, `_extract_severity_score`, `_extract_relation_score`, `_quest_score`, `_infer_proximity_hops`, `_normalize_ratio`); metric emission extracted to `context_metrics.py` (`record_context_metrics`, `record_compression_metrics` + metric name constants)
- **DOC-02 pass** on context_utils, context_merger, context_serializer, token_budget_enforcer, context_budget_enforcer, subgraph_retriever, dialogue_context_cache, context_builder, context_relevance_engine, context_compression, context_metrics, context_scoring
- **backward-compat shims** `_enforce_final_serialized_budget` and `_estimate_tokens` retained in context_builder for test imports

---

## Service #16 — retrieval.embedding

**Status:** ✅ Done
**Date completed:** 2026-05-02
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** retrieval/vector_store_protocol.py, retrieval/vector_store_factory.py, retrieval/embedding_index.py, retrieval/embedding_reconciler.py

**What was fixed:**
- **DOC-02 pass** on all 3 protocol method stubs in `VectorStoreProtocol`: full Args, Returns, Raises sections added
- **DOC-02 + TYPE-01** on `InMemoryVectorStore.__init__`: annotated `-> None` and added docstring
- **DOC-02 pass** on all 3 public methods of `InMemoryVectorStore`: full Args, Returns, Raises sections
- **DOC-02 pass** on `create_vector_store`: full Args, Returns, Raises sections
- **DOC-02 + TYPE-01** on `EmbeddingIndex.__init__`: annotated `-> None` and added docstring
- **DOC-02 pass** on all 3 public methods of `EmbeddingIndex`: full Args, Returns, Raises sections
- **TYPE-01** on `EmbeddingReconciler.__init__`: annotated `-> None`
- **DOC-02 pass** on `EmbeddingReconciler.__init__`: full Args, Returns, Raises sections
- **DOC-02 pass** on `EmbeddingReconciler.reconcile_once`: Returns section added
- **DOC-02 pass** on `EmbeddingReconciler.run_forever`: expanded to describe loop semantics, cancellation, error swallowing
- **TYPE-01 + DOC-02** on private protocol stubs (`_SessionProtocol.run`, `_GraphDbProtocol.get_session`, `_EmbeddingIndexProtocol.upsert`): return type annotations and expanded docstrings

---

## Service #24 — auth

**Status:** ✅ Done
**Date completed:** 2026-05-04
**Tests:** 291 passed, 0 failed (no change)
**Files created:** auth/middleware_helpers.py
**Files modified:** auth/api_key.py, auth/permissions.py, auth/middleware.py

**What was fixed:**
- **middleware.py STRUCT-01** (441L → ~230L): all 9 standalone private functions + all constants + LOGGER extracted to `middleware_helpers.py`; `middleware.py` now imports them explicitly and contains only `ApiKeyMiddleware` with `__init__` and `dispatch`
- **TYPE-01**: `ApiKeyMiddleware.__init__ -> None`; `dispatch` call_next annotated as `Callable[[Request], Awaitable[Response]]`
- **DOC-02 + TYPE-01** on `__init__` and `dispatch`: full Args/Returns sections
- **DOC-02** on `api_key.py`: `_extract_bearer_token`, `validate_bearer_token`, `resolve_scope_from_authorization` expanded to full Args/Returns/Raises
- **DOC-02** on `permissions.py`: `has_scope` expanded to full Args/Returns
- **DOC-02** on all 9 helpers in `middleware_helpers.py`: full Args/Returns/Raises sections

---

## Service #25 — cache

**Status:** ✅ Done (no-op with TYPE-01 + DOC-02)
**Date completed:** 2026-05-04
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** cache/redis_runtime.py

**What was fixed:**
- **TYPE-01**: `RedisRuntime.__init__ -> None`
- **DOC-02**: `RedisRuntime.__init__` given full Args docstring

---

## Service #26 — api

**Status:** ✅ Done
**Date completed:** 2026-05-04
**Tests:** 291 passed, 0 failed (no change)
**Files created:** api/dependency_singletons.py
**Files modified:** api/dependencies.py, api/action_helpers.py, api/route_helpers.py, api/graph_warning_helpers.py, api/routes/graph.py, api/routes/graph_admin.py, api/routes/quest.py

**What was fixed:**
- **dependencies.py STRUCT-01** (260L → ~120L): all 18 `@lru_cache` singleton factories extracted to `dependency_singletons.py` with full DOC-02; `dependencies.py` re-exports all singletons + contains only session-scoped and composed handlers (get_db_session, get_llm_client, build_dialogue_handler, get_dialogue_handler, get_generic_graph_service, get_graph_admin_service) — backward compat fully preserved for all route imports
- **DOC-02** on `action_helpers.py`: all 6 public functions expanded to full Args/Returns
- **DOC-02** on `route_helpers.py`: all 4 public functions expanded to full Args/Returns/Raises
- **DOC-02** on `graph_warning_helpers.py`: `emit_graph_warnings` and `attach_warnings_meta` expanded to full Args/Returns
- **DOC-02** on `routes/graph.py`: all 8 route handlers given one-liner docstrings
- **DOC-02** on `routes/graph_admin.py`: all 7 route handlers given one-liner docstrings
- **DOC-02** on `routes/quest.py`: `_quest_error_status`, `_quest_error_to_http`, `_build_transition_meta`, `_to_objective_inputs` given full Args/Returns/Raises

---

## Service #27 — data

**Status:** ✅ Done
**Date completed:** 2026-05-04
**Tests:** 291 passed, 0 failed (no change)
**Files created:** data/seed_queries.py
**Files modified:** data/seed.py

**What was fixed:**
- **seed.py STRUCT-01** (214L → ~130L): all 8 Cypher query string constants extracted to `data/seed_queries.py`; `seed.py` imports them and is now ~130 lines
- **DOC-02** on `_locations`, `_characters`, `_events`, `_event_knowledge`, `seed`: full Args/Returns sections added

---

## Deferred

### P1 — Migrate misplaced domain exceptions to errors.py
- `RelationDeltaExceededError` is defined in `mutation/modifier_bounds_validator.py` — migrate in service #6 (mutation)
- `TokenBudgetExceededError` is defined in `retrieval/token_budget_enforcer.py` — migrate in service #17 (retrieval.context)
- `ContextBudgetError` is defined in `retrieval/context_budget_enforcer.py` — migrate in service #17 (retrieval.context)

### P2 — Architecture conformance test still failing
- `test_all_python_files_have_module_docstring_contract` — will pass incrementally as each service adds module docstrings. Not yet a blocker.

---

## Service #20 — engines.gossip

**Status:** ✅ Done
**Date completed:** 2026-05-03
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** engines/gossip/gossip_distort.py, engines/gossip/pair_selector.py, engines/gossip/knowledge_propagator.py, engines/gossip/edge_updater.py, engines/gossip/gossip_handler.py

**What was fixed:**
- **DOC-02** on `gossip_distort`: `gossip_distort` full Args/Returns
- **DOC-02** on `pair_selector`: `select_pairs` full Args/Returns
- **DOC-02** on `knowledge_propagator`: `propagate` full Args
- **DOC-02** on `edge_updater`: `log_gossip` full Args describing optimistic-concurrency pattern
- **TYPE-01 + DOC-02** on `gossip_handler`: `GossipHandler.__init__ -> None` + docstring; `run_tick` full Args/Returns

---

## Service #21 — engines.events

**Status:** ✅ Done
**Date completed:** 2026-05-03
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** engines/events/event_pool.py, engines/events/location_scoper.py, engines/events/awareness_seeder.py, engines/events/event_handler.py

**What was fixed:**
- **DOC-02** on `event_pool`: `load_event_pool` full Args/Returns/Raises
- **DOC-02** on `location_scoper`: `resolve_locations` full Args/Returns
- **DOC-02** on `awareness_seeder`: `seed_awareness_tx` full Args; blank line before `async def` corrected
- **TYPE-01 + DOC-02** on `event_handler`: `EventHandler.__init__ -> None` + docstring; `run_tick` full Args/Returns

---

## Service #22 — engines.quest

**Status:** ✅ Done
**Date completed:** 2026-05-03
**Tests:** 291 passed, 0 failed (no change)
**Files created:** engines/quest/quest_engine_helpers.py
**Files modified:** engines/quest/quest_lifecycle_engine.py

**What was fixed:**
- **quest_lifecycle_engine.py STRUCT-01** (430L): pure helpers extracted to `quest_engine_helpers.py` (`is_trusted_reward_source`, `normalize_item_rewards`, `ensure_transaction_session`, `build_lifecycle_event`); engine now ~280L
- **TYPE-01**: `QuestLifecycleEngine.__init__ -> None`
- **DOC-02** on `QuestLifecycleEngine.__init__` and all 5 public methods (`offer_quest`, `accept_quest`, `update_objective`, `evaluate_completion`, `apply_rewards`)
- **DOC-02** on all 7 functions in `quest_engine_helpers.py`
- Private async methods `_require_state`, `_emit_lifecycle_event`, `_persist_state_and_event` kept as class methods (not extracted) to preserve monkeypatch targets in tests

---

## Service #23 — scheduler

**Status:** ✅ Done
**Date completed:** 2026-05-03
**Tests:** 291 passed, 0 failed (no change)
**Files modified:** scheduler/game_clock.py, scheduler/tick_lease.py, scheduler/tick_scheduler.py

**What was fixed:**
- **TYPE-01 + DOC-02** on `GameClock.__init__ -> None` + docstring; `advance` full Args/Returns; `state` property Returns section
- **TYPE-01 + DOC-02** on `TickLeaseRepository.__init__ -> None` + docstring; `ensure_constraints`, `try_claim`, `mark_done`, `is_done`, `mark_failed` all given full Args/Returns docstrings
- **TYPE-01 + DOC-02** on `TickScheduler.__init__ -> None` + docstring; `gossip_handler` and `event_handler` typed as `object`; `advance` expanded to full Args/Returns; `state`, `next_gossip_tick`, `next_event_tick` properties given Returns sections
- `ClockState` imported in `tick_scheduler.py` for the `state` property return annotation
