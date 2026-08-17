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
        type-ratchet type-ratchet-update type-evals type-evals-update check-harness \
        test-cov-evals \
        verify-v13 verify-v14-p0 verify-v14-p1 verify-v14-p2 verify-v14-p3 verify-v14-p4 verify-v14-p5 \
        eval eval-report eval-anti-hallucination eval-e2e eval-generate eval-judge eval-score eval-calibrate eval-adjudicate eval-retrieval eval-compare eval-deterministic-verdicts eval-replay-criteria eval-sequence eval-harness check-dead-keywords mock-calibrate mock-calibrate-oracle measure-reset-fidelity label-export label-import scenarios scenario-edge scenario-demo demo-video eval-llm eval-llm-demo eval-combined draft-cases hedge-probe seed-probe seed-api smoke \
        demo demo-seed demo-run demo-village demo-tavern test-demo dashboard \
        demo-snapshot demo-restore eval-world-reset \
        seed-tavern-world seed-village-world package

install:
	pip install -e .[dev]

# package: build the standalone npc_engine_server binary via PyInstaller (SHIP-04).
# Requires: pip install pyinstaller  (not in dev dependencies — build-time only).
# Output:   dist/npc_engine_server/npc_engine_server[.exe]
package:
	$(PYTHON) -m PyInstaller packaging/npc_engine.spec --distpath dist/npc_engine_server --workpath build/pyinstaller --noconfirm

run:
	uvicorn npc_engine.main:app --reload --reload-include="*.yaml" --reload-include="*.json"

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

# type-evals: ratchet mypy errors in evals/ (baseline 16 in .mypy_evals_baseline, EVAL-P15.4).
# Fails only when the error count grows above baseline.
type-evals:
	$(PYTHON) scripts/mypy_evals_ratchet.py

type-evals-update:
	$(PYTHON) scripts/mypy_evals_ratchet.py --update

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

# check-conservation: gate on conservation identity violations over the committed artifact.
# Exits non-zero when any identity fails (wired as a gate by EVAL-P17.6).
# Identity 4 is DEFERRED (spans two different artifact producers).
check-conservation:
	$(PYTHON) scripts/check_conservation.py

# check-dead-keywords: work-list of keyword_none terms with zero hits in the committed
# corpus (EVAL-P19.3). Informational only — always exits 0, never edits a case file.
# Deciding what a case should forbid is a human call (EVAL-P20.1).
check-dead-keywords:
	$(PYTHON) scripts/check_dead_keywords.py

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

# check: the single canonical health gate. Same command locally and in CI.
# mypy is at 0 (SEV-14 done) so 'type' is now a hard gate here.
# EVAL-P15.4 added: check-evals-rules type-evals check-test-quality test-cov-evals
# EVAL-P17.6 added: check-conservation (exits non-zero on any identity violation)
# EVAL-P20→P24 unblock plan Phase A1 added: check-label-survival
check: lint check-rules check-evals-rules check-layers check-docstrings type type-evals check-harness check-human-gates check-test-quality check-conservation check-label-survival test-cov test-cov-evals

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
eval-retrieval:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m evals retrieval

# eval-generate: two-phase pipeline — generation pass (writes to evals/generations/<gen-id>/ or legacy transcript)
# Pass ARGS="--k 2 --gen-id smoke" to enable k-repeat output.
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

# eval-judge: two-phase pipeline — judge pass (reads transcript written by eval-generate)
# Pass GEN_ID=<id> to also write evals/generations/<id>/judged.jsonl (EVAL-P1.6).
eval-judge:
	@echo "Running eval judge pass from transcript $(TRANSCRIPT) ..."
	$(PYTHON) -m evals judge \
		--transcript $(TRANSCRIPT) \
		--reports evals/reports \
		$(if $(GEN_ID),--json-out evals/generations/$(GEN_ID)/judged.jsonl,)

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

# demo-restore: wipe Neo4j graph and reimport from .cache/demo/snapshot.json
# Use between demo takes to reset the world to the snapshot state.
demo-restore:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m demo_game.snapshot --mode restore --path /work/.cache/demo/snapshot.json

# eval-world-reset: wipe Neo4j and restore the checked-in clean eval-world baseline
# (demo + village + tavern, freshly seeded, none of the Quest/TickLease/Memory
# state that accumulates from eval runs). Closes ISSUE-167 (EVAL-P20.3a): this is
# what makes two generation runs comparable — both start from identical graph
# state. Run before any regeneration or repeated eval measurement.
eval-world-reset:
	MSYS_NO_PATHCONV=1 docker compose run --rm -v "$$PWD:/work" -w /work app \
		python -m demo_game.snapshot --mode restore --path /work/evals/fixtures/eval_world_baseline.json

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
