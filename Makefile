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
        check-rules check-rules-update check-evals-rules check-evals-rules-update \
        check-layers check-docstrings roadmap-verify check-human-gates check-conservation check-label-survival check-test-quality check-mutations \
        check-migrations check-api-stability check-api-contract check-engine-logs \
        check-base-rate check-base-rate-update check-dead-keywords-update \
        check-ledger-ids check-cited-reports check-ceiling-baseline \
        type-ratchet type-ratchet-update type-evals type-evals-update type-demo type-demo-update check-harness \
        test-cov-evals test-integration check-integration-baseline check-integration-baseline-update \
        openapi harness-status check-readme-paths verify-v13 verify-v14-p0 verify-v14-p1 verify-v14-p2 verify-v14-p3 verify-v14-p4 verify-v14-p5 \
        eval eval-report eval-anti-hallucination eval-e2e eval-generate eval-judge eval-score eval-calibrate eval-adjudicate eval-retrieval eval-arm-probe eval-supply-report probe-inner-life probe-ceiling eval-compare eval-deterministic-verdicts eval-replay-criteria eval-sequence eval-harness check-dead-keywords mock-calibrate mock-calibrate-oracle measure-reset-fidelity label-export label-import scenarios scenario-edge scenario-demo demo-video eval-llm eval-llm-demo eval-combined draft-cases hedge-probe seed-probe seed-api smoke \
        demo demo-seed demo-run demo-village demo-tavern test-demo dashboard \
        demo-snapshot demo-restore eval-world-reset restore-with-app-stopped \
        seed-tavern-world seed-village-world package eval-dashboard verify-rag

install:
	pip install -e .[dev]

# package: build the standalone npc_engine_server binary via PyInstaller (SHIP-04).
# Requires: pip install -e .[packaging]  (build-time only, not a runtime or dev dep).
# Output:   dist/npc_engine_server/npc_engine_server[.exe]
package:
	$(PYTHON) -m PyInstaller packaging/npc_engine.spec --distpath dist/npc_engine_server --workpath build/pyinstaller --noconfirm

run:
	uvicorn npc_engine.main:app --reload --reload-include="*.yaml" --reload-include="*.json"

# openapi: print the live OpenAPI schema, or write it with OUT=<path>. Replaces the
# tracked live_openapi.json deleted in R4.7, which had drifted four routes behind the
# app (/setup/config, /setup/validate, /v1/admin/debug/vector-store,
# /v1/admin/vector-store/rehydrate) while looking authoritative. Keys are sorted so two
# dumps of the same app are byte-identical. Do not commit the output.
openapi:
	$(PYTHON) scripts/dump_openapi.py $(if $(OUT),--out $(OUT),)

# harness-status: print what `make check` runs and every baseline's live value, read from
# the files that hold them. Exists so no document has to keep a copy of a number: R4.6
# found HARNESS_GATES.md asserting "57 today" against a live 118 and "256 today" against a
# live 0, both untouched for 85 days. Reporting only -- deliberately NOT in `make check`,
# because it cannot fail and a gate that cannot fail is what R1 existed to delete.
harness-status:
	$(PYTHON) scripts/harness_status.py

# check-readme-paths: fail when README.md links to a path that does not exist. Deliberately
# NOT added to `make check`: DEC-250 freezes the gate apparatus through end-of-R4 and DEC-224
# forbids a new gate without retiring one. Enforcement comes from
# tests/unit/scripts/test_check_readme_paths.py instead, which `test-cov` already runs inside
# `make check` -- same coverage, no new gate (R4.6).
check-readme-paths:
	$(PYTHON) scripts/check_readme_paths.py

smoke:
	$(PYTHON) -m pytest tests/unit/conformance/test_boot_smoke.py -q

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
	$(PYTHON) -m pytest tests/ -q --cov=npc_engine --cov=matchers --cov=summary --cov=runner --cov-report=term-missing --cov-fail-under=80

test-cov-v13:
	$(PYTHON) -m pytest -q tests/unit/config/test_schema_loader.py tests/unit/conformance/test_v1_route_versioning.py tests/unit/retrieval/test_embedding_reconciler.py tests/unit/api/test_main_reconciler_lifespan.py tests/unit/config/test_schema_resolvers.py --cov=src/npc_engine/schema --cov=src/npc_engine/retrieval/embedding_reconciler --cov-report=term-missing --cov-fail-under=80

test-cov-full-report:
	$(PYTHON) -m pytest -q tests/ --cov=npc_engine --cov=evals --cov-report=term-missing

test-v13-contracts:
	$(PYTHON) -m pytest -q tests/unit/config/test_schema_loader.py tests/unit/conformance/test_v1_route_versioning.py tests/unit/api/test_auth_permissions_v13.py

test-v13-graph-admin:
	$(PYTHON) -m pytest -q tests/unit/api/test_graph_v13_routes.py tests/unit/api/test_graph_warning_pipeline.py tests/unit/api/test_graph_admin_reindex_jobs.py

test-v13-retrieval:
	$(PYTHON) -m pytest -q tests/unit/retrieval/test_vector_store_and_index.py tests/unit/retrieval/test_context_builder.py tests/unit/retrieval/test_embedding_reconciler.py tests/unit/api/test_main_reconciler_lifespan.py

check-contracts:
	$(PYTHON) -m npc_engine.scripts.check_contracts

check-contract-sync:
	$(PYTHON) -m npc_engine.scripts.guard_contract_test_sync

test-v14-p0:
	$(PYTHON) -m pytest -q tests/unit/api/test_auth_idempotency_middleware_v14.py tests/unit/graph/test_idempotency_service_v14.py tests/unit/llm/test_llm_config_loader_v14.py tests/unit/conformance/test_engine_contract_schema_checker_v14.py tests/unit/api/test_main_reconciler_lifespan.py

test-v14-p1:
	$(PYTHON) -m pytest -q tests/unit/retrieval/test_context_relevance_engine_v14.py tests/unit/retrieval/test_context_budget_enforcer_v14.py tests/unit/retrieval/test_context_builder.py

test-v14-p2:
	$(PYTHON) -m pytest -q tests/unit/graph/test_currency_verification_engine_v14.py tests/unit/graph/test_currency_writer_v14.py tests/unit/graph/test_graph_writer_currency_coordinator_v14.py tests/unit/graph/test_action_currency_routing_v14.py tests/unit/api/test_auth_idempotency_middleware_v14.py

test-v14-p3:
	$(PYTHON) -m pytest -q tests/unit/engines/test_quest_lifecycle_engine_v14.py tests/unit/graph/test_quest_reward_routing_v14.py tests/unit/graph/test_quest_event_provenance_v14.py tests/unit/graph/test_graph_writer_quest_reward_coordinator_v14.py tests/unit/api/test_quest_routes_v14.py tests/unit/conformance/test_v1_route_versioning.py tests/integration/test_quest_lifecycle_integration_v14.py

test-v14-p4:
	$(PYTHON) -m pytest -q tests/contract tests/unit/api/test_simulate_world_flow_v14.py tests/unit/conformance/test_guard_contract_test_sync_v14.py
	$(PYTHON) -m npc_engine.scripts.simulate_world_flow

test-v14-p5:
	$(PYTHON) -m pytest -q tests/unit -k "metrics or observability"

# lint: ruff over the shipped engine AND the eval harness (EVAL-P0.3).
# evals/ is in scope because it is production-adjacent code that gates releases;
# tests/unit/evals/test_gate_scope.py fails if this recipe ever loses evals/.
lint:
	$(PYTHON) -m ruff check src/ evals/

type:
	$(PYTHON) -m mypy src/

# --- Ratcheted gates (debt may shrink, never grow) -------------------------
# check-rules: enforce the strict CLAUDE.md rules; fails only on NEW violations
# vs scripts/rules_baseline.txt. Run check-rules-update after fixing some to lock it in.
check-rules:
	$(PYTHON) scripts/check_rules.py

check-rules-update:
	$(PYTHON) scripts/check_rules.py --update-baseline

# check-evals-rules: enforce CLAUDE.md rules on evals/ with a separate ratcheted baseline
# (scripts/evals_baseline.txt). Fails only on NEW violations; 59 grandfathered (EVAL-P15.4).
check-evals-rules:
	$(PYTHON) scripts/check_rules.py --evals

check-evals-rules-update:
	$(PYTHON) scripts/check_rules.py --update-evals-baseline

# type-ratchet: kept for historical reference; mypy is now at 0 so 'make type' is the gate.
type-ratchet:
	$(PYTHON) scripts/mypy_ratchet.py

type-ratchet-update:
	$(PYTHON) scripts/mypy_ratchet.py --update

# type-evals: ratchet mypy errors in evals/ (baseline in .mypy_evals_baseline, EVAL-P15.4).
# Fails only when the error count grows above baseline. The file holds 0 today; the
# comment used to say 16 and had gone stale (ISSUE-249).
type-evals:
	$(PYTHON) scripts/mypy_evals_ratchet.py

type-evals-update:
	$(PYTHON) scripts/mypy_evals_ratchet.py --update

# type-demo: ratchet mypy errors in demo_game/ (baseline 256 in .mypy_baseline_demo, R2.2).
# demo_game/ was gated by nothing at all — 256 errors across 45 files, invisible on every
# push. Ratchet and not a hard zero for DEC-236's reason: a gate that is red before the
# work starts gets switched off, and fixing 256 errors is not this task's job. The count
# is measured with mypy.ini (which wins over pyproject's strict=true), i.e. exactly the
# invocation this target uses. Requires demo_game/requirements.txt to be installed, or
# mypy reports import errors and the count will not reproduce.
type-demo:
	$(PYTHON) scripts/mypy_ratchet.py --target demo_game/ --baseline-file .mypy_baseline_demo --label mypy-demo-ratchet --update-hint "make type-demo-update"

type-demo-update:
	$(PYTHON) scripts/mypy_ratchet.py --target demo_game/ --baseline-file .mypy_baseline_demo --label mypy-demo-ratchet --update-hint "make type-demo-update" --update

# test-integration: the Neo4j-backed integration suite. Identical command locally and in
# CI (R2.2). Requires the graph up and NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD exported:
#   docker compose -f docker-compose.yml -f docker-compose.test.yml up -d neo4j
# Not a `check:` prerequisite — `make check` must stay runnable without Docker.
test-integration:
	$(PYTHON) -m pytest tests/integration -q --tb=no -rf -p no:cacheprovider $(ARGS)

# check-integration-baseline: ratchet the integration suite against the committed
# allowlist of known-failing node ids in scripts/integration_baseline.txt (R2.2).
# A node-id set, not a count: a count passes when one test is fixed and another breaks in
# the same run. Recorded 2026-09-01 at 8 known-failing, measured against a live neo4j:5 —
# which settles ISSUE-236 in favour of .loop-state/gate_baseline.json's 8 over ISSUE-233's
# 9 (test_set_standing_independent_directions now passes). R3.6 shrinks this file.
# The gate also asserts a floor of executed tests: _skip_if_no_neo4j() skips at runtime, so
# a misconfigured job would otherwise pass green over an all-skip suite — the exact vacuity
# R2.2 exists to remove.
# check-ledger-ids: fail when a reused DEC/ISSUE id is undocumented, or when a planning
# document cites an id that was never assigned (R4.5, DEC-239).
# Contract is "document every reuse", not "no id is reused": all four colliding DEC ids are
# cited by number from live source, so renumbering would silently repoint code comments at a
# decision they were not written about. Counterfactual recorded in
# tests/unit/scripts/test_check_ledger_ids.py — an undocumented collision reds, a documented
# one greens. Measured 2026-09-01: 4 DEC + 2 ISSUE reuses, all documented; 0 undeclared citations.
check-ledger-ids:
	$(PYTHON) scripts/check_ledger_ids.py

check-integration-baseline:
	$(PYTHON) scripts/check_integration_baseline.py

check-integration-baseline-update:
	$(PYTHON) scripts/check_integration_baseline.py --update-baseline

# test-cov-evals: gate evals/ test coverage at ~78% measured baseline; floor 75 (EVAL-P15.4).
# Runs evals unit tests and script tests only (fast; integration evals need real artifacts).
test-cov-evals:
	$(PYTHON) -m pytest tests/unit/evals/ tests/unit/scripts/ -q --cov=evals --cov-report=term-missing --cov-fail-under=75

# check-harness: fail when the harness docs contradict the live gates.
check-harness:
	$(PYTHON) scripts/check_harness_honesty.py

# check-layers: enforce the NPC Engine layer model (SEV-31).
check-layers:
	$(PYTHON) scripts/check_layers.py

# roadmap-verify: grammar doctor for the overnight loop's ROADMAP queue fence.
# Run after ANY hand edit to project-harness/ROADMAP.md — a marker that does not
# parse back is invisible to the cursor, and its task gets implemented twice.
roadmap-verify:
	$(PYTHON) scripts/roadmap_cursor.py --verify

# check-human-gates: audit the `#### HUMAN GATE` grammar in ROADMAP.md (DEC-164).
# Grammar only — a closed gate is normal and exits 0. Red means a gate references a
# task id that does not exist, is missing a field, or can never open.
check-human-gates:
	$(PYTHON) scripts/check_human_gates.py --verify

# check-blocking: exit 1 while any HUMAN GATE is not yet cleared (R1.2).
# NOT in `make check` — it reds on 6+ open gates and would block all loop tasks.
# Run manually to get a go/no-go signal before starting human gate work.
check-blocking:
	$(PYTHON) scripts/check_human_gates.py --strict

# check-conservation: gate on conservation identity violations over the committed artifact.
# Exits non-zero when any identity fails (wired as a gate by EVAL-P17.6).
# Identity 4 is DEFERRED (spans two different artifact producers).
check-conservation:
	$(PYTHON) scripts/check_conservation.py

# check-dead-keywords: keyword_none terms with zero hits in the newest committed
# generation (EVAL-P19.3). Ratcheted at 208 by R2.3 — still never edits a case file
# (what a case should forbid is a human call, EVAL-P20.1), but it no longer exits 0
# unconditionally: a newly added guaranteed-pass term is RED. The corpus moved from
# k3_73e6c36 to k3_77688e7_regen1 in the same commit, which is what took the count
# from 237 to 208; no case file was edited to get there.
check-dead-keywords:
	$(PYTHON) scripts/check_dead_keywords.py

check-dead-keywords-update:
	$(PYTHON) scripts/check_dead_keywords.py --update

# check-base-rate: the guard battery's pass base rate against the [0.55, 0.85] target
# band (EVAL-P25.3), ratcheted by R2.3 against scripts/base_rate_baseline.json.
# Ratchet, not advisory: advisory's promotion criterion named EVAL-P26, a phase DEC-233
# culled, so it would never have fired. Not raw blocking either: nine of ten families
# breach today for a defect no scheduled task fixes, so blocking would red every
# downstream task through no fault of its own. Re-pointing at a newer generation is a
# deliberate human step — automatic re-pointing would let a worse generation launder
# itself into the baseline.
check-base-rate:
	$(PYTHON) scripts/check_base_rate.py evals/generations/k3_77688e7_regen1

check-base-rate-update:
	$(PYTHON) scripts/check_base_rate.py evals/generations/k3_77688e7_regen1 --update

# check-cited-reports: reds when a project-harness document cites an eval report that is
# not committed (B5/ISSUE-247). Reports are ignored by default and tracked once cited —
# see DEC-241 for why "tracked when cited" beats tracking all 421 of them.
check-cited-reports:
	$(PYTHON) scripts/check_cited_reports.py

# check-ceiling-baseline: the measured assembled-context ceiling must stay a RECORDED
# measurement that states what it measured, and the shipped window must still clear it
# (B6/R2.7b, DEC-242). This does NOT re-measure — that needs a live stack, and is
# `make probe-ceiling ARGS="--record --corpus-sha <sha>"`.
check-ceiling-baseline:
	$(PYTHON) scripts/check_ceiling_baseline.py

# check-label-survival: freeze-gate check — does the labels file survive the
# committed transcript unchanged (no drift, no orphaning)? Run before spending a
# regeneration or a labelling pass (EVAL-P20→P24 unblock plan, Phase A1/B3).
check-label-survival:
	$(PYTHON) scripts/check_label_survival.py

# check-test-quality: static scan of tests/** for anti-vacuous patterns (4 types).
# Exits 0 always (items are fixed or suppressed inline with '# quality-ok: <reason>').
# Wired into make check as of EVAL-P15.4.
check-test-quality:
	$(PYTHON) scripts/check_test_quality.py

# check-docstrings: fail when any src/ or evals/ file lacks Layer:/Purpose: (+ Public surface: for __init__.py).
check-docstrings:
	$(PYTHON) scripts/docstring_audit.py

# check-mutations: apply named mutations to evals/ code one at a time and fail if any
# survives the unit suite. Proves EVAL-P15.1-P15.5 actually catch the structural
# failures they were built to detect (EVAL-P15.6).
check-mutations:
	$(PYTHON) scripts/mutation_probe.py

# R1.8 gates. All three are blocking. Each accepts today's state as a recorded
# baseline and reds on any increase, so none of them needs a "warn-only until
# promoted" phase — the state a gate cannot fail in is the one R1 exists to remove.

# check-migrations: a node type gained a required field that no migration in
# scripts/migrations/ declares (existing graph nodes would not carry it).
check-migrations:
	$(PYTHON) scripts/check_migrations.py

# check-api-stability: a /v1 response model lost a field it had in the baseline.
# Narrow by construction: an AST field-drop ratchet over api/response_models/ and
# api/schemas.py only (17 of 105 api/ models). check-api-contract is the real contract
# gate; this one is kept because it sees a source-level rename before a route is wired.
check-api-stability:
	$(PYTHON) scripts/check_api_stability.py

# verify-rag: exercise the real embedding path (loads the model, needs torch).
# Deliberately NOT in `check`: CI has no GPU and no torch, and a skipif guard would make
# it pass by skipping. Human-run verification instead (R5.2).
verify-rag:
	$(PYTHON) scripts/verify_rag.py

# check-api-contract: the /v1 surface changed in a way that breaks an existing consumer
# — route removed (including the WebSocket route, which app.openapi() does not list),
# response field dropped or retyped, request tightened, status code or auth changed.
# Additive change passes and needs no baseline edit. Re-record a deliberate break with:
#   python scripts/check_api_contract.py --update      (see docs/API_STABILITY.md, DEC-253)
check-api-contract:
	$(PYTHON) scripts/check_api_contract.py

# check-engine-logs: engine logger.info calls missing duration_ms exceed the
# recorded baseline (42 at R1.8).
check-engine-logs:
	$(PYTHON) scripts/check_engine_logs.py

# check: the single canonical health gate. Same command locally and in CI.
# mypy is at 0 (SEV-14 done) so 'type' is now a hard gate here.
# EVAL-P15.4 added: check-evals-rules type-evals check-test-quality test-cov-evals
# R1.3: check-conservation and check-label-survival moved out — they audited
# unchangeable committed inputs; conservation now runs inside eval-generate.
# R1.4: check-harness moved before lint — H1 must fire even when lint short-circuits.
# R1.8: three blocking ratchet gates added (check-migrations check-api-stability
#        check-engine-logs). check-dead-tests was NOT added — it duplicated
#        check-test-quality, whose NO_ASSERTION pattern absorbed its one real rule.
# R2.3: check-base-rate and check-dead-keywords added, both ratcheted. The plan
#        predicted 16 targets (check-base-rate only); check-dead-keywords is here too
#        because R2.4's RED anchor is its ratchet direction, and a ratchet outside this
#        aggregate is a gate nothing runs — the exact shape R1 spent three tasks
#        removing. 17 targets.
# R2.2: test-cov-v13 and test-cov-full-report folded in (DEC-238), 17 -> 19. They were
#        verify-v13 prerequisites that only CI ran directly, so collapsing the CI
#        coverage job into `make check` without them would have deleted two gates in
#        the commit meant to restore gates. CI now runs this aggregate as one step, so
#        anything added here is enforced on push without editing any YAML.
# R4.5: check-ledger-ids added, 19 -> 20. Placed beside check-harness because both audit
#        the project ledgers rather than the code, and both must fire before lint can
#        short-circuit the run (the R1.4 ordering fix, applied to the new gate too).
check: check-harness check-ledger-ids check-cited-reports check-ceiling-baseline lint check-rules check-evals-rules check-layers check-docstrings type type-evals check-human-gates check-test-quality test-cov test-cov-evals test-cov-v13 test-cov-full-report check-migrations check-api-stability check-api-contract check-engine-logs check-base-rate check-dead-keywords

verify-v13: lint type test-v13-contracts test-v13-graph-admin test-v13-retrieval test-cov-v13 test-cov-full-report

verify-v14-p0: lint type check-contracts test-v14-p0

verify-v14-p1: lint type test-v14-p1

verify-v14-p2: lint type test-v14-p1 test-v14-p2

verify-v14-p3: lint type test-v14-p1 test-v14-p2 test-v14-p3

verify-v14-p4: lint type check-contracts check-contract-sync test-v14-p4

verify-v14-p5: lint type test-v14-p5

# ---------------------------------------------------------------------------
# Eval targets. Every one below is a thin alias over `python -m evals <verb>`
# (EVAL-P6.3). No target was deleted; deleting them is a separate, later step
# once nothing references them (DEC-148: coverage parity -> aliases -> delete last).
# Exception: eval-llm / eval-llm-demo stay direct pytest invocations — they are
# test-suite runs, not harness modules, so routing them through the CLI would mean
# the CLI shelling out to pytest. See DEC-155.
# ---------------------------------------------------------------------------

eval:
	@echo "Running eval cases against $(BASE_URL) ..."
	$(PYTHON) -m evals report \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--cases evals/cases \
		--reports evals/reports

# eval-report: alias for `eval` — runs the suite and prints the published
# anti-hallucination guarantee ("0 lore hallucinations across N adversarial turns").
eval-report: eval

# eval-anti-hallucination: run JSON-fixture anti-hallucination eval against the live engine
eval-anti-hallucination:
	@echo "Running anti-hallucination eval against $(BASE_URL) ..."
	$(PYTHON) -m evals anti-hallucination \
		--base-url $(BASE_URL) \
		--api-key $(API_KEY) \
		--fixture evals/cases/anti_hallucination_demo.json \
		--reports evals/reports

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

# eval-retrieval: measure retrieval precision@k/recall@k/MRR against demo world labels.
# evals.engine_adapter connects to Neo4j directly (bolt), which needs the app
# container's network (EVAL-P20.3a / ISSUE-131 — see the demo-snapshot comment above).
# GEN_ID / RETRIEVAL_PROFILE are optional and forwarded to the runner's own flags, which
# have always accepted them. Without them this ran with NO arguments, so
# retrieval_metrics.json was never written and every trend row carried
# mean_precision_at_k=null. GEN_ID becomes the CONTAINER path (/work/...), not the host
# path: the recipe runs inside the app container, where the host path does not exist.
# Usage: make eval-retrieval GEN_ID=k3_abc123 RETRIEVAL_PROFILE=default
eval-retrieval:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m evals retrieval \
		$(if $(GEN_ID),--gen-dir /work/evals/generations/$(GEN_ID),) \
		$(if $(RETRIEVAL_PROFILE),--retrieval-profile $(RETRIEVAL_PROFILE),)

# probe-inner-life: the 8-NPC inner-life probe (ISSUE-216). Reports which context slots
# are actually POPULATED per NPC — the instrument behind every "beliefs 8/8, goals 8/8,
# memories 8/8, current_location 8/8, was 0/975" figure from P0 to P8.
#
# It lived in a session scratchpad until P9, so it was rewritten from prose before each
# use; in P8 the reconstruction parsed the wrong response shape and reported a false 0/8
# before being corrected. Its parse is now pinned by
# tests/unit/scripts/test_probe_inner_life.py.
#
# player_relation tracks LIVE world state (an ordinary dialogue turn creates a RELATES_TO
# edge), so it is comparable across phases ONLY immediately after `make eval-world-reset`.
# Usage: make probe-inner-life LABEL="post-P9"
probe-inner-life:
	API_KEY_SECRET="$(API_KEY)" $(PYTHON) scripts/probe_inner_life.py "$(or $(LABEL),unlabelled)" $(ARGS)

# probe-ceiling: the 8-NPC assembled-context CEILING probe (P10/DEC-215). Reports what
# context assembly COSTS per NPC, which is the number probe-inner-life cannot give — it
# reports slot PRESENCE and never a token total. This is P10's primary trim input.
#
# Two totals are printed because the route returns two that differ: `summed` is the
# receipt's per-item sum, `serial` is the serialized blob the budget is actually enforced
# against. CEILING is the larger, because a window sized to the smaller has headroom that
# does not exist. Parse pinned by tests/unit/scripts/test_probe_context_ceiling.py.
#
# It also answers P10 gate 11: per NPC, whether the CONFIGURED window re-opens ISSUE-209's
# non-monotone tier-A skip. Run it at the POST-TRIM window — at a window where nothing is
# dropped the answer is vacuous.
#
# No LLM is called; the debug route assembles context and returns the receipt.
# Usage: make probe-ceiling LABEL="P10 16384" [ARGS="--retrieval-profile no_rag"]
probe-ceiling:
	API_KEY_SECRET="$(API_KEY)" $(PYTHON) scripts/probe_context_ceiling.py "$(or $(LABEL),unlabelled)" $(ARGS)

# eval-supply-report: measured supply per ceiling knob, over the 8-NPC probe roster.
# Run this BEFORE declaring an A/B arm (DEC-214). It answers the question the receipts
# cannot: a receipt shows min(supply, ceiling) items, so a saturated default and a
# generous world look identical, and that is how `wide_events` and `wide_rag` came to be
# declared as arms with zero exposure.
#
# Runs INSIDE the app container: it reads Neo4j directly, and neo4j has no host port
# mapping (see the eval-world-reset note below). No HTTP, no LLM, no writes.
# Usage: make eval-supply-report [ARGS="--npc mira_innkeeper --npc lira_fence"]
eval-supply-report:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m evals.arm_supply $(ARGS)

# eval-arm-probe: the P9 gate. Four ordered gates over 2 cases x N arms at k=1 — config,
# corpus, cache isolation, effect — diffing each arm's item_keys and tier_spend through
# GET /v1/admin/debug/retrieval, printing the corpus fingerprint and the per-arm-pairing
# MDE, and exiting non-zero if any arm is indistinguishable from default.
#
# It is the thing standing between an operator and a ten-hour null result: it costs
# seconds and it can say the paired generation is pointless while cancelling is still
# free. Run it AFTER `make eval-world-reset`, and before any P10 generation.
#
# Runs on the HOST, not in the app container: gates 1 and 3 are pytest modules that need
# the test tree, and the engine is reached over the published port. No LLM is called —
# the debug route assembles context and returns the receipt without generating.
# Usage: make eval-arm-probe [ARGS="--gate 4"]
eval-arm-probe:
	API_KEY_SECRET="$(API_KEY)" $(PYTHON) -m evals.arm_probe $(ARGS)

# eval-generate: two-phase pipeline — generation pass (writes to evals/generations/<gen-id>/ or legacy transcript)
# Pass ARGS="--k 2 --gen-id smoke" to enable k-repeat output.
# Conservation identities 1 and 3 are checked after generation when GEN_ID is set (R1.3).
eval-generate:
	@echo "Running eval generation pass against $(BASE_URL) ..."
	$(PYTHON) -m evals generate \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--cases evals/cases \
		--fixture evals/cases/anti_hallucination_demo.json \
		--out evals/generations \
		--run-id latest \
		$(ARGS)
	$(if $(GEN_ID),$(PYTHON) scripts/check_conservation.py --gen-dir evals/generations/$(GEN_ID),)

# eval-judge: two-phase pipeline — judge pass (reads transcript written by eval-generate)
# Pass GEN_ID=<id> to also write evals/generations/<id>/judged.jsonl (EVAL-P1.6).
# Pass ARGS=--panel for the 3-model judge panel. $(ARGS) is forwarded because make
# accepts ARGS= whether or not the recipe expands it: without the line below,
# Run-EvalHarness.ps1's `ARGS=--panel` was silently dropped and every harness run
# single-judged while its own logs said panel (DEC-197). Pinned by
# tests/unit/scripts/test_makefile_arg_forwarding.py.
eval-judge:
	@echo "Running eval judge pass from transcript $(TRANSCRIPT) ..."
	$(PYTHON) -m evals judge \
		--transcript $(TRANSCRIPT) \
		--reports evals/reports \
		$(if $(GEN_ID),--json-out evals/generations/$(GEN_ID)/judged.jsonl,) \
		$(ARGS)

# eval-score: deterministic (no-LLM) scoring pass over a cached transcript.
# Usage: make eval-score TRANSCRIPT=evals/generations/<run>/outputs.jsonl
# Optional: add ARGS="--vocabulary evals/generations/<run>/vocabulary.json" to enable entity scoring.
eval-score:
	@echo "Scoring transcript $(TRANSCRIPT) with deterministic scorers (no LLM) ..."
	$(PYTHON) -m evals score \
		--transcript $(TRANSCRIPT) \
		--aliases evals/cases/entity_aliases.yaml \
		$(ARGS)

# eval-calibrate: per-scorer confusion matrices, Cohen's κ with bootstrap CI (EVAL-P5.4).
# Usage: make eval-calibrate [LABELS=evals/calibration/labels_v1.jsonl]
eval-calibrate:
	$(PYTHON) -m evals calibrate $(if $(LABELS),--file $(LABELS),)

# eval-adjudicate: resumable interactive adjudication of calibration labels (EVAL-P5.3).
# Usage: make eval-adjudicate [LABELS=evals/calibration/labels_v1.jsonl]
eval-adjudicate:
	$(PYTHON) -m evals adjudicate $(if $(LABELS),--file $(LABELS),)

# eval-replay-criteria: re-score selected calibration rows against a new criteria file,
# without a full judge pass (EVAL-P19.0b).
# Usage: make eval-replay-criteria CRITERIA=prompts/eval/refusal_judge.yaml SCORER=refusal_judge [RECORD_IDS=id1,id2] [LABELS=evals/calibration/labels_v1.jsonl]
eval-replay-criteria:
	$(PYTHON) -m evals replay-criteria \
		--criteria-file $(CRITERIA) \
		--scorer $(SCORER) \
		$(if $(RECORD_IDS),--record-ids $(RECORD_IDS),) \
		$(if $(LABELS),--labels-file $(LABELS),)

# eval-compare: McNemar paired comparison of two generation directories (EVAL-P8.2).
# Usage: make eval-compare BEFORE=<gen_id> AFTER=<gen_id>
eval-compare:
	@echo "Comparing $(BEFORE) vs $(AFTER) ..."
	$(PYTHON) -m evals compare \
		--before evals/generations/$(BEFORE) \
		--after evals/generations/$(AFTER)

# eval-deterministic-verdicts: replay every deterministic matcher to judged-format JSONL (no LLM).
# Required alongside eval-judge before label-import: judged.jsonl covers LLM-judge records only.
# Usage: make eval-deterministic-verdicts TRANSCRIPT=evals/generations/<id>/outputs.jsonl GEN_ID=<id>
eval-deterministic-verdicts:
	@echo "Replaying deterministic matchers from $(TRANSCRIPT) ..."
	$(PYTHON) -m evals deterministic-verdicts \
		--transcript $(TRANSCRIPT) \
		--json-out evals/generations/$(GEN_ID)/deterministic_judged.jsonl

# mock-calibrate: exercise export -> import -> adjudicate -> calibrate with RANDOM labels.
# Spends no Claude credits and produces a MEANINGLESS report — for pipeline testing only.
# Usage: make mock-calibrate GEN_ID=<id>
mock-calibrate:
	@echo "MOCK calibration dry run for $(GEN_ID) — results are random and meaningless."
	$(PYTHON) -m evals label-export \
		--transcript evals/generations/$(GEN_ID)/outputs.jsonl \
		--out-dir evals/calibration/batches
	$(PYTHON) -m evals deterministic-verdicts \
		--transcript evals/generations/$(GEN_ID)/outputs.jsonl \
		--json-out evals/generations/$(GEN_ID)/deterministic_judged.jsonl
	$(PYTHON) scripts/mock_labeller.py \
		--batches evals/calibration/batches \
		--out evals/calibration/mock_raw_labels.jsonl
	$(PYTHON) -m evals label-import \
		--raw evals/calibration/mock_raw_labels.jsonl \
		--transcript evals/generations/$(GEN_ID)/outputs.jsonl \
		--judged evals/generations/$(GEN_ID)/judged.jsonl \
		         evals/generations/$(GEN_ID)/deterministic_judged.jsonl \
		--model mock-random-v1 \
		--out evals/calibration/mock_labels.jsonl
	$(PYTHON) scripts/mock_adjudicate.py \
		--labels evals/calibration/mock_labels.jsonl \
		--out evals/calibration/mock_labels_adjudicated.jsonl
	$(PYTHON) -m evals calibrate --file evals/calibration/mock_labels_adjudicated.jsonl

# measure-reset-fidelity: measure what preconditions.reset_world actually clears (EVAL-P12.1).
# Requires the stack up and all three worlds seeded. Writes docs/RESET_FIDELITY.md and
# evals/reset_fidelity.json. The tier is derived from the evidence, never chosen: a report
# claiming FULL while anything survived cannot be constructed.
# Usage: make measure-reset-fidelity [REPEATS=5]
measure-reset-fidelity:
	$(PYTHON) e2e/scripts/measure_reset_fidelity.py \
		--base-url $(BASE_URL) --api-key $(API_KEY) \
		$(if $(REPEATS),--repeats $(REPEATS),)

# eval-sequence: run the 6 EVAL-P12.4 promoted multi-turn scenarios live and print
# the fidelity-conditional report. Requires the stack up, all three worlds seeded,
# and evals/reset_fidelity.json present (EVAL-P12.1). Wall-clock budget comes from
# EVAL-P12.1's measured per-reset cost: 6 scenarios x k x (turns + reset_cost).
# Usage: make eval-sequence [K=3]
eval-sequence:
	@echo "Running the 6 promoted multi-turn scenarios against $(BASE_URL) (k=$(or $(K),3)) ..."
	$(PYTHON) -m evals sequence \
		--base-url $(BASE_URL) --api-key "$(API_KEY)" \
		--k $(or $(K),3)

# mock-calibrate-oracle: exercise export -> import -> adjudicate -> calibrate with
# RULE-BASED labels whose confusion matrix is known BEFORE the run (EVAL-P15.1).
# Unlike mock-calibrate (random labels, kappa meaningless by construction), the
# numbers this prints are predictable in closed form, so any arithmetic error
# anywhere in the chain surfaces as a number mismatch rather than a silent pass.
#
# Defaults reproduce refusal_judge tp=60 fp=8 fn=4 tn=3 (n=75), which saturates
# that scorer's rows exactly: 68 scorer_verdict=True and 7 scorer_verdict=False.
# Expected kappa = 296/1196 = 0.247 to 3 dp — see tests/unit/evals/test_oracle_labeller.py.
# The naive tp=40 fp=5 fn=3 tn=12 needs 15 negatives and is unsatisfiable for
# EVERY scorer; the labeller raises UnsatisfiableMatrixError naming the caps.
#
# Never writes to the real labels file: --out is always under evals/calibration/oracle/,
# and evals/synthetic_label_guard.py refuses an oracle-* model aimed at labels_v1.jsonl.
# Usage: make mock-calibrate-oracle GEN_ID=<id> [SCORER=.. TP=.. FP=.. FN=.. TN=..] [MERGE=1]
mock-calibrate-oracle:
	@echo "ORACLE calibration for $(GEN_ID) — labels are synthetic; this measures the pipeline, not a scorer."
	$(PYTHON) -m evals label-export \
		--transcript evals/generations/$(GEN_ID)/outputs.jsonl \
		--out-dir evals/calibration/oracle_batches
	$(PYTHON) scripts/oracle_labeller.py \
		--batches evals/calibration/oracle_batches \
		--judged evals/generations/$(GEN_ID)/judged.jsonl \
		         evals/generations/$(GEN_ID)/deterministic_judged.jsonl \
		--scorer $(or $(SCORER),refusal_judge) \
		--tp $(or $(TP),60) --fp $(or $(FP),8) --fn $(or $(FN),4) --tn $(or $(TN),3) \
		--out evals/calibration/oracle/raw_labels_oracle.jsonl
	$(PYTHON) -m evals label-import \
		--raw evals/calibration/oracle/raw_labels_oracle.jsonl \
		--transcript evals/generations/$(GEN_ID)/outputs.jsonl \
		--judged evals/generations/$(GEN_ID)/judged.jsonl \
		         evals/generations/$(GEN_ID)/deterministic_judged.jsonl \
		--model oracle-matrix-v1 \
		--out evals/calibration/oracle/labels_oracle.jsonl \
		$(if $(MERGE),--merge,)
	$(PYTHON) scripts/oracle_adjudicate.py \
		--labels evals/calibration/oracle/labels_oracle.jsonl \
		--out evals/calibration/oracle/labels_oracle_adjudicated.jsonl
	$(PYTHON) -m evals calibrate --file evals/calibration/oracle/labels_oracle_adjudicated.jsonl

# label-export: export transcript records as JSON batches for the CLI labelling pass (EVAL-P5.6).
# Usage: make label-export TRANSCRIPT=evals/generations/<gen_id>/outputs.jsonl OUT_DIR=evals/calibration/export
label-export:
	$(PYTHON) -m evals label-export --transcript $(TRANSCRIPT) --out-dir $(OUT_DIR) \
		$(if $(VOCABULARY),--vocabulary $(VOCABULARY),) \
		$(if $(BATCH_SIZE),--batch-size $(BATCH_SIZE),)

# label-import: import a CLI labelling session into CalibrationLabel rows (EVAL-P5.6).
# Usage: make label-import RAW=<path> TRANSCRIPT=<outputs.jsonl> JUDGED=<judged.jsonl> [MERGE=1]
# Refuses to overwrite a labels file holding human verdicts. Pass MERGE=1 on every
# import after the first: it refreshes the machine-derived fields and keeps every
# human verdict, so re-judging after a criteria fix costs no relabelling.
label-import:
	$(PYTHON) -m evals label-import --raw $(RAW) --transcript $(TRANSCRIPT) --judged $(JUDGED) \
		$(if $(OUT),--out $(OUT),) \
		$(if $(MODEL),--model $(MODEL),) \
		$(if $(MERGE),--merge,) \
		$(if $(FORCE_OVERWRITE),--force-overwrite,)

# eval-combined: one command that runs dialogue evals + retrieval evals and prints both summaries
eval-combined: eval eval-retrieval

# draft-cases: generate draft capability cases from the live graph into evals/cases/_drafts/.
# Requires: running engine (make docker-compose up -d && make demo-seed).
# Usage: make draft-cases [NPC_IDS="npc_a npc_b"] [REQUIRES_WORLD=demo] [OVERWRITE=1]
draft-cases:
	$(PYTHON) -m evals draft-cases \
		--base-url $(BASE_URL) \
		--drafts-dir evals/cases/_drafts \
		--requires-world $(or $(REQUIRES_WORLD),demo) \
		$(if $(NPC_IDS),--npc-ids $(NPC_IDS),) \
		$(if $(OVERWRITE),--overwrite,)

# hedge-probe: score the capability battery against a scripted always-hedge responder
# (EVAL-P20.2 validation 2). Offline — no engine, no Neo4j; judges call Ollama only if a
# case declares one. Exits non-zero when the battery does NOT hold the hedge under 0.30.
# Usage: make hedge-probe [CASE_IDS="case_pos_a case_pos_b"]
hedge-probe:
	$(PYTHON) scripts/hedge_responder_probe.py \
		$(if $(CASE_IDS),--case-ids $(CASE_IDS),)

# seed-probe: measure byte-identical npc_response reproduction between two same-seed
# generation runs (EVAL-P20.0 / HUMAN GATE H4). Offline — reads two committed gen dirs.
# Exits 1 when rate_calls < 0.95, 2 when the two runs are not comparable.
# Usage: make seed-probe A=seedrepro_a_<sha> B=seedrepro_b_<sha>
seed-probe:
	$(PYTHON) scripts/seed_reproduction_probe.py --a $(A) --b $(B) \
		$(if $(JSON_OUT),--json-out $(JSON_OUT),)

# eval-harness: the single entry point (EVAL-P23.3). Preflight (services up, ollama
# panel models present, worlds seeded, tree clean) -> generate -> panel judge ->
# deterministic verdicts -> score -> calibrate -> compare -> record trend -> gate.
# Exit code is the verdict: 0 pass, 1 regression, 2 a precondition failed.
# Usage: make eval-harness ARGS=-DryRun   (prints the plan, exits 0, checks nothing)
#        make eval-harness ARGS="-K 3"
eval-harness:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/Run-EvalHarness.ps1 $(ARGS)

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

# eval-dashboard: the ENGINE-DEVELOPER eval dashboard (EVAL-P7) — run list, run detail
# with the headline card, per-case drill-down. Distinct from `dashboard` above, which is
# the designer-facing demo UI served by the engine on :8000. Reads artifacts off disk, so
# it needs no stack running.
# Usage: make eval-dashboard [ARGS="--port 8051"]
eval-dashboard:
	$(PYTHON) -m evals dashboard $(ARGS)

# hello: integrator hello-world — seed one NPC, send one dialogue turn, print reply
hello:
	$(PYTHON) -m demo_game.quickstart

# demo-seed: seed the demo world via the HTTP API (idempotent — safe to re-run)
demo-seed:
	$(PYTHON) -m demo_game.seeds.seed

# demo-run: play the scripted hackathon scenario (see docs/DEMO_SCRIPT.md)
# ARGS: --dry-run (no API calls), --cached (recording mode, error on miss)
demo-run:
	$(PYTHON) -m demo_game.runners.run $(ARGS)

# test-demo: run demo_game unit tests in isolation (separate from make test)
# Requires: pip install -r demo_game/requirements.txt
test-demo:
	$(PYTHON) -m pytest demo_game/tests/ -q

# demo-snapshot / demo-restore / eval-world-reset all need a raw bolt connection to
# Neo4j. neo4j has no host port mapping (EVAL-P20.3a / ISSUE-131) — Docker silently
# voids host port publishing for a service on an `internal: true` network only, so
# these run *inside* the app container instead, which shares that network.
# MSYS_NO_PATHCONV avoids Git Bash mangling the `/work` container path into a
# Windows path on Windows hosts; it is a no-op on Linux/Mac.

# demo-snapshot: export current Neo4j graph to .cache/demo/snapshot.json
# Run once before the demo to capture the clean seeded state.
demo-snapshot:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m demo_game.snapshot --mode snapshot --path /work/.cache/demo/snapshot.json

# eval-world-snapshot: capture the eval-world baseline WITH the derived-field strip.
# DEC-206 step 5 + DEC-211 Decision 3: `embedding`, `last_embedding_indexed_at`,
# `embedding_model` and `embedding_dim` are derived data the engine recomputes in
# seconds. Baking them in triples the fixture and couples a world fixture to whatever
# EMBEDDING_MODEL produced it. The strip used to be a script in a session-scoped temp
# directory; it is a flag now, so a clean checkout can regenerate the baseline.
eval-world-snapshot:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app 		python -m demo_game.snapshot --mode snapshot 			--path /work/evals/fixtures/eval_world_baseline.json --strip-derived

# demo-restore: wipe Neo4j graph and reimport from .cache/demo/snapshot.json
# Use between demo takes to reset the world to the snapshot state.
demo-restore:
	$(MAKE) --no-print-directory restore-with-app-stopped SNAPSHOT_PATH=/work/.cache/demo/snapshot.json

# eval-world-reset: wipe Neo4j and restore the checked-in clean eval-world baseline
# (demo + village + tavern, freshly seeded, none of the Quest/TickLease/Memory
# state that accumulates from eval runs). Closes ISSUE-167 (EVAL-P20.3a): this is
# what makes two generation runs comparable — both start from identical graph
# state. Run before any regeneration or repeated eval measurement.
eval-world-reset:
	$(MAKE) --no-print-directory restore-with-app-stopped SNAPSHOT_PATH=/work/evals/fixtures/eval_world_baseline.json

# restore-with-app-stopped: shared body of demo-restore and eval-world-reset.
# The engine's tick autopilot writes :WorldState every TICK_INTERVAL_SECONDS (10s), so a
# restore racing a running app used to leave the graph HALF-WIPED (ISSUE-188). The app is
# stopped for the duration here, matching what project-harness/Run-OvernightCombined.ps1
# already does; demo_game/restore_guard.py additionally refuses the restore if anything is
# still writing, so neither path can corrupt the graph. `docker compose run app` starts its
# own one-off container, so the restore works fine while the service is down. The app is
# always brought back up, even when the restore fails, and the restore's status is preserved.
restore-with-app-stopped:
	docker compose stop app
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m demo_game.snapshot --mode restore --path $(SNAPSHOT_PATH); \
	status=$$?; \
	docker compose up -d; \
	echo "[make] waiting for the engine to answer /health ..."; \
	healthy=0; \
	for i in $$(seq 1 60); do \
		if curl -sf http://localhost:8000/health >/dev/null 2>&1; then healthy=1; break; fi; \
		sleep 3; \
	done; \
	if [ $$healthy -eq 0 ]; then echo "[make] FATAL: engine did not answer /health within 180s."; exit 1; fi; \
	echo "[make] engine healthy."; \
	exit $$status


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
