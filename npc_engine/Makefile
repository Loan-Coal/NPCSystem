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
	$(PYTHON) -m pytest -q tests/unit/test_graph_v13_routes.py tests/unit/test_graph_edit_service_edges.py tests/unit/test_graph_admin_reindex_jobs.py

test-v13-retrieval:
	$(PYTHON) -m pytest -q tests/unit/test_vector_store_and_index.py tests/unit/test_context_builder.py tests/unit/test_embedding_reconciler.py tests/unit/test_main_reconciler_lifespan.py

lint:
	$(PYTHON) -m ruff check .

type:
	$(PYTHON) -m mypy .

check: lint type test

verify-v13: lint type test-v13-contracts test-v13-graph-admin test-v13-retrieval test-cov-v13 test-cov-full-report

seed:
	python -m data.seed
