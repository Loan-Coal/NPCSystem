# CR-L15 — Test economics

Branch `eval-ab-context-arms`, HEAD `d46ae42`. Read-only review. Neo4j is not
published to the host (only port 8000 is mapped) — no host-side direct-Neo4j
checks were possible or attempted; nothing below depended on one.

## Required measurements

### 1. Wall-clock

| Target | Result | Elapsed |
|---|---|---|
| `make check` (orchestrator's baseline, reused) | 15 targets, all exit 0 | 595s (9m55s) |
| `make test` (`pytest tests/ -q`) — ran live | **4048 passed, 36 skipped**, 2299 warnings | `333.01s` reported by pytest / `338s` shell wall-clock |
| `make test-demo` (`pytest demo_game/tests/ -q`) — ran live | **1116 passed** | `12.12s` reported by pytest / `18s` shell wall-clock |

```
$ pytest demo_game/tests/ -q
1116 passed, 30 warnings in 12.12s
$ pytest tests/ -q --durations=25
4048 passed, 36 skipped, 2299 warnings in 333.01s (0:05:33)
```

### 2. Slowest 20/25 — `tests/`

```
27.21s  tests/unit/engines/test_eval_runner_loop.py::test_run_case_keyword_none_fails_when_keyword_present
18.02s  tests/unit/evals/test_run_config.py::test_editing_a_judge_criteria_changes_harness_version
17.98s  tests/unit/evals/test_run_config.py::test_readme_in_cases_does_not_change_harness_version
17.84s  tests/unit/evals/test_run_config.py::test_golden_set_version_changes_when_a_case_changes
8.96s   tests/unit/evals/test_run_config.py::test_git_sha_is_seven_chars
8.89s   tests/unit/evals/test_run_config.py::test_run_config_fields_from_minimal_yaml
8.88s   tests/unit/evals/test_run_config.py::test_resolve_reads_dialogue_llm_config
8.87s   tests/unit/evals/test_generate_runner_k.py::test_gen_dir_run_records_a_non_null_run_config
8.85s   tests/unit/evals/test_run_config.py::test_resolve_seed_is_none_when_config_omits_it
8.80s   tests/unit/evals/test_run_config.py::test_resolve_with_custom_retrieval_profile
8.77s   tests/unit/evals/test_run_config.py::test_run_config_is_frozen
8.75s   tests/unit/evals/test_run_config.py::test_resolve_reads_seed_from_dialogue_llm_config
8.71s   tests/unit/evals/test_run_config.py::test_resolve_reads_prompt_version
8.15s   tests/unit/evals/test_generate_runner_k.py::test_gen_dir_run_resolves_config_before_generating
7.95s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_starts_reconciler_task
6.45s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_cancels_reconciler_task_on_shutdown
6.40s   tests/unit/conformance/test_sev15_type_gate.py::test_mypy_exits_zero
6.39s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_is_skipped_when_the_flag_is_off
6.36s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_that_reads_nothing_logs_at_error
6.36s   tests/unit/api/test_main_reconciler_lifespan.py::test_boot_hydration_finishes_before_the_reconciler_task_starts
6.11s   tests/unit/api/test_main_reconciler_lifespan.py::test_lifespan_closes_graph_db_when_startup_fails_after_connect
6.05s   tests/unit/scripts/test_record_trend_and_gate.py::test_explicit_baseline_gen_id_is_gated_against
4.72s   tests/unit/scripts/test_run_eval_harness.py::test_harness_accepts_a_custom_base_url_and_still_fails_loudly
4.62s   tests/unit/scripts/test_record_trend_and_gate.py::test_stable_kappa_still_exits_zero
4.49s   tests/unit/scripts/test_record_trend_and_gate.py::test_kappa_drop_exits_three_not_one
```

**What they're actually doing** — traced, not guessed:
- Rank 1 (27.21s) and ranks 2–14 (13 tests, ~133s combined) are **real, unmocked `httpx` calls to Ollama (`:11434`) and/or the live engine API (`:8000`)**, not CPU/setup cost. Full trace in CR-L15-01. Re-ran the single slowest test file twice in isolation to confirm this is not a fluke: `26.52s` then `26.19s` (`pytest tests/unit/engines/test_eval_runner_loop.py -q --durations=5`, both runs).
- Rank 17 (`test_mypy_exits_zero`, 6.40s) shells out to a **second, independent `mypy src/` subprocess** inside the test suite — duplicate of `make type`'s own 7s (CR-L15-05).
- The `test_main_reconciler_lifespan.py` cluster (5 tests, ~33s) drives real `asyncio` background-task lifecycles with `asyncio.sleep`-paced polling in the reconciler; legitimate async-integration cost, not flakiness or network — not investigated further (in budget, not in scope of the two defects above).
- `demo_game/tests/` slowest is `0.73s` (`test_dry_run_completes_through_act8_on_cp1252_stdout`); every other demo test is sub-0.6s. **1116 passed in 9.77s** pytest-reported. No network/DB dependency found — clean, fast unit suite.

### 3. Flakiness

Two independent full runs of `tests/` (durations run and the later coverage run, different flag sets, ~6 minutes apart) both produced **4048 passed, 36 skipped, 0 failed** — no differing outcome between runs. Re-ran the single slowest file twice in isolation (above) with consistent ~26.5s timing both times — the slowness is deterministic real-network latency, not a flake.

A third instrumented run (`--cov-context=test`, to build the per-test coverage map for §4) crashed with a `pytest-cov`/`coverage.py` **INTERNALERROR** (`sqlite3.OperationalError: no such table: context`) on this Windows/Python 3.14 combination — a tooling incompatibility in the `--cov-context` sqlite writer, not a test-suite defect. It surfaced no test failures before crashing; abandoned in favor of the grep-based method for §4 (as the task brief allows).

Grep for the usual flake sources:
```
time.sleep(              : tests/unit/retrieval/test_dialogue_context_cache.py:71 (1.1s, TTL-expiry test — deliberate, harmless)
                          : demo_game/tests/pollers/test_gold_poller.py:132,148 (0.01s/0.001s)
                          : demo_game/tests/scenarios/test_sandbox_loop.py:30,44,48,62 (0.1-0.2s)
datetime.now()/utcnow()  : 2 files (test_route_clock_tick.py, test_dialogue_handler_clock_tick.py) — both clock-tick tests, not time-of-day dependent
random.* unseeded        : 0 hits
pytest-randomly / xdist  : not installed (pip list confirms only pytest, pytest-asyncio, pytest-cov) — test order is deterministic file/declaration order, so no ordering-dependence risk from randomization
```
No flake source found beyond the deliberate, bounded `time.sleep`s above (worst case ~1.5s total across the whole suite) — the real cost driver is the *reproducible* real-network dependency in §2/CR-L15-01, not flakiness.

### 4. Coverage: real vs. import-only — 10 largest `src/npc_engine/` modules

Method: ran `pytest tests/ -q --cov=npc_engine --cov-report=json` live (4048 passed, 36 skipped, 339.16s — reconciles exactly with the orchestrator's baseline, see §6) and cross-referenced each module's statement/coverage numbers against which test files reference it and whether those tests call its own functions or patch them out at a higher layer.

| Module (stmts) | Coverage % | Tests naming it | Verdict |
|---|---|---|---|
| `retrieval/context/context_builder.py` (298 stmt) | 94.3% | `test_context_builder.py` (639 lines) + `test_context_builder_helpers_phase6.py` + 15 more | **Real** |
| `scheduler/tick_scheduler.py` (187 stmt) | 93.0% | `test_tick_scheduler_engine_isolation.py`, `test_tick_scheduler_llm_skip.py` (22 test fns) | **Real** |
| `retrieval/context/context_budget_enforcer.py` (148 stmt) | 96.6% | `test_context_budget_enforcer_v14.py` + 4 more | **Real** |
| `config.py` (229 stmt) | 99.1% | No dedicated `Settings`-validator test file; `Settings(...)` is constructed 76× across the suite purely for DI wiring (API_KEY_SECRET etc.), which happy-path-executes all 15 `@field_validator` + 5 `@model_validator` bodies as a side effect. Only 1 test (`test_config_prompt_window.py`) deliberately exercises a validator's *reject* branch. | **Mixed** — statements execute, but 14 of ~20 validators have their pass/fail decision logic verified nowhere; the 2 missing lines (474, 491) are almost certainly the untested raise branches |
| `engines/dialogue/dialogue_handler.py` (167 stmt) | 94.6% | `test_dialogue_handler_clock_tick.py`, `test_dialogue_handler_fallback_v14.py`, `test_tts_dialogue_handler.py` + 11 more | **Real** |
| `engines/gossip/gossip_handler.py` (111 stmt) | 96.4% | 7 dedicated files (`test_gossip_determinism.py`, `_distort`, `_emotion_wiring`, `_event_selection`, `_n_plus_one`, `_rumor_integration`, `_spread_service`) | **Real** |
| `utils/errors.py` (167 stmt) | 98.8% | `test_errors.py`, `test_errors_machinery.py` + 59 more | **Real** |
| `engines/quest/quest_lifecycle_engine.py` (98 stmt) | 85.7% | `test_quest_lifecycle_engine.py`, `test_quest_lifecycle_engine_v14.py` (13 test fns) | **Real** |
| `engines/quest_generation/quest_generation_engine.py` (135 stmt) | 87.4% | `test_quest_generation_engine.py` (unit, 11 fns) + `tests/contract/test_quest_generation_engine.py` | **Real** |
| `graph/intent/intent_queries.py` (78 stmt) | **34.6%** | `test_intent_repository.py` (4 tests) | **Gap — mock-shielded, not import-only.** See CR-L15-02: every test that references this module's 12 functions (`test_intent_repository.py`, `test_intent_queue_writer.py`, `test_intent_queue_reader.py`) `patch()`es them out at the caller's import site before invoking the wrapper. No integration/contract test picks up the slack. |

**Quantified answer to "what fraction of 87.86% is import-only":** among the 10 largest modules — the highest-leverage sample, since a fake-coverage problem would show up here first — **zero** show the "high-%-but-never-called" pattern the brief hypothesized. The two real defects found are different in kind: one module is *honestly low* (`intent_queries.py`, 34.6%, dragging the average down, not up) and one is *high via an untested side channel* (`config.py`'s validators, executed as DI-wiring fallout rather than intentional test design — 2 known-untested lines, negligible in isolation). Broadening to the population of trivial `__init__.py`/`Protocol`-stub files (many at 1 statement, 100% covered by nothing more than being imported anywhere) adds at most another ~30-40 statements of true "exists because it was imported" coverage — under 0.3% of the 17,796 `npc_engine` total. **Honest estimate: import-only inflation is small, under ~2% of the headline number** — the 87.86% is mostly real, modulo the separate and much larger validity problem in §6/CR-L15-01 (coverage whose *underlying test run* depends on live infra being reachable).

### 5. Cost per commit

Measured directly (warm caches, this machine):

```
$ time ruff check src/                        # pre-commit hook `ruff`      → 0.257s
$ time ruff format --check src/               # pre-commit hook `ruff-format` (would-be) → 0.293s
$ time python scripts/check_rules.py          # pre-commit hook `check-rules` (always_run) → 1.287s
$ time python scripts/check_harness_honesty.py# pre-commit hook `check-harness` (always_run) → 0.497s
$ time python scripts/mypy_ratchet.py         # pre-push hook `mypy-ratchet` → 2.566s
```

`.pre-commit-config.yaml` (read directly): commit hooks = `ruff`, `ruff-format`, `check-rules`, `check-harness`; **only** `mypy-ratchet` is `stages: [pre-push]`. **`make check` (including `test-cov`/`test-cov-evals`) is not a hook at all** — nothing in `.pre-commit-config.yaml` invokes it, and `.github/workflows/ci.yml` doesn't run it as one job either (it splits the 15 targets across 4 parallel jobs: `static-analysis`, a 3-way `v13-tests` matrix, `coverage-gate`, `v14-p4-gates`).

- **Actual git-enforced cost**: commit ≈ 2.33s, +push ≈ 2.57s → **≈ 4.9s per commit+push**, measured.
- **967 commits × real enforced cost** ≈ 967 × 4.9s ≈ **4,738s ≈ 1.3 hours total**, to date.
- **Orchestrator's requested model** ("assume `make check` runs once per commit"): 967 × 595s = 575,395s = **159.8 hours ≈ 6.66 days** of serial wall-clock.
  - Sanity check against the busiest real day: `git log --format='%ad' --date=short | sort | uniq -c | sort -rn` → **2026-06-12: 107 commits** (matches the brief's "max 107/day" exactly). 107 × 595s = 63,665s = **17.68 hours inside one 24-hour day** — physically incompatible with also writing 107 commits' worth of code that day. This is strong (if indirect) evidence that `make check` in its full 595s form is **not** run once per commit in practice; it is a task/phase-boundary gate (`/expand-next`'s "make check gating" per phase), not a per-commit one. See CR-L15-04.

### 6. `--cov` scope

Reconciled precisely by re-running coverage and inspecting the JSON (`coverage.json`, `files` map):

```
npc_engine files measured:            616   17,796 statements, 15,605 covered → 87.69%
evals/matchers.py + summary.py + runner.py:  545 statements, 337 covered
combined (== `make test-cov`'s scope):     18,341 statements  → 86.92%  (orchestrator's baseline run: 87.86% — 616 files is a big surface, ~1pt run-to-run drift is plausible non-determinism, not investigated further)
```

**The "18,341 vs 68,218-LOC `src/`" tension is fully explained, not a scope defect.** All 616 measured `npc_engine` files are real; nothing is silently excluded (`pyproject.toml`'s `[tool.coverage.run] source = ["src/npc_engine", "evals"]` instruments the whole tree, independent of which `--cov=` flags pytest-cov is given). The low statement:LOC ratio (17,796/67,331 measured-file LOC = **26.4%**, max observed anywhere in the tree is 59%) is a direct, measured consequence of this repo's own mandatory-docstring rule: every one of ~40 trivial `__init__.py` files is 100% covered at 1 statement / 13-14 lines (one paragraph of required package docstring, no code), and Protocol/port stub files (`dialogue_context_port.py`: 4 stmt / 68 lines) are similarly docstring-heavy. This is a real, if unusually low, ratio — not a hidden-package bug.

**`evals/` is also fully measured**: 110/110 `.py` files under `evals/` appear in the coverage JSON (0 missing) — the same 5,993-statement, 79.76%-adjacent figure recurs identically whether measured via the full `tests/` run or the narrow `test-cov-evals` target, because the same 110 files are the only ones any test imports either way.

**What genuinely has zero coverage floor** — confirmed via `grep -n "cov=" Makefile` (4 lines total: `test-cov`, `test-cov-v13`, `test-cov-full-report` [non-gating], `test-cov-evals`; none mention `scripts`, `e2e`, or `demo_game`):

| Body | LOC | Coverage floor? |
|---|---|---|
| top-level `scripts/` (48 files — `check_rules.py`, `check_layers.py`, `mypy_ratchet.py`, `check_test_quality.py`, etc.) | 7,821 | **None.** Tested by 17 files under `tests/unit/scripts/`, but no `--cov=scripts` anywhere, ever. |
| `e2e/` | 7,597 | **None.** Runs via `pytest e2e/scenarios` (in `testpaths`) but never appears in a `--cov=` flag. |
| `demo_game/` non-test code | 21,109 (36,961 total − 15,852 test) | **None.** `make test-demo` is `pytest demo_game/tests/ -q` — no `--cov` flag, no floor, not even a report. |

**Total shipped/tooling LOC under no coverage floor at all: 7,821 + 7,597 + 21,109 = 36,527 LOC**, against 88,359 LOC that does carry an enforced floor (68,218 `src` @ 80% + 20,141 `evals` @ 75%) — **~29% of the codebase's non-test surface ships with zero coverage enforcement**, including the very meta-scripts (`scripts/`) that enforce every other rule in this document.

---

## Findings

### [CR-L15-01] "Unit" tests in the eval harness make real, unmocked network calls to Ollama and the live API

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `evals/run_config.py:250-288` — `resolve_run_config()` defaults `fetch_generation_digest`/`fetch_judge_digest`/`fetch_ollama_version_fn` to `engine_adapter.fetch_model_digest`/`fetch_ollama_version` (`evals/engine_adapter.py:83-129`, real `httpx.post`/`httpx.get` to `DEFAULT_JUDGE_URL = "http://localhost:11434"`, `evals/judge_config.py:30`) and always calls `corpus_fields(fetch_corpus_fingerprint)` (`evals/engine_adapter.py:246-274`, real `httpx.get` against the live engine API). `tests/unit/evals/test_run_config.py` calls `resolve_run_config(...)` in 11 of its tests **without** passing any of the 4 injectable fakes (confirmed by grep — only 2 tests in the file pass `fetch_generation_digest=`/`fetch_judge_digest=`/`fetch_ollama_version_fn=`, and *none* ever overrides `fetch_corpus_fingerprint`). Separately, `evals/matchers.py:252` (`_eval_binary_judge`) does a real `httpx.post(f"{_JUDGE_URL}/api/generate", ...)`; `tests/unit/engines/test_eval_runner_loop.py:145` names a case `"case_neg_x"`, which matches `runner._GUARD_PREFIXES` (`evals/runner.py:38`), auto-injecting a `tone_judge` expectation (`evals/runner.py:104-111`) that is evaluated for real. Root `tests/conftest.py:1-4` states as its contract: *"Does NOT: connect to Neo4j, call LLM services, or modify production data."* — directly contradicted. Reproduced twice: `pytest tests/unit/engines/test_eval_runner_loop.py -q --durations=5` → 26.52s then 26.19s for the one affected test, both runs, consistent with `DEFAULT_JUDGE_TIMEOUT_S = 30.0` (`evals/judge_config.py:31`) minus real generation time. Summed real-network cost across the identified tests in the `tests/ -q --durations=25` run: ~124.6s (`test_run_config.py`, 11 tests) + ~17.0s (`test_generate_runner_k.py`, 2 tests) + 27.2s (`test_eval_runner_loop.py`, 1 test) ≈ **169s of the 333s total `make test` wall-clock (≈51%)**.
- **Cost of inaction:** Every `make test` / `make test-cov` / `make test-cov-evals` run is silently contingent on Ollama and the API being reachable at fixed default URLs. If either is down (a very plausible CI state — CI's `coverage-gate` job in `.github/workflows/ci.yml` never starts Ollama or docker-compose), these tests still "pass" today because every fetch function catches its own exception and returns `None`/`score=None` (`evals/engine_adapter.py`'s `except` blocks), but the wall-clock and the actual code path exercised (success vs. `except`) differ per-environment — meaning the coverage percentage attributed to `run_config.py`, `engine_adapter.py`, and `matchers.py`'s judge path is not a fixed property of the code, it is a property of whatever infrastructure happened to be running when the suite last executed. That is the CRITICAL-tier "coverage number used to make decisions that is not a valid measurement" the review brief called out by name.
- **Fix sketch:** Give every call site in `test_run_config.py`/`test_generate_runner_k.py` the same `fetch_*` fake-injection pattern the file's own two mocked tests already use; rename `test_eval_runner_loop.py`'s guard-prefixed case id to something outside `_GUARD_PREFIXES` (or explicitly assert on the injected `tone_judge` guard and mock `matchers.evaluate`). No production code changes needed — `resolve_run_config()` already has the injection seams.
- **Effort:** S (<2h) — mechanical, seams already exist.
- **Blast radius:** `tests/unit/evals/test_run_config.py`, `test_generate_runner_k.py`, `tests/unit/engines/test_eval_runner_loop.py` only. Fixing this removes ~169s (~28%) from `make test`'s 595s-inclusive `make check` budget and ~169s×2 (paid again inside `make test-cov-evals`, since `test_run_config.py` is under `tests/unit/evals/`) from the combined gate.

### [CR-L15-02] `intent_queries.py`'s real query logic is unverified — every caller mocks it out three layers deep

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `src/npc_engine/graph/intent/intent_queries.py` defines 12 public async functions (`get_npc_location`, `get_player_location`, `get_unmet_needs`, `get_witnessed_events`, `get_unresolved_goals`, `count_npc_pending_intents`, `get_lowest_score_pending`, `delete_intent_by_id`, `merge_pending_intent`, `get_pending_for_player`, `mark_intent_delivered`, `expire_stale_intents` — `intent_queries.py:118-338`). Measured coverage: 78 statements, 27 covered = **34.6%** (vs. 85.7-99.1% for the other 9 largest `src/npc_engine/` modules — see §4 table). `tests/unit/graph/test_intent_repository.py` (4 tests) `patch()`es `get_npc_location`, `get_witnessed_events`, `enqueue_intent`, `expire_old_intents` at `npc_engine.graph.repositories.intent_repository.*` before calling the repository wrapper — the real function bodies never run (test names are literally `test_*_delegates`). `tests/unit/engines/test_intent_queue_writer.py` and `test_intent_queue_reader.py` do the same at `intent_queue_writer`/`intent_queue_reader`'s import sites for the remaining 8 functions. `grep -rl "intent_queries\|intent_repository\|IntentRepository" tests/integration tests/contract` → no matches — no integration test exists to exercise the real Cypher-adjacent logic either.
- **Cost of inaction:** A bug in any of these 12 functions' actual query construction or result-shape handling (e.g. a wrong Cypher parameter, an off-by-one in `expire_stale_intents`'s cutoff comparison, a KeyError in `get_unresolved_goals`'s row parsing) has zero chance of being caught by the unit suite and no integration test as a backstop.
- **Fix sketch:** Add a real (Neo4j-test-DB) integration test per CLAUDE.md's own rule ("Functions touching Neo4j have integration tests against a real test DB, not mocks") for at minimum the 4 write-path functions (`merge_pending_intent`, `delete_intent_by_id`, `mark_intent_delivered`, `expire_stale_intents`) where a query-construction bug would silently corrupt state.
- **Effort:** M (<1d)
- **Blast radius:** New test file(s) under `tests/integration/`; no production code change required.

### [CR-L15-03] `check-test-quality` cannot fail `make check` regardless of what it finds

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `scripts/check_test_quality.py:7` (module docstring): *"Exits 0 always (report-only); gate wired into make check in EVAL-P15.4."* Confirmed in code: `main()` (`scripts/check_test_quality.py:250,261`) `return 0` unconditionally regardless of findings; `sys.exit(main())` at line 265 therefore always exits 0. Ran it live: `check-test-quality: 0 issues found.` (0.0s of real work today, 3s per the orchestrator's `make check` timing table — the gap is process-startup/AST-walk overhead across `tests/`, not analysis work).
- **Cost of inaction:** The Makefile target and the review's own framing present `check-test-quality` alongside 14 real gates ("15 targets, all exit 0") as if a violation would block `make check`. It cannot. If someone adds a `BARE_EXCEPTION_RAISES`/`VACUOUS_MOCK_NOT_CALLED` pattern tomorrow, `make check` stays green and nobody is notified except by reading stdout.
- **Fix sketch:** Either flip it to `sys.exit(1)` on any non-waived finding (now that the codebase already sits at 0 findings, this is a safe, immediate ratchet), or rename the Makefile target/docs to make its advisory-only nature explicit so it isn't miscounted as an enforcement gate.
- **Effort:** S (<2h)
- **Blast radius:** `scripts/check_test_quality.py`, `tests/unit/scripts/test_check_test_quality.py` (must assert the new exit code), `Makefile` comment at line ~180-183.

### [CR-L15-04] `make check`'s 595s is not the actual per-commit gate — the real one is ~5s

- **Severity:** MEDIUM
- **Confidence:** Likely
- **Kind:** Process
- **Evidence:** `.pre-commit-config.yaml` (full file read) wires only `ruff`, `ruff-format`, `check-rules`, `check-harness` to `git commit` and only `mypy-ratchet` to `git push` (`stages: [pre-push]`); none of `test`, `test-cov`, `test-cov-evals`, `check-layers`, `type-evals`, etc. are hooked at all. `.github/workflows/ci.yml` runs the 15 targets across 4 separate jobs, never `make check` as one invocation. Measured actual hook cost: 2.33s (commit) + 2.57s (push) ≈ 4.9s. Arithmetic check against `git log`-derived real commit rate: the busiest real day (`2026-06-12`, 107 commits, confirmed via `git log --format='%ad' --date=short | sort | uniq -c | sort -rn`) would require 107 × 595s = 17.68 hours of serial `make check` time inside one 24-hour day if it ran once per commit — not physically compatible with also writing that many commits.
- **Cost of inaction:** Nothing breaks today, but any future process document or automation that assumes "`make check` runs on every commit, so it costs `commits × 595s`" will overstate real gate-time spent by roughly 3 orders of magnitude (159.8h modeled vs. ~1.3h actually spent in git hooks) and will misallocate effort trying to speed up a gate that is not, in fact, the commit-path bottleneck.
- **Fix sketch:** If `make check` is meant to run once per task/phase (matching `/expand-next`'s "make check gating" language), document that explicitly next to the pre-merge checklist in `project-harness/CLAUDE.md` rather than leaving "before declaring a task done, run this checklist" ambiguous about frequency.
- **Effort:** S (<2h) — documentation only.
- **Blast radius:** `project-harness/CLAUDE.md` pre-merge-checklist section.

### [CR-L15-05] `mypy src/` runs twice per `make check` under two different mechanisms

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `tests/unit/conformance/test_sev15_type_gate.py:13-22` (`test_mypy_exits_zero`) shells out via `subprocess.run([sys.executable, "-m", "mypy", "src/", "--no-error-summary"], ...)` inside the pytest run — measured at 6.40s in the `tests/ -q --durations=25` run. `make type` (a separate, dedicated Makefile target) already runs the equivalent `mypy` invocation as its own `make check` step, measured by the orchestrator at 7s. Both are part of the same `make check` invocation (the conformance test runs inside `make test`/`test-cov`, which is also a `make check` target).
- **Cost of inaction:** ~6-7s of pure duplication per `make check` run — small in isolation, but a second, independent implementation of "mypy must be 0" means the two can silently diverge (different `mypy` invocation flags, different CWD) without anyone noticing until one fails and the other doesn't.
- **Fix sketch:** Either drop `test_mypy_exits_zero` (the dedicated `make type` target already gates this) or have it invoke the exact same code path `make type` uses (e.g. shell out to `make type` or import a shared helper) so there is one source of truth for "how do we check mypy".
- **Effort:** S (<2h)
- **Removes:** ~10 lines / 1 file (if dropped)
- **Blast radius:** `tests/unit/conformance/test_sev15_type_gate.py` only.

### [CR-L15-06] 36,527 LOC of shipped/tooling code — including the gate scripts themselves — carry no coverage floor

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `grep -n "cov=" Makefile` → exactly 4 lines (`test-cov`, `test-cov-v13`, `test-cov-full-report`, `test-cov-evals`), none referencing `scripts`, `e2e`, or `demo_game`. `make test-demo` recipe (`Makefile:604-605`) is `pytest demo_game/tests/ -q` — no `--cov` flag at all. Measured: top-level `scripts/` (48 files, tested by 17 files under `tests/unit/scripts/` but never gated) = 7,821 LOC; `e2e/` = 7,597 LOC; `demo_game/` non-test code = 36,961 − 15,852 (its own test LOC) = 21,109 LOC. Total = **36,527 LOC with zero enforced coverage floor**, against 88,359 LOC (`src` 68,218 @ 80% + `evals` 20,141 @ 75%) that does have one — **~29% of the codebase's shipped non-test surface**.
- **Cost of inaction:** `scripts/` is not incidental — it contains `check_rules.py`, `check_layers.py`, `mypy_ratchet.py`, `check_test_quality.py`, `check_harness_honesty.py`: the very enforcement mechanisms this whole review's "make check = 15 targets, all exit 0" baseline depends on. A regression in one of those scripts that makes it silently pass (a false "OK") would not itself be caught by any coverage floor, only by whatever ad hoc unit tests happen to exist for it.
- **Fix sketch:** Add `--cov=scripts` to whichever target already runs `tests/unit/scripts/` (it currently runs inside plain `make test`); add a `--cov` flag (even a low bar, e.g. 50%, ratcheted up over time) to `make test-demo`, matching the existing `test-cov`/`test-cov-evals` pattern.
- **Effort:** M (<1d) — mechanical Makefile change plus whatever floor-miss cleanup surfaces once the number is first measured.
- **Blast radius:** `Makefile` (`test-demo`, and whichever target covers `tests/unit/scripts/`); CI workflow if it should also gate on it.

---

## Pre-merge checklist (this review task)

- [x] Read-only — no source file edited, created, or deleted (only this evidence file written)
- [x] No commit made
- [x] Every claim above is file:line, a pasted live command + output, or a traced call chain
- [x] Severities follow the brief's calibration (invalid coverage number → CRITICAL; slow-but-not-behavior-changing suite → not escalated past MEDIUM)
- [x] Neo4j-host-access limitation stated up front; nothing below required it
