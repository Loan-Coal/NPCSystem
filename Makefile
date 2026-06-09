PYTHON := python

ifneq (,$(wildcard .venv/Scripts/python.exe))
PYTHON := .venv/Scripts/python.exe
else ifneq (,$(wildcard .venv/bin/python))
PYTHON := .venv/bin/python
endif

BASE_URL ?= http://localhost:8000
API_KEY  ?= $(shell $(PYTHON) -c "import re; m=re.search(r'^API_KEY_SECRET=(.+)', open('.env').read(), re.M); print(m.group(1).strip() if m else '')")

.PHONY: install run test test-cov test-cov-v13 test-cov-full-report \
        test-v13-contracts test-v13-graph-admin test-v13-retrieval \
        test-v14-p0 test-v14-p1 test-v14-p2 test-v14-p3 test-v14-p4 test-v14-p5 \
        check-contracts check-contract-sync lint type check \
        check-rules check-rules-update check-layers check-docstrings type-ratchet type-ratchet-update check-harness \
        verify-v13 verify-v14-p0 verify-v14-p1 verify-v14-p2 verify-v14-p3 verify-v14-p4 verify-v14-p5 \
        eval eval-report eval-e2e scenarios scenario-edge scenario-demo demo-video eval-llm eval-llm-demo seed-api smoke \
        demo demo-seed demo-run demo-village demo-tavern test-demo dashboard \
        demo-snapshot demo-restore \
        seed-tavern-world seed-village-world

install:
	pip install -e .[dev]

run:
	uvicorn npc_engine.main:app --reload --reload-include="*.yaml" --reload-include="*.json"

smoke:
	$(PYTHON) -m pytest tests/unit/test_boot_smoke.py -q

# Boot gate (L9-01 / L9-05): rebuild the app image stamped with the current git
# SHA, start it, and fail if it never becomes healthy or if /health reports a
# different SHA (stale image). Catches "fresh build can't boot" and "up -d served
# an old image" regressions. Recommended for CI once CI changes are approved.
boot-check:
	BUILD_SHA=$$(git rev-parse --short HEAD) docker-compose up -d --build app
	$(PYTHON) e2e/scripts/boot_check.py --base-url $(BASE_URL) --expect-sha $$(git rev-parse --short HEAD)

test:
	$(PYTHON) -m pytest tests/ -q

test-cov:
	$(PYTHON) -m pytest tests/ -q --cov=npc_engine --cov=matchers --cov=summary --cov-report=term-missing --cov-fail-under=80

test-cov-v13:
	$(PYTHON) -m pytest -q tests/unit/test_schema_loader.py tests/unit/test_v1_route_versioning.py tests/unit/test_embedding_reconciler.py tests/unit/test_main_reconciler_lifespan.py tests/unit/test_schema_resolvers.py --cov=src/npc_engine/schema --cov=src/npc_engine/retrieval/embedding_reconciler --cov-report=term-missing --cov-fail-under=80

test-cov-full-report:
	$(PYTHON) -m pytest -q tests/ --cov=npc_engine --cov=evals --cov-report=term-missing

test-v13-contracts:
	$(PYTHON) -m pytest -q tests/unit/test_schema_loader.py tests/unit/test_v1_route_versioning.py tests/unit/test_auth_permissions_v13.py

test-v13-graph-admin:
	$(PYTHON) -m pytest -q tests/unit/test_graph_v13_routes.py tests/unit/test_graph_warning_pipeline.py tests/unit/test_graph_admin_reindex_jobs.py

test-v13-retrieval:
	$(PYTHON) -m pytest -q tests/unit/test_vector_store_and_index.py tests/unit/test_context_builder.py tests/unit/test_embedding_reconciler.py tests/unit/test_main_reconciler_lifespan.py

check-contracts:
	$(PYTHON) -m npc_engine.scripts.check_contracts

check-contract-sync:
	$(PYTHON) -m npc_engine.scripts.guard_contract_test_sync

test-v14-p0:
	$(PYTHON) -m pytest -q tests/unit/test_auth_idempotency_middleware_v14.py tests/unit/test_idempotency_service_v14.py tests/unit/test_llm_config_loader_v14.py tests/unit/test_engine_contract_schema_checker_v14.py tests/unit/test_main_reconciler_lifespan.py

test-v14-p1:
	$(PYTHON) -m pytest -q tests/unit/test_context_relevance_engine_v14.py tests/unit/test_context_budget_enforcer_v14.py tests/unit/test_context_builder.py tests/unit/test_context_pipeline.py

test-v14-p2:
	$(PYTHON) -m pytest -q tests/unit/test_currency_verification_engine_v14.py tests/unit/test_currency_writer_v14.py tests/unit/test_graph_writer_currency_coordinator_v14.py tests/unit/test_action_currency_routing_v14.py tests/unit/test_auth_idempotency_middleware_v14.py

test-v14-p3:
	$(PYTHON) -m pytest -q tests/unit/test_quest_lifecycle_engine_v14.py tests/unit/test_quest_reward_routing_v14.py tests/unit/test_quest_event_provenance_v14.py tests/unit/test_graph_writer_quest_reward_coordinator_v14.py tests/unit/test_quest_routes_v14.py tests/unit/test_v1_route_versioning.py tests/integration/test_quest_lifecycle_integration_v14.py

test-v14-p4:
	$(PYTHON) -m pytest -q tests/contract tests/unit/test_simulate_world_flow_v14.py tests/unit/test_guard_contract_test_sync_v14.py
	$(PYTHON) -m npc_engine.scripts.simulate_world_flow

test-v14-p5:
	$(PYTHON) -m pytest -q tests/unit -k "metrics or observability"

lint:
	$(PYTHON) -m ruff check src/

type:
	$(PYTHON) -m mypy src/

# --- Ratcheted gates (debt may shrink, never grow) -------------------------
# check-rules: enforce the strict CLAUDE.md rules; fails only on NEW violations
# vs scripts/rules_baseline.txt. Run check-rules-update after fixing some to lock it in.
check-rules:
	$(PYTHON) scripts/check_rules.py

check-rules-update:
	$(PYTHON) scripts/check_rules.py --update-baseline

# type-ratchet: kept for historical reference; mypy is now at 0 so 'make type' is the gate.
type-ratchet:
	$(PYTHON) scripts/mypy_ratchet.py

type-ratchet-update:
	$(PYTHON) scripts/mypy_ratchet.py --update

# check-harness: fail when the harness docs contradict the live gates.
check-harness:
	$(PYTHON) scripts/check_harness_honesty.py

# check-layers: enforce the NPC Engine layer model (SEV-31).
check-layers:
	$(PYTHON) scripts/check_layers.py

# check-docstrings: fail when any src/ file lacks Layer:/Purpose: (+ Public surface: for __init__.py).
check-docstrings:
	$(PYTHON) scripts/docstring_audit.py

# check: the single canonical health gate. Same command locally and in CI.
# mypy is at 0 (SEV-14 done) so 'type' is now a hard gate here.
check: lint check-rules check-layers check-docstrings type check-harness test-cov

verify-v13: lint type test-v13-contracts test-v13-graph-admin test-v13-retrieval test-cov-v13 test-cov-full-report

verify-v14-p0: lint type check-contracts test-v14-p0

verify-v14-p1: lint type test-v14-p1

verify-v14-p2: lint type test-v14-p1 test-v14-p2

verify-v14-p3: lint type test-v14-p1 test-v14-p2 test-v14-p3

verify-v14-p4: lint type check-contracts check-contract-sync test-v14-p4

verify-v14-p5: lint type test-v14-p5

eval:
	@echo "Running eval cases against $(BASE_URL) ..."
	$(PYTHON) evals/runner.py \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--cases evals/cases \
		--reports evals/reports

# eval-report: alias for `eval` — runs the suite and prints the published
# anti-hallucination guarantee ("0 lore hallucinations across N adversarial turns").
eval-report: eval

# eval-e2e: run YAML eval cases as pytest parametrized tests (requires --scenarios-only)
eval-e2e:
	$(PYTHON) -m pytest e2e/scenarios/scenario_yaml_evals.py -v -m eval --scenarios-only -p no:cacheprovider $(ARGS)

scenarios:
	$(PYTHON) -m pytest e2e/scenarios/ -v -s -m "not llm_eval" --scenarios-only -p no:cacheprovider

scenario-edge:
	$(PYTHON) -m pytest e2e/scenarios/ -v -s -k "edge" --scenarios-only -p no:cacheprovider

scenario-demo:
	$(PYTHON) -m pytest e2e/scenarios/scenario_demo.py -v -s --scenarios-only -p no:cacheprovider

demo-video:
	$(PYTHON) -m pytest e2e/scenarios/scenario_demo_video.py -v -s -m demo_video --scenarios-only -p no:cacheprovider

eval-llm:
	$(PYTHON) -m pytest e2e/scenarios/scenario_llm_judge.py -v -s -m llm_eval --scenarios-only -p no:cacheprovider

eval-llm-demo:
	$(PYTHON) -m pytest e2e/scenarios/scenario_demo_game_judge.py -v -s -m llm_eval --scenarios-only -p no:cacheprovider

# eval-retrieval: measure retrieval precision@k/recall@k/MRR against demo world labels
eval-retrieval:
	$(PYTHON) -m evals.retrieval_runner

# ---------------------------------------------------------------------------
# Demo game targets (Phase 2)
# Run from repo root so demo_game/ is on sys.path.
# ---------------------------------------------------------------------------

# demo: start engine (idempotent) then open Pygame window
demo:
	docker-compose up -d
	$(PYTHON) -m demo_game

# dashboard: print the URL for the Phase 12 designer web dashboard.
# The FastAPI app serves it as static files at /dashboard once the backend is up
# (docker-compose up -d). Paste an API key in the top bar to connect.
dashboard:
	@echo "Designer dashboard: http://localhost:8000/dashboard/  (start backend first: docker-compose up -d)"

# hello: integrator hello-world — seed one NPC, send one dialogue turn, print reply
hello:
	$(PYTHON) -m demo_game.quickstart

# demo-seed: seed the demo world via the HTTP API (idempotent — safe to re-run)
demo-seed:
	$(PYTHON) -m demo_game.seed

# demo-run: play the scripted hackathon scenario (see docs/DEMO_SCRIPT.md)
# ARGS: --dry-run (no API calls), --cached (recording mode, error on miss)
demo-run:
	$(PYTHON) -m demo_game.run $(ARGS)

# test-demo: run demo_game unit tests in isolation (separate from make test)
# Requires: pip install -r demo_game/requirements.txt
test-demo:
	$(PYTHON) -m pytest demo_game/tests/ -q

# demo-snapshot: export current Neo4j graph to .cache/demo/snapshot.json
# Run once before the demo to capture the clean seeded state.
demo-snapshot:
	$(PYTHON) -m demo_game.snapshot --mode snapshot

# demo-restore: wipe Neo4j graph and reimport from .cache/demo/snapshot.json
# Use between demo takes to reset the world to the snapshot state.
demo-restore:
	$(PYTHON) -m demo_game.snapshot --mode restore

# ---------------------------------------------------------------------------
# seed-tavern-world / seed-village-world: seed independent eval worlds (idempotent)
seed-tavern-world:
	$(PYTHON) -m seeds.worlds.seed_tavern_world --base-url $(BASE_URL) --api-key $(API_KEY)

seed-village-world:
	$(PYTHON) -m seeds.worlds.seed_village_world --base-url $(BASE_URL) --api-key $(API_KEY)

# ---------------------------------------------------------------------------
# Alternate storyline demos (Phase 3, S3.0)
# Each demo uses its own eval world seed and LLM cache directory.
# ---------------------------------------------------------------------------

# demo-village: village crisis demo (crop blight + bandit raid)
# Requires: make seed-village-world
demo-village:
	$(PYTHON) -m demo_game.scenarios.run_village_crisis $(ARGS)

# demo-tavern: tavern intrigue demo (theft + voice distinctiveness)
# Requires: make seed-tavern-world
demo-tavern:
	$(PYTHON) -m demo_game.scenarios.run_tavern_intrigue $(ARGS)

# seed-api: seed world data via the external HTTP API (works from outside Docker)
seed-api:
	$(PYTHON) src/npc_engine/data/api_seeder.py \
		--base-url $(BASE_URL) --api-key $(API_KEY)
