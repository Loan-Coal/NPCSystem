PYTHON := python

ifneq (,$(wildcard .venv/Scripts/python.exe))
PYTHON := .venv/Scripts/python.exe
else ifneq (,$(wildcard .venv/bin/python))
PYTHON := .venv/bin/python
else ifneq (,$(wildcard ../.venv/Scripts/python.exe))
PYTHON := ../.venv/Scripts/python.exe
else ifneq (,$(wildcard ../.venv/bin/python))
PYTHON := ../.venv/bin/python
endif

install:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload

test:
	$(PYTHON) -m pytest -q

test-cov:
	$(PYTHON) -m pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80

test-cov-v13:
	$(PYTHON) -m pytest -q tests/unit/test_schema_loader.py tests/unit/test_v1_route_versioning.py tests/unit/test_embedding_reconciler.py tests/unit/test_main_reconciler_lifespan.py --cov=main --cov=config --cov=retrieval.embedding_reconciler --cov-report=term-missing --cov-fail-under=80

test-cov-full-report:
	$(PYTHON) -m pytest -q --cov=. --cov-report=term-missing

test-v13-contracts:
	$(PYTHON) -m pytest -q tests/unit/test_schema_loader.py tests/unit/test_v1_route_versioning.py tests/unit/test_auth_permissions_v13.py

test-v13-graph-admin:
	$(PYTHON) -m pytest -q tests/unit/test_graph_v13_routes.py tests/unit/test_graph_warning_pipeline.py tests/unit/test_graph_admin_reindex_jobs.py

test-v13-retrieval:
	$(PYTHON) -m pytest -q tests/unit/test_vector_store_and_index.py tests/unit/test_context_builder.py tests/unit/test_embedding_reconciler.py tests/unit/test_main_reconciler_lifespan.py

check-contracts:
	$(PYTHON) -m scripts.check_contracts

check-contract-sync:
	$(PYTHON) -m scripts.guard_contract_test_sync

test-v14-p0:
	$(PYTHON) -m pytest -q tests/unit/test_auth_idempotency_middleware_v14.py tests/unit/test_idempotency_service_v14.py tests/unit/test_llm_config_loader_v14.py tests/unit/test_engine_contract_schema_checker_v14.py tests/unit/test_main_reconciler_lifespan.py

test-v14-p1:
	$(PYTHON) -m pytest -q tests/unit/test_context_relevance_engine_v14.py tests/unit/test_context_budget_enforcer_v14.py tests/unit/test_context_builder.py tests/unit/test_context_pipeline.py

test-v14-p2:
	$(PYTHON) -m pytest -q tests/unit/test_currency_verification_engine_v14.py tests/unit/test_currency_writer_v14.py tests/unit/test_graph_writer_currency_coordinator_v14.py tests/unit/test_action_currency_routing_v14.py tests/unit/test_auth_idempotency_middleware_v14.py

test-v14-p3:
	$(PYTHON) -m pytest -q tests/unit/test_quest_lifecycle_engine_v14.py tests/unit/test_quest_reward_routing_v14.py tests/unit/test_quest_event_provenance_v14.py tests/unit/test_graph_writer_quest_reward_coordinator_v14.py tests/unit/test_quest_routes_v14.py tests/unit/test_v1_route_versioning.py tests/integration/test_quest_lifecycle_integration_v14.py

test-v14-p4:
	$(PYTHON) -m pytest -q tests/engine_contract_tests tests/unit/test_simulate_world_flow_v14.py tests/unit/test_guard_contract_test_sync_v14.py
	$(PYTHON) -m scripts.simulate_world_flow

test-v14-p5:
	$(PYTHON) -m pytest -q tests/unit -k "metrics or observability"

lint:
	$(PYTHON) -m ruff check .

type:
	$(PYTHON) -m mypy .

check: lint type test

verify-v13: lint type test-v13-contracts test-v13-graph-admin test-v13-retrieval test-cov-v13 test-cov-full-report

verify-v14-p0: lint type check-contracts test-v14-p0

verify-v14-p1: lint type test-v14-p1

verify-v14-p2: lint type test-v14-p1 test-v14-p2

verify-v14-p3: lint type test-v14-p1 test-v14-p2 test-v14-p3

verify-v14-p4: lint type check-contracts check-contract-sync test-v14-p4

verify-v14-p5: lint type test-v14-p5

seed:
	python -m data.seed
