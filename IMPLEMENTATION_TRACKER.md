# NPC Engine v1.0 Implementation Tracker

This file tracks staged implementation and allows interruption/resume.

## How to Resume
1. Open this file and find the first stage marked IN_PROGRESS or TODO.
2. Continue from the first unchecked item in that stage.
3. Run the stage smoke commands listed in the stage section.
4. Update status, date, and notes.

## Status Legend
- TODO: not started
- IN_PROGRESS: partially complete
- DONE: complete and smoke-verified
- BLOCKED: needs decision

## Stages

### M0 - Auth and Infra Skeleton
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP0_BOOTSTRAP

Tasks:
- [x] Create base project structure
- [x] Add config and shared utilities
- [x] Add auth middleware and API key validation
- [x] Add FastAPI app skeleton with health endpoint
- [x] Add environment template, dependencies, and Make targets
- [x] Run startup smoke test

Smoke commands:
```bash
cd npc_engine
pip install -r requirements.txt
uvicorn main:app --reload
```

Expected checks:
- GET /health returns status payload
- Non-health routes require Bearer token

Notes:
- Smoke verified with FastAPI TestClient:
	- GET /health -> 200
	- GET /protected without token -> 401
	- GET /protected with valid bearer token -> 200

### M1 - Graph Layer and World State
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP1_GRAPH

Tasks:
- [x] Implement graph schemas, readers, writers, and transactions
- [x] Implement mutation validator and delta log manager
- [x] Implement world state models and read/write layer
- [x] Implement idempotent seed logic

Notes:
- Added development commands in Makefile: lint, type, test, test-cov, check, seed.
- Added docker-compose + Dockerfile for app/Neo4j local stack.
- Added architecture conformance tests under tests/unit.
- Added strict local .env with valid development API_KEY_SECRET.
- Validation: ruff check ., mypy ., pytest -q all pass.

### M2 - LLM Adapters and Retrieval
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP2_RETRIEVAL

Tasks:
- [x] Implement LLM protocol/adapters/factory
- [x] Implement retrieval layers and context pipeline
- [x] Add token budget enforcement and serialization

Notes:
- M2 baseline found in workspace was reviewed and retained.
- Added Tier-A context enrichment: player relation, nearby NPCs, location context.
- Removed silent stream fallback in HTTP adapters; now raises typed stream errors.
- Added top_k validation in vector store/index and corresponding tests.
- Validation: focused M2 tests (19 passed), ruff scope checks passed, mypy on M2 packages passed.

### M3 - Dialogue Engine and API Routes
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP3_DIALOGUE

Tasks:
- [x] Implement emotion and dialogue submodules
- [x] Implement dependency composition root
- [x] Implement REST and WebSocket dialogue routes

Notes:
- Added emotion and dialogue engine modules including session store, parser, mutator, prompt builder, and handler orchestration.
- Added API schemas, dependency composition root, and routes for dialogue, websocket dialogue, npc state/emotion, and player action report.
- Added fallback response data file used by dialogue LLM wrapper.
- M3 hardening pass completed: WebSocket auth enforced, single-pass WS execution, error event emission, action enum alignment, and include_relations/include_events support.
- Validation: ruff check ., mypy ., pytest -q all pass.

### M4 - Gossip, Events, Scheduler
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP4_SIMULATION

Tasks:
- [x] Implement gossip engine modules
- [x] Implement event engine modules
- [x] Implement scheduler and clock/batch routes

Notes:
- Added M4 gossip/event/scheduler modules and API routes for clock and batch simulation.
- Hardening applied: scheduler runs handlers before clock advancement, severe-event world updates in event transaction, CAS retries for gossip delta-log writes, and non-fatal embedding index invalidation warnings.
- Added Neo4j-based distributed tick lease/claim mechanism with scheduler owner+TTL controls.
- Added scheduler regression coverage for partial-failure retry behavior.
- Validation: ruff check ., mypy ., pytest -q passed.

### M5 - Tests, CI, and Docs
Status: DONE
Started: 2026-04-14
Completed: 2026-04-14
Checkpoint: CP5_RELEASE

Tasks:
- [x] Add unit and integration tests
- [x] Add CI pipeline with coverage gate
- [x] Finalize docs and runbook

## Decisions Needed
- None yet.

## Change Log
- 2026-04-14: Tracker created.
- 2026-04-14: M1 completed and validated.
- 2026-04-14: M2 reviewed, fixed, and completed.
- 2026-04-14: M3 implemented and validated.
- 2026-04-14: M4 completed with distributed Neo4j tick lease/claim support.
- 2026-04-14: M5 completed (tests/docs updated; CI workflow with coverage gate added).
