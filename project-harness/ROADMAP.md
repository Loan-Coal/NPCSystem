# NPCSystem — Engine Roadmap

**Status:** Phases 0–26 complete; the EXP-201..230 expansion program **and** its slice-2 follow-up
(**Phases F/G/H — activate, surface, make-it-a-game**) are **fully shipped** (every F/G/H item checked;
only the two type-C deferrals H-D1/H-D2 + parked backlog remain). The architectural-remediation SEV backlog
(SEV-01..24, incl. the GraphRepository facade) is **fully drained** (47/47). `make check` GREEN.

**Next (as of 2026-08-02):** the active program is the **eval pipeline — `EVAL-P0..P8`** (see
*Active — Eval pipeline* below). ~20.1 h of coding, one phase per `/expand-next` session. Goal: turn the
existing scoring *harness* into a reproducible, repeat-aware, calibrated *pipeline* that can also answer
whether a given change improved the engine.

**Revised 2026-08-02 by adversarial review — 🔶 DEC-153 (ACCEPTED).** Ten findings applied: a
`DEC-149` id collision that falsely cleared EVAL-P5.2's ask-gate (now **DEC-152**), a wrong pinned Wilson
interval used as a test oracle, a loop fence wide enough to drain the whole program without ever measuring
anything, and the absence of any run-to-run comparison. **`compare` is promoted out of Parked to
Phase EVAL-P8**; the 18 h ceiling is lifted rather than silently overrun. Full rationale: DEC-153.

**Deferred (2026-07-31):** all game-client integration work — `SHIP-05b..11` and `Phase X` (Unity/Unreal
SDKs) — moved verbatim to **`project-harness/UNREAL_DEFERRED.md`**. Shipped engine-side runtime work
(`P0` / `SHIP-01..05a`, `INTEG-01..05`, Phases `F`/`G`/`H`) stays here. Engine choice for the LLM/graph
runtime remains **DEC-124** (dual LLM path; stay on Neo4j for now, copyleft revisit deferred via
`OD-Ship-graph`/`PERF-04`).

## Archive (completed history)

| Range | Where |
|-------|-------|
| Phases 0–13 (+ engine audit, session log → S13.3) | `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 (proactive dialogue, retrieval evals, moderation, API exit contract, arch-debt drain, runtime correctness, P3 sweep, eval fixtures, temporal framing, voice polish) + full session log | `project-harness/archive/ROADMAP_phase14-26_2026-06-11.md` |
| 2026-06-01 Munich hackathon roadmap | `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md` |
| 2026-06-03 codebase review (BLOCK, 43 findings) — remediation backlog, now drained across Phases 20–26 | `project-harness/archive/review-2026-06-03/` |
| EXP-201..230 expansion program (analysis + briefs + overnight loop driver) | `project-harness/archive/2026-06-18-shipped-programs/expansion/` |
| Phases F/G/H slice-2 (activate/surface/make-it-a-game) — driver + demo-expansion analysis | `project-harness/archive/2026-06-18-shipped-programs/DEMO_BUILD_LOOP.md`, `…/demo-expansion/`, `…/DEMO_GAME_EXPANSION_REVIEW.md` |
| 2026-06-13 full review (9-lens) + SEV-01..24 fix backlog (47/47 drained) | `project-harness/archive/2026-06-18-shipped-programs/REVIEW_FINDINGS.md`, `…/review-fixes/` |

---

## Active — Eval suite redesign (EVAL-B2..FINAL)

> **Approved plan (full detail, source of truth):** `~/.claude/plans/plan-the-full-implementation-glistening-parnas.md`.
> Goal of the program: make the eval suite measure the *engine*, not the harness — trustworthy,
> model-separated (judge ≠ generation), state-clean evaluation.
>
> **Already shipped (do not redo):**
> - **B-1 — model-separation invariant + judge consolidation (DEC-143).** `evals/judge_config.py`
>   (`resolve_judge_model`/`discover_generation_models`/`JudgeModelCollisionError`, default judge
>   `mixtral:8x7b`, exact-collision hard-fail + same-family warn); `matchers.py` wired; duplicated
>   `_make_judge`/`_ollama_reachable` consolidated into `e2e/helpers/judge_client.py`; both scenario
>   suites rewired. Tests: `tests/unit/engines/test_judge_config.py` + the mixtral tripwire in
>   `tests/unit/conformance/test_eval_matchers_sev38.py`. ✅
> - **B-2 production code — clean-state + precondition guard.** `evals/preconditions.py`
>   (`WorldBaseline`, `Preconditions`, `reset_world`, `ensure_player_node`, `assert_preconditions`,
>   `prepare`); `runner.py` ensures the player node per case + `--reset-world` flag;
>   `anti_hallucination_runner.run()` resets to age_of_peace; `clean_world` fixture in
>   `e2e/scenarios/conftest.py`; scenario tests 2/3 use it. Tests: `tests/unit/test_preconditions.py`,
>   `tests/unit/test_runner_player_node.py`. ✅ (commit 252a5fc)
>
> **Gate state going in: RED.** The B-2 `reset_world` call broke 8 `test_anti_hallucination_runner.py`
> cases (mock client returns a non-200 `.patch()`) — logged as **ISSUE-121**. EVAL-B2 below closes it.
>
> **Hard constraints (all phases):** `evals/` stays **src-free** (local exceptions, mirror `EvalConfigError`);
> judge prompts only in `prompts/eval/`; Pydantic v2 for any data crossing a boundary; ≤300 lines/file,
> ≤40 lines/function, ≤3 nesting; `make check` green per step. `test-cov` measures only
> `npc_engine + matchers + summary + runner` — new lines in those need same-phase tests; new standalone
> eval modules stay **out** of `--cov`.

### Phase EVAL-B2 — Finish clean-state guard (close ISSUE-121)
**Goal:** Restore the gate to green after the committed B-2 wiring. **Effort:** ~½ session.
**Constraint:** Do not weaken `reset_world`; fix the *tests* to model a real 200 PATCH.
**Notes:** B-2 production code already landed (252a5fc); only the unit tests lag. The 8 failures all live in
`tests/unit/engines/test_anti_hallucination_runner.py` and are caused by the mock client's `.patch()` not
returning `status_code == 200`, so `preconditions.reset_world` raises `PreconditionError`.

- [x] **EVAL-B2.1** Update `tests/unit/engines/test_anti_hallucination_runner.py` so the mocked client returns a 200 `.patch()` (or patches `anti_hallucination_runner.preconditions.reset_world`) — the 8 failing cases pass for the right reason. `make check` green. ✅ 2026-06-23
- [x] **EVAL-B2.2** Add a focused test asserting `run()` calls `preconditions.reset_world` once before the case loop (regression guard for the contamination fix), and confirm `runner.main` ensures the player node for a non-reputation case (already covered by `test_runner_player_node.py` — extend if gaps). Mark **ISSUE-121 `[FIXED]`** + move it to `archive/ISSUES_RESOLVED.md`. ✅ 2026-06-23

### Phase EVAL-B3 — LLM-judge refusal scorer (close ISSUE-119)
**Goal:** Replace the brittle keyword refusal match with the LLM judge so valid refusals are not scored as
hallucinations (and vice-versa). **Effort:** ~1 session. **Constraint:** judge transport stays in the
cov-measured `matchers.py`; refusal criterion lives only in `prompts/eval/`.
**Notes:** `anti_hallucination_runner._is_refusal` / `_REFUSAL_KEYWORDS` are the target. Re-measure the true
anti-hallucination number against the live engine after the swap (manual, not gated).

- [x] **EVAL-B3.1** Add `prompts/eval/refusal_judge.yaml` (header + `{criteria}`/`{content}`); add `matchers.judge_refusal(content) -> JudgeResult` (new `_REFUSAL_YAML_PATH` + loader mirroring the tone loader; reuse `_run_binary_judge`). Tests in `tests/unit/conformance/test_eval_matchers_sev38.py`: YES→score True, NO→False, infra→None; refusal prompt loaded. ✅ 2026-06-23
- [x] **EVAL-B3.2** Rewire `anti_hallucination_runner._classify_case` to use `matchers.judge_refusal` (delete `_REFUSAL_KEYWORDS`/`_is_refusal`; `score is None`→`error` outcome). Update the refusal tests in `test_anti_hallucination_runner.py` to patch `matchers.judge_refusal`. Mark **ISSUE-119 `[FIXED]`** + move to `archive/ISSUES_RESOLVED.md`. ✅ 2026-06-23

### Phase EVAL-B4 — Two-phase generate→judge, shared record model (DEC-144)
**Goal:** A generation pass collects all engine replies → persists structured records → a judge pass reads
and scores them; covers the case-based evals AND the scenario judge tests via one Pydantic v2 record model.
**Effort:** ~1–1.5 sessions. **Constraint:** purely additive (`make eval`/`make eval-anti-hallucination`
unchanged); new modules out of `--cov`; transcripts under `e2e/transcripts/` (gitignored).
**Notes:** Multi-step scenario tests (memory consolidation, gossip KNOWS_ABOUT count, planted rumor) do NOT
fit single-turn generate→judge — keep them as pytest but route through the shared `judge_client` +
`clean_world` and persist a record (`judge_kind=None` for the pure graph-count test). Add a `DECISIONS.md`
**DEC-144** entry for the two-phase architecture.

- [x] **EVAL-B4.1** `evals/eval_records.py` — Pydantic v2 `GenerationRecord` (incl. `judge_kind: Literal[...]|None`, `expected_polarity: Literal["pass_on_yes","pass_on_no"]`), `JudgedRecord`, `TranscriptFile`, `write_transcript`/`read_transcript`. Unit test: round-trip + schema-mismatch raises + polarity literal enforced. ✅ 2026-06-23
- [x] **EVAL-B4.2** `evals/generate_runner.py` (split a pure `generate_record_builder.py` if a function nears 40 lines): reuse `runner._load_cases`/`_expected_with_guards`; POST `/v1/dialogue` per LLM-judge expectation → `GenerationRecord` (affirms ⇒ `pass_on_no`); second loop emits anti-hallucination `refusal_judge` records; calls `ensure_player_node`. `make eval-generate` target. Unit test with mock client. ✅ 2026-06-23
- [x] **EVAL-B4.3** `evals/judge_runner.py`: `read_transcript` → `matchers._run_binary_judge` per record → apply polarity (None ⇒ inconclusive) → `JudgedRecord`; feed existing `summary.summarize`/`report.write_report` via a thin `_to_result_dict` adapter. `make eval-judge` target. Unit test (patch `_run_binary_judge`, assert polarity + summary headline). ✅ 2026-06-23
- [x] **EVAL-B4.4** Scenario record persistence: autouse `persist_scenario_records` fixture in conftest writes a session-collected `GenerationRecord` list at teardown; single-turn judge tests append records; multi-step tests append provenance records (gossip-count uses `judge_kind=None` + before/after metadata). Add **DEC-144**. ✅ 2026-06-23

### Phase EVAL-FINAL — Trustworthy re-run vs Stage-A baseline (manual, live)
**Goal:** Prove the redesign with real numbers, self-eval bias removed. **Effort:** ~½ session, **live** (engine
+ Ollama up). **Constraint:** not `make check`-gated (requires the running stack); record outputs in the
Session Log.
**Notes:** Stage-A baseline to beat — `make eval` 1/53 (missing player node) → 41/53 (after node);
anti-hallucination 27/40 via brittle scorer; scenarios self-evaluated on qwen2.5.

- [x] **EVAL-FINAL.1 — SUPERSEDED 2026-07-31 by `EVAL-P0.4`.** Not run as written. Its entire scope (live
  run of every eval target with both worlds seeded + a new-vs-Stage-A table) is absorbed into **EVAL-P0.4**
  below, which additionally instruments per-turn and per-judge-call timings. Running it separately would
  repeat ~90 minutes of live execution and produce no timing data. Original text preserved below.

  > **EVAL-FINAL.1 (original)** With both worlds seeded and `JUDGE_MODEL=mixtral:8x7b`: run `make eval --reset-world`, `make eval-anti-hallucination`, `make eval-generate` + `make eval-judge`, `make eval-llm`, `make eval-llm-demo`, and `retrieval_runner` in-container. Produce a **new-vs-Stage-A** table; confirm judge ≠ generation, player-node 422s gone, true anti-hallucination number re-measured. Re-judge one saved transcript with a second `JUDGE_MODEL` to demonstrate generate-once / judge-many. If the demo-world gossip-propagation failures persist, log a **new ISSUE** (next id 122) — do not fold into this program.

**Batching for `/expand-next`:** EVAL-B2 is a short close-out (one commit may suffice). EVAL-B3 is one session.
EVAL-B4 is its own session (4 steps, one commit each). EVAL-FINAL is superseded by EVAL-P0.4 below.

---

## Active — Eval pipeline (EVAL-P0..P7) ← **the current program**

<!-- LOOP:QUEUE start -->
<!-- Everything between these two markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside this fence — that is deliberate:
     19 open tasks elsewhere in this file (Phase PERF, Phase EVAL, two bullets inside
     "## Completed", Parked backlog, optional PR-9) must never be auto-started at 3am.
     To widen the queue later, move the `end` marker — never delete the fence.
     A task tagged ⏸️ is skipped even inside the fence.

     NARROWED 2026-08-02 (DEC-153 §3) to Phase EVAL-P0 only. Rationale: compute_next()
     SKIPS flagged tasks and never blocks on them, so with the fence open through P7 the
     loop would run P1..P7 while EVAL-P0.3 (ask-gate) and EVAL-P0.4 (live) sat unchecked
     forever. P0.4 is the measured baseline "every later estimate depends on" — the loop
     would have drained the entire program to all-boxes-checked without ever producing a
     single eval number, since every gate is `make check` with mocked I/O.
     REOPEN CONDITION: once EVAL-P0.3 and EVAL-P0.4 are both ticked by a human session,
     move this `end` marker down to just above "### Parked (out of budget)" to release
     P1..P8. Do not move it before then.

     REOPENED 2026-08-06 — the condition above FIRED and was executed. P0.4 (live baseline)
     and P0.3 (ask-gate, lint scope) were both ticked in human sessions on 2026-08-06, so the
     `end` marker now sits just above "### Parked (out of budget)" and the queue spans
     EVAL-P0..EVAL-P8. The narrowing did its job: the baseline exists (Session Log, 2026-08-06)
     before a single judge call was spent on P1..P8. The fence itself was NOT deleted — it
     still holds back the 19 open tasks elsewhere in this file. -->


> **Origin:** an externally-written proposal (`project-harness/npc_system_eval_plan_idea`) reviewed
> adversarially on 2026-07-31. The proposal was **not** adopted as written — its phase numbering,
> effort estimates and several load-bearing repo claims were wrong. This block is renumbered and
> re-timed from measurements taken against the codebase. **Do not consult the proposal for
> sequencing or estimates**; it is retained only for its methodology arguments.
>
> **Goal of the program:** turn the existing scoring *harness* into an eval *pipeline* — reproducible,
> repeat-aware, uncertainty-quantified, calibrated against adjudicated labels, and able to state whether
> one run is better than another.
>
> **Not in scope (DEC-153 §8):** this program measures **single-turn** quality. Cross-session memory
> retention, multi-turn coherence, and golden-transcript regression are the separate multi-turn program —
> see *Next+1 → Phase EVAL* below, which is rescoped rather than superseded.
>
> **Measured facts this program is planned against** (all commands run 2026-07-31):
>
> | Quantity | Value | How measured |
> |---|---|---|
> | YAML golden cases | **53** (not 56) | `ls evals/cases/*.yaml` |
> | — guard cases (`case_adv_`/`case_neg_`) | **37**, all `requires_world: demo` | parsed |
> | — world split | demo **49** · village **3** · tavern **1** | parsed `seed.requires_world` |
> | Anti-hallucination fixture cases | **41** (25 refusal / 16 grounded) | `anti_hallucination_demo.json` |
> | Retrieval labelled cases | **20**, each with `relevant_node_ids` | `retrieval_demo.json` |
> | Dialogue POSTs per full generation | **94** | 53 + 41 |
> | **Judge LLM calls per full run** | **115** | 8 declared tone + 8 declared affirms + 37 injected tone + 37 injected affirms + 25 refusal |
> | Tests in `tests/` | **2,637** (the proposal claimed ~951) | `pytest tests/ --collect-only` |
> | Stats libs installed | `numpy` only — `sklearn`/`scipy`/`statsmodels` **absent** | import probe |
> | `wilson\|kappa\|calibrat\|confusion\|human_verdict` in code | **0 hits** | grep |
> | `added_in\|retired_in\|golden_set_version` | **0 hits** | grep |
>
> **Refuted proposal claims — do not plan against these:**
> - *"k=15 full set ≈ 5 hours."* 15 × generation ≈ 5 h **alone**; judging adds 15 × 115 = **1,725
>   `mixtral:8x7b` calls** (~26 GB model, DEC-143). k=15 full-set is multi-day, not overnight.
> - *"Prompts externalised and versioned."* Three inconsistent, unreachable signals:
>   `prompt_builder.py:30 PROMPT_VERSION="stage_b_v2.13"` (a Python constant injected into the prompt
>   text at `:286`), `engines/dialogue/llm_config.yaml prompt.version: 1` (never bumped), and filename
>   `_v1` suffixes. Exactly **one** in-file `version:` key repo-wide. **`--prompt-version` has nothing
>   to switch on** — that is EVAL-P1.2, a hidden prerequisite.
> - *"The hard half (the scoring function) already exists."* `matchers.py` is 12 per-response boolean
>   matchers; `summary.py` computes counts, not rates. Nothing computes entity rate, knowledge boundary,
>   pass-rate-over-k, Wilson, κ, or a confusion matrix. The **harness** exists; the **scorers** are new.
> - *"The calibration labels already exist."* They do not. Zero hits, repo-wide.
>
> **Hard constraints (all phases):** `evals/` stays **src-free** behind exactly one sanctioned adapter
> (`evals/engine_adapter.py`, EVAL-P0.2). Note this is a **coupling-hygiene rule inside this program**:
> src-free is not engine-free (EVAL-P3 fetches vocabulary over the engine's HTTP API; EVAL-P1.1 reads
> engine YAML by path), and the extraction that would make the harness runnable by a stranger is a
> **post-program milestone**, not a phase here (DEC-153 §6 — see *Post-program milestones* below);
> judge prompts only in `prompts/eval/`;
> Pydantic v2 for any data crossing a boundary; ≤300 lines/file, ≤40 lines/function, ≤3 nesting;
> `make check` green per step. `test-cov` measures only `npc_engine + matchers + summary + runner` —
> edits to those three need same-phase tests to hold ≥80 %; new standalone eval modules stay **out** of `--cov`.
>
> **Effort budget: ~20.1 h of coding (DEC-153 §9).** The original 17.5 h/18 h framing was not credible —
> it excluded EVAL-P0.4's ~1.5 h wall clock, EVAL-P5's human adjudication, and EVAL-P6.1's recorded-fixture
> live run. The ceiling is therefore **lifted and restated honestly** rather than held and overrun:
>
> | Line | Cost |
> |---|---|
> | Original P0–P7 estimate | 17.5 h |
> | + EVAL-P8 (`compare` + paired stats, DEC-153 §4) | +1.5 h |
> | + EVAL-P4.0 (annotate 15 dialogue cases, DEC-153 §5) | +0.75 h |
> | + EVAL-P0.4 raw-verdict capture (DEC-153 §7) | +0.33 h |
> | **Coding total** | **~20.1 h** |
>
> **Non-coding costs, stated separately so they stop distorting the estimate:** ~1.5 h live wall clock
> (EVAL-P0.4) · ~4 h live wall clock (EVAL-P8's two test generations) · **4–6 h of maintainer adjudication**
> (EVAL-P5, 500 labels) — the single largest human cost in the program, and the one that cannot be bought.
> **EVAL-P7 (dashboard) remains the designated cut if a phase overruns**; EVAL-P8 is *not* a cut candidate —
> it carries the only statistic that answers "did this change help".
> Everything that did not fit is under `### Parked (out of budget)` at the end of this block.
>
> **New tests live in `tests/unit/evals/`** (mirror-source subdir per the PR-7 convention; needs an
> `__init__.py`). The five existing root-level eval tests are **not** moved — out of scope.

### Phase EVAL-P0 — Foundations: src-free repair, gated `evals/`, measured baseline
**Goal:** `evals/` genuinely honours the src-free constraint behind one named adapter and is covered by
lint; and a recorded live baseline replaces the proposal's unmeasured "20 minutes" with per-turn and
per-judge-call numbers that every later estimate depends on.
**Effort:** 2 h (+ ~1.5 h wall-clock background for the baseline run)
**Constraint:** No behaviour change to any existing scorer — `make eval` and `make eval-retrieval` output
must be byte-identical before and after EVAL-P0.2.
**Notes:** Absorbs **EVAL-FINAL.1** (already ticked as superseded above); do not run it separately.
`retrieval_runner.py` **already violates** the src-free rule this program is about to enforce — it imports
`npc_engine.graph.graph_reader` (`:104`), `npc_engine.config`, `npc_engine.graph.infra.db`,
`npc_engine.retrieval.embedding_index`, `npc_engine.retrieval.vector_store_factory` (`:238-241`). `evals/`
has **no `__init__.py`** and two incompatible entry conventions: flat imports (`import preconditions`, run as
`python evals/runner.py`, working only because `pyproject.toml` sets `pythonpath = [..., "evals"]`) versus
package imports (`from evals.retrieval_matchers import …`, run as `python -m evals.retrieval_runner`). Every
gate scopes to `src/` only (`scripts/check_rules.py:108`; `lint` = `ruff check src/`; `type` = `mypy src/`;
`rules_baseline.txt` has zero `evals/` entries) — so nothing in `evals/` is linted, typed or docstring-checked
today. **DEC-147 ✅ ACCEPTED 2026-07-31 (all five clauses, incl. §4 lint gate with the 30-min time-box).**

- [x] **EVAL-P0.1** Resolve the uncommitted generation-model drift and make the documented model authoritative.
      ✅ **2026-07-31 — 🔶 DEC-149 (ACCEPTED): all five engines on `qwen2.5:7b`**, `CLAUDE.md` authoritative.
      Answer to the ask-gate: **7b, fleet-wide** (not dialogue-only — a mixed fleet makes `RunConfig.generation_model`
      dishonest and `discover_generation_models()` multi-valued). Judge **unchanged** (`mixtral:8x7b`) so the
      EVAL-P0.4 baseline stays comparable to the Stage-A counts. Full stale-`14b` sweep done: `CLAUDE.md`,
      `README.md`, `docs/DEMO.md` (×4, plus the judge-model prerequisite it never documented), `docs/ENGINES.md`,
      `docs/ARCHITECTURE.md`, `CONTRIBUTING.md`, both `.env.example`s, `evals/judge_config.py` docstring.
      Measured-on-14b latency comments (`demo_game/constants.py`, `test_dialogue_ws_timeout.py`) were **annotated,
      not rewritten** — the 38 s figure is a real measurement and 7b is faster, so the bound stays conservative;
      EVAL-P0.4 re-measures. `model_tiers.py`'s `MODEL_14B` is a legitimate VRAM tier and was left alone.
      **Also fixed:** `e2e/scenarios/scenario_voice_from_graph.py` hardcoded a `qwen2.5:14b` judge default and
      built its own adapter, **bypassing the DEC-143 collision guard entirely** — now routed through
      `judge_client`. **Also found:** `OLLAMA_MODEL` is published in both `.env.example`s but read by zero code
      paths and named the *judge* model → **ISSUE-125**. `tests/unit/engines/test_judge_config.py::
      test_discover_generation_models_reads_real_configs` pinned the old `14b` state and was already red under
      the drift; updated to `7b`.
      **Follow-through — 🔶 DEC-150 (ACCEPTED), same session, before the P0.4 baseline:** the three findings
      above were closed rather than logged. (a) `OLLAMA_MODEL` **and** `LLM_BACKEND` — the only 2 of 55 keys
      absent from `config.py` — deleted from both `.env.example`s, completing `ISSUE-003` (fixed 2026-05-06),
      which had already removed both from `config.py` and simply missed the `.env.example` cleanup;
      **ISSUE-125 closed and archived** with a correction noting it under-described the problem as one key
      and as an open question. (b) `CONTRIBUTING.md`'s `LLM_BACKEND=mock` instruction has been **inert since
      ISSUE-003** — replaced with the working mechanism (`llm.backend: mock` in the five engine YAMLs,
      verified against `registered_backends()` and `EngineModelConfig`). (c) `tests/unit/evals/
      test_judge_bypass_guard.py` now enforces DEC-143 by AST scan; **validated against the pre-fix
      `scenario_voice_from_graph.py` from git, where it flags both halves of the real bypass at `:32` and
      `:39`.** `make check` green: 2,618 passed, 29 skipped, coverage 87.10 %.
      Files: `edit src/npc_engine/engines/dialogue/llm_config.yaml`, `edit project-harness/CLAUDE.md`,
      `create tests/unit/evals/__init__.py`, `create tests/unit/evals/test_model_identity.py`.
      RED anchor: `tests/unit/evals/test_model_identity.py::test_documented_generation_model_matches_config`
      fails because the model string in `CLAUDE.md` does not equal `llm.model` in `llm_config.yaml`.
      Validation: `git status` shows no unstaged `llm_config.yaml`; `judge_config.discover_generation_models()`
      returns exactly the model named in `CLAUDE.md`.
      ⚠️ **ask-gate:** changing the shipped generation model has engine-wide effect. `/expand-next` must
      **halt and ask which model is intended** before committing — do not guess from the working tree.

- [x] **EVAL-P0.2** Introduce the single sanctioned adapter and a guard that keeps every other module src-free.
      Files: `create evals/__init__.py`, `create evals/engine_adapter.py`, `edit evals/retrieval_runner.py`,
      `create tests/unit/evals/test_src_free.py`. Move the five `npc_engine` imports out of `retrieval_runner`
      into `engine_adapter.build_retrieval_stack()` / `engine_adapter.known_event_ids(session, npc_id)`.
      RED anchor: `tests/unit/evals/test_src_free.py::test_only_engine_adapter_imports_npc_engine` fails
      because `retrieval_runner` still names `npc_engine`.
      Validation: the guard AST-scans every `evals/*.py`, permits `npc_engine` imports **only** in
      `engine_adapter.py`, and reports the other 12 modules clean; `make eval-retrieval` prints an identical
      table to the pre-change run. ✅ AUTO (EVAL-P0.2, 2026-08-05)

- [x] **EVAL-P0.3** Bring `evals/` under the lint gate. Files: `edit Makefile` (`lint: ruff check src/ evals/`),
      plus the ruff fixes it demands, `create tests/unit/evals/test_gate_scope.py`.
      RED anchor: `tests/unit/evals/test_gate_scope.py::test_lint_target_covers_evals` fails because the
      `lint` recipe names only `src/`.
      Validation: `make lint` exits 0 with `evals/` in scope; `make check` green.
      **Time-box 30 min.** If ruff surfaces more than ~20 violations, fix the mechanical ones, add the rest to
      a new `# evals/` section of `scripts/rules_baseline.txt`, and log the remainder as an ISSUE — do not let
      this phase become a cleanup sweep. mypy + docstring coverage for `evals/` is **Parked**.
      ⚠️ **ask-gate:** edits the shared `make check` health gate.
      ✅ **DONE 2026-08-06** (human session; ask-gate answered: approve `src/ evals/`, fix the import, static
      Makefile parse for the test). **The 13 `evals/` modules carried exactly ONE ruff violation** — `E402` at
      `retrieval_runner.py:39`, a `from pydantic import BaseModel` stranded below a comment banner; moved into
      the third-party import group. Nothing was added to `scripts/rules_baseline.txt` and **no deferred ISSUE
      was needed** — the ~20-violation escape hatch never came near firing. This retires the "unbounded until
      EVAL-P0.3's ruff pass reveals the true violation count" blocker on the Parked
      *`evals/` under `mypy` + `check-docstrings`* line: **the true ruff count is 1**; mypy/docstring counts
      remain unmeasured and that item stays Parked. `tests/unit/evals/test_gate_scope.py` (6 tests) now parses
      the Makefile statically and fails if the `lint` recipe ever loses `evals/` or `check` stops depending on
      `lint`. Also re-snapshotted `test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire`, which was
      **already red at HEAD** (it asserted `pending == 1` while both remaining P0 tasks are flagged, so
      `pending` was `[]`) — see the fence move below.

- [x] **EVAL-P0.4** *(live; not `make check`-gated — requires engine + Neo4j + Ollama up)* Measured baseline.
      ✅ **DONE 2026-08-06** — see [Session Log — EVAL-P0.4](#session-log--eval-p04-measured-baseline-2026-08-06) below the fence.
      With **all three** worlds seeded (`make demo-seed`, `make seed-village-world`, `make seed-tavern-world` —
      required, or 4 of 53 cases silently skip) and `JUDGE_MODEL=mixtral:8x7b`: run
      `python evals/runner.py --reset-world --base-url … --api-key …` (the `eval` target passes no `ARGS`, so
      `--reset-world` must be invoked directly), then `make eval-anti-hallucination`, `make eval-generate` +
      `make eval-judge`, `make eval-retrieval`.
      Files: `edit project-harness/ROADMAP.md` (Session Log), `create evals/generations/baseline/verdicts.json`.
      Validation: a Session Log table stating (a) measured **seconds per dialogue turn**, (b) measured
      **seconds per `mixtral` judge call**, (c) the implied wall-clock for k=3 and k=15 over the full set,
      computed from (a) and (b) — this is the number that replaces the proposal's "20 minutes", (d) pass counts
      against the Stage-A baseline (`make eval` 41/53; anti-hallucination 27/40), (e) how many cases **skipped**.
      Re-judge one saved transcript with a second `JUDGE_MODEL` to demonstrate generate-once / judge-many.
      **(f) Raw per-case verdicts, not just counts (DEC-153 §7).** Persist the full
      `{case_id: {passed, skipped, expectations: [...]}}` list to `evals/generations/baseline/verdicts.json`.
      Three different headline denominators appear across this program — 53 total → 49 `evaluated_cases`
      (EVAL-P2.3) → 74 vs 37 guard turns (EVAL-P6.2) — and the Stage-A figures are counts only, so they can
      never be restated. Capturing verdicts makes every later denominator change a recomputation instead of
      an orphaned baseline. **(g) Freeze the canonical denominator here**, in the Session Log, as
      **`evaluated_cases` (skipped excluded) + case-level guard turns**, and quote it in every later headline.
      **Note the Stage-A anti-hallucination figure is quoted as `27/40` but the fixture holds 41 cases**
      (25 refusal / 16 grounded, verified) — state the corrected denominator when recording the comparison.
      ⚠️ **This task and EVAL-P0.3 gate the loop fence.** Both must be ticked before the queue-fence end
      marker may be moved down to release EVAL-P1..P8. (The literal marker token is deliberately not repeated
      here — a second copy between the two real markers would truncate the parsed queue.)

<!-- ^ The `end` marker stood here from 2026-08-02 (DEC-153 §3) until 2026-08-06, holding the
     queue to Phase EVAL-P0 alone so the loop could not drain P1..P8 before a human ran the
     live baseline. Both gating tasks are now ticked (P0.4 on 2026-08-06, P0.3 the same day),
     so the reopen condition fired and the marker moved down to just above
     "### Parked (out of budget)". The Session Log below now sits *inside* the fence — it is
     prose, carries no `- [ ]` task bullets, and is therefore invisible to the cursor's
     grammar; it does widen `--slice EVAL-P0` output, which no longer matters now that
     EVAL-P0 is complete. -->

## Session Log — EVAL-P0.4 measured baseline (2026-08-06)

**Stack:** engine + Neo4j (docker-compose) + Ollama on one workstation — RTX 5070 Ti Laptop
(12 GB VRAM), 93.7 GB RAM. Generation `qwen2.5:7b`, judge `mixtral:8x7b` (27 GB, runs
63% CPU / 37% GPU — does **not** fit in VRAM). All three worlds seeded before the run
(`demo` created=101 skipped=71, `village` created=42 skipped=14, `tavern` created=26 skipped=10),
so **0 of 53 cases skipped** in the YAML suite.

### (a)–(c) Timing — the numbers that replace the proposal's "20 minutes"

| Phase | Wall clock | Unit work | **Measured rate** |
|---|---|---|---|
| `eval-generate` (qwen only, no model swap) | 278.6 s | 78 dialogue POSTs | **(a) 3.57 s / dialogue turn** |
| `eval-judge` (mixtral only, no model swap) | 969.1 s | 115 judged records | **(b) 8.43 s / mixtral judge call** |
| `runner.py --reset-world` (inline, interleaved) | 1789.6 s | 53 turns + 90 judge calls | 33.8 s / case |
| `anti_hallucination_runner.py` | 860.0 s | 40 evaluated cases | 21.5 s / case |
| `retrieval_runner` (in-container) | 37.7 s | 20 cases | 1.9 s / case |

**(c) Implied wall-clock over the full set**, from (a) and (b):

```
wall_clock(k) = k × (78 × 3.57 s  +  115 × 8.43 s) = k × 1247.6 s = k × 20.8 min
```

| k | Implied wall clock |
|---|---|
| k=1 | 20.8 min |
| **k=3** | **62.4 min (1.04 h)** |
| **k=15** | **5.20 h** |

The proposal's "20 minutes" is almost exactly **k=1**, not the full set. For j judge models
over one generation set (generate-once / judge-many): `k × 78 × 3.57 + k × j × 115 × 8.43`.

**Two-phase is worth 47% of wall clock on this hardware.** `runner.py` interleaves a qwen turn
with mixtral judge calls, and the two models cannot co-reside in 12 GB VRAM — a single dialogue
turn evicts mixtral (verified with `ollama ps`). Predicted inline cost at the clean rates is
53 × 3.57 + 90 × 8.43 = **947.6 s**; actual was **1789.6 s**. The **842 s (47.0%) delta is pure
model-swap overhead.** Reload penalty measured directly: 22.8 s cold vs 7.1 s warm. This also
explains the first attempt's `binary_judge_infra_failure` flood — the default 30 s judge timeout
is shorter than a cold 27 GB load. Live runs need `JUDGE_TIMEOUT_SECONDS=300` + a mixtral
prewarm; infra failures return `score=None` (inconclusive), so an unprewarmed run yields a
silently worthless baseline, not a failing one.

### (d) Pass counts vs the Stage-A baseline

| Suite | Stage-A | **This run** | Delta |
|---|---|---|---|
| `runner.py` (YAML cases) | 41/53 | **47/53** | **+6** |
| anti-hallucination | "27/40" | **35/40 evaluated** | **+8** (see denominator note) |
| two-phase judge, `mixtral:8x7b` | — | 110/115 records | new |
| two-phase judge, `qwen2.5:14b` | — | 110/115 records | new |
| retrieval | — | P@k 0.278 · R@k 0.625 · MRR 0.417 (20 cases) | new |

**Denominator correction (as required):** the Stage-A anti-hallucination figure is quoted as
`27/40`, but the fixture holds **41 cases** (25 refusal / 16 grounded, verified by loading it).
This run evaluated **40** of those 41 (1 skipped), so `35/40` and `27/40` share a denominator
only by coincidence. Breakdown this run: grounded **11/15** (4 over-refusals), refusal **24/25**
(1 hallucination).

Stage-A's 41/53 also folded skipped cases into the numerator — both runners report a skipped
case as `passed=True`. This run had 0 skips in the YAML suite, so 47/53 is unaffected, but the
comparison is only clean because of that.

### (e) Skipped cases

| Suite | Skipped |
|---|---|
| `runner.py` | **0** of 53 (all three worlds seeded) |
| anti-hallucination | **1** of 41 — `ah_demo_mira_player_taught` |
| two-phase judge | 0 of 115 |
| retrieval | 0 of 20 |

The one skip is the `learned_from_player` belief pre-flight (ISSUE-090 / DEC-095), not a missing
NPC — the console message "SKIP (NPC not found)" is misleading (ISSUE-130).

### (f) Raw per-case verdicts (DEC-153 §7)

| Artifact | Contents |
|---|---|
| `evals/generations/baseline/verdicts.json` | 53 cases · evaluated 53 · passed 47 · skipped 0 |
| `evals/generations/baseline/verdicts_ah.json` | 41 cases · evaluated 40 · passed 35 · skipped 1 |

Both carry `{case_id: {passed, skipped, description, expectations:[{kind, passed, skipped, detail}]}}`
plus a `totals` block that separates `passed_cases_raw` (skips counted as passes, the Stage-A
reading) from `passed_evaluated`. Written by the new `--json-out` flag on both runners
(`evals/verdicts.py`, added by this task — nothing in `evals/` emitted JSON before).

Not persisted: the 115 **record-level** judge verdicts (`judge_runner` has no `--json-out`).
Given the judge disagreement in the next section, that gap matters — EVAL-P1's transcript
schema v2 is the natural home for it.

### (g) Canonical denominator — FROZEN HERE

> **`evaluated_cases` (skipped excluded) + case-level guard turns.**
> For this baseline: **53 evaluated cases, 37 case-level guard turns** (YAML suite);
> **40 evaluated cases** (anti-hallucination fixture, 41 total − 1 skipped).
> Every later headline quotes this pair and states which one it is using.

⚠️ **Case-level guard turns (37) and record-level guard turns (82) are different numbers.**
The judge pass reports "82 adversarial turns" because it counts one record per judge
*expectation*, not per case. The two must never be swapped in a published figure. This is
the drift EVAL-P6.2 anticipated (74 vs 37) — measured here as **82 vs 37**.

### Generate-once / judge-many — demonstrated, and it flipped the headline

The same transcript (`e2e/transcripts/eval_generation_latest.json`, 115 records) was judged
twice with zero regeneration cost:

| Judge | Passed | tone_judge fails | affirms_judge fails | other | Published headline |
|---|---|---|---|---|---|
| `mixtral:8x7b` | 110/115 | 3 | **1** | 1 | "**1** lore hallucination across 82 adversarial turns" |
| `qwen2.5:14b` | 110/115 | 3 | **0** | 2 | "**0** lore hallucinations across 82 adversarial turns" |

Identical pass counts, different verdicts on individual records — and the anti-hallucination
guarantee, the program's headline claim, **depends on which judge is asked**. `qwen2.5:14b`
correctly logged `judge_same_family_as_generation` (allowed, not a collision, per DEC-143).
Logged as ISSUE-129; this is the strongest argument in the program for a judge panel rather
than a single judge.

### Failures worth reading, not just counting

- **1 real hallucination** — `case_neg_captain_sorn_no_troop_specifics`: the NPC invented a
  warlord named "bjorn". Genuine engine defect (ISSUE-128).
- **1 judge false positive** — `case_neg_injection_001`: mixtral failed it claiming the NPC
  "explicitly claims to be an AI by saying 'I am Captain Sorn'". It did not; it stayed in
  character and refused. One of the 6 failures is the scorer's error, not the engine's
  (ISSUE-129).
- **4 over-refusals** in the anti-hallucination grounded set (11/15) — NPCs refusing facts
  they hold in the graph.
- Remaining 4 YAML failures: `case_002_suspicious_guard` (tone), `case_voice_captain_sorn_001`
  (tone — voice too hedged for a guard captain), `case_pos_mira_war_gossip_tokens` and
  `reputation_dialogue_tone_001` (both `keyword_any` token-list misses).

### Harness defects fixed to make this run possible

| Defect | Fix |
|---|---|
| `make demo-seed` broken since PR-5 (`-m demo_game.seed`, module moved to `demo_game.seeds.seed`) | Makefile target corrected; missing gate logged as ISSUE-127 |
| No JSON verdict output anywhere in `evals/` | `evals/verdicts.py` + `--json-out` on both runners (6 unit tests) |
| `binary_judge_infra_failure` logged the cause via `extra={}`, which the default formatter drops | now logs model, timeout and exception; conformance test asserts the cause survives |
| `retrieval_runner` error handler raised `NameError: settings` (EVAL-P0.2 leftover; ruff F821 would catch it — see EVAL-P0.3) | `engine_adapter.neo4j_uri()` |
| `make eval-retrieval` unrunnable from the host | compose publishes neo4j's 7687 but the `internal: true` network silently voids it (ISSUE-131). Ran via `docker compose run --rm -v "$PWD:/work" -w /work app python -m evals.retrieval_runner` |

**Total live execution: ~1.4 h** (1789.6 + 860.0 + 278.6 + 969.1 + ~969 untimed qwen re-judge + 37.7 s).

### Phase EVAL-P1 — Transcript schema v2: reproducible run identity
**Goal:** A generation artifact a stranger can reproduce from — exact config, k repeats, git SHA, golden-set
version, per-turn timing, and the retrieved context that produced each reply.
**Effort:** 3 h · **running total: 5.33 h**
**Constraint:** Hard break to `version: 2`; `read_transcript` rejects v1 loudly. Nothing to migrate —
`e2e/transcripts/` is gitignored and no v1 artifact is tracked anywhere. `TranscriptFile` and
`GenerationRecord` stay `frozen=True`.
**Notes:** **DEC-146 ✅ ACCEPTED 2026-07-31 (hard break, no v1 reader; `seed` stays absent).** **`seed` must NOT appear in the config block** — `LLMGenerateProtocol.generate()`
(`engines/llm/protocols.py`) has no `seed` parameter and `ollama_adapter.py` never sets `options.seed`; claiming
it would be dishonest. Adding it is a Protocol change across three adapters → **Parked**. `model`/`temperature`/
`top_p`/`max_tokens` **are** honest: read them as *files* from `src/npc_engine/engines/*/llm_config.yaml`, the
exact precedent `judge_config.py:87` already sets — reading a YAML file is not a src import. Retrieved context
comes from `GET /v1/admin/debug/retrieval`, which **re-runs** retrieval with `session_turns=[]` and flattens
tier/priority to sentinels (`admin/debug_retrieval.py:80-108`) — it is an *approximation* of the context that
produced the reply, and that caveat goes in the schema docstring verbatim, not in a backlog. **Depends on:**
EVAL-P0.2 (`evals/__init__.py` must exist). **Blocks:** EVAL-P2, EVAL-P3, EVAL-P4, EVAL-P7.

- [x] **EVAL-P1.1** Run-config model. Files: `create evals/run_config.py`, `create tests/unit/evals/test_run_config.py`.
      Frozen Pydantic v2 `RunConfig`: `prompt_version`, `generation_model`, `temperature`, `top_p`, `max_tokens`,
      `judge_model`, `retrieval_profile`, `git_sha`, `golden_set_version`. `resolve_run_config()` reads the engine
      YAML + `git rev-parse --short HEAD` + `judge_config.resolve_judge_model()`.
      RED anchor: `tests/unit/evals/test_run_config.py::test_resolve_reads_dialogue_llm_config` fails — module absent.
      Validation: `python -c "from run_config import resolve_run_config as r; print(r().model_dump_json(indent=2))"`
      prints a block with a non-empty 7-char `git_sha` and a `generation_model` equal to `llm_config.yaml`'s.
      **No `seed` field exists on the model** — assert its absence in the test. ✅ AUTO (EVAL-P1.1, 2026-08-06)

- [x] **EVAL-P1.2** Single-source the prompt version (the hidden prerequisite). Make `llm_config.yaml`'s
      `prompt.version` authoritative and have `prompt_builder` read it instead of hardcoding.
      Files: `edit src/npc_engine/engines/dialogue/prompt_builder.py`, `edit src/npc_engine/engines/dialogue/llm_config.yaml`,
      `create tests/unit/conformance/test_prompt_version_single_source.py`, `edit tests/unit/engines/test_prompt_builder.py`.
      RED anchor: `tests/unit/conformance/test_prompt_version_single_source.py::test_prompt_version_matches_llm_config`
      fails because `PROMPT_VERSION = "stage_b_v2.13"` (`prompt_builder.py:30`) ≠ `prompt.version: 1`.
      Validation: editing `prompt.version` in the YAML changes what `resolve_run_config().prompt_version` returns
      **with no Python edit**, and the existing `test_prompt_builder.py:138` assertion still passes.
      **Approach chosen 2026-08-07 (human decision): YAML authoritative, module-level read.** Set
      `prompt.version: stage_b_v2.13` in `llm_config.yaml`, then make `prompt_builder.py:30` read it:
      `PROMPT_VERSION = str(_CFG["prompt"]["version"])`. Assert the value is a non-empty string at read
      time, so a YAML typo fails loudly at import instead of silently injecting an empty version into
      every prompt. `run_config.py:143` already reads the same key and needs no change.
      *No human decision is pending on this task.* `PROMPT_VERSION` has no callers outside its own module
      except that one test (verified by grep, `demo_game/constants.py` uses a separate `DEMO_CACHE_VERSION`).
      WARNING: the sentence that used to sit here contained the literal token the cursor's skip-regex
      matches, so this task was flagged and skipped for the entire program despite the sentence saying the
      opposite. Reworded 2026-08-07; root cause logged as **ISSUE-134**. ✅ AUTO (EVAL-P1.2, 2026-08-07)

- [x] **EVAL-P1.3** Schema v2. Files: `edit evals/eval_records.py`, `create evals/retrieved_item.py`,
      `create tests/unit/evals/test_eval_records_v2.py`. `_TRANSCRIPT_VERSION = 2`; `TranscriptFile` gains
      `gen_id`, `k`, `config: RunConfig`; `GenerationRecord` gains `repetition: int`, `duration_ms: int`,
      `retrieved_context: tuple[RetrievedItem, ...]`; `read_transcript` raises a new `TranscriptVersionError`
      on `version != 2`.
      RED anchor: `tests/unit/evals/test_eval_records_v2.py::test_read_transcript_rejects_v1` fails because
      `read_transcript` currently accepts any version.
      Validation: v2 round-trip passes; a hand-written v1 JSON raises `TranscriptVersionError` naming both versions.
      **Size watch:** `eval_records.py` is 136 L today — split `RetrievedItem` into its own module *before* writing,
      per the 300-line rule. ✅ AUTO (EVAL-P1.3, 2026-08-06)

- [x] **EVAL-P1.4** `--k`, `--gen-id`, and retrieved-context capture. Files: `edit evals/generate_runner.py`,
      `edit Makefile`, `edit .gitignore`, `create tests/unit/evals/test_generate_runner_k.py`. Each case runs k
      times; each turn records `duration_ms` and a `GET /v1/admin/debug/retrieval` capture; output goes to
      `evals/generations/<gen_id>/{meta.json,outputs.jsonl}` (gitignored).
      RED anchor: `tests/unit/evals/test_generate_runner_k.py::test_k_repeats_produce_k_records_per_case` fails
      because `collect_records` has no repeat loop.
      Validation: `make eval-generate ARGS="--k 2 --gen-id smoke"` against a mock client writes
      `evals/generations/smoke/` containing 2× the single-run record count, every record carrying
      `repetition ∈ {0,1}`, `duration_ms > 0`, and a non-empty `retrieved_context`.
      **Size watch:** `generate_runner.py` is 276 L — extract the capture helper into a new module, do not grow it. ✅ AUTO (EVAL-P1.4, 2026-08-06)

- [x] **EVAL-P1.5** Honest `golden_set_version`. Two runs over different case sets currently record the
      same run identity: `run_config.py:40` defaults `golden_set_version` to the constant `"unversioned"`
      and nothing ever overrides it, so the field claims reproducibility it does not provide — the same
      class of defect as EVAL-P1.2, found while planning it.
      Files: `edit evals/run_config.py`, `edit tests/unit/evals/test_run_config.py`.
      Add `resolve_golden_set_version(cases_dir) -> str`: sha256 over each case file's name and bytes in
      sorted-name order, rendered as the first 12 hex chars. Call it from `resolve_run_config`.
      RED anchor: `tests/unit/evals/test_run_config.py::test_golden_set_version_changes_when_a_case_changes`
      fails because the value is a hardcoded constant.
      Validation: editing one byte of one case file changes the hash; touching a file's mtime without
      changing content does not; an empty or missing cases dir raises a named error rather than returning
      the hash of nothing. **Leave `retrieval_profile` as-is** but state in its field docstring that it is
      not yet wired to any retrieval configuration, so no reader mistakes a default for a measurement. ✅ AUTO (EVAL-P1.5, 2026-08-07)

- [x] **EVAL-P1.6** Persist the judge pass. `judge_runner.main` writes a markdown report
      (`report.write_report`) and prints a summary — **the 115 record-level verdicts are never saved in any
      machine-readable form.** The EVAL-P0.4 session log already noted this ("Not persisted: the 115
      record-level judge verdicts; `judge_runner` has no `--json-out`") but nothing was scheduled, and three
      later pieces of this program silently depend on it: EVAL-P5.6 has no source for `scorer_verdict`,
      EVAL-P8.2 cannot build `CaseStat` without re-running the judge (violating its own "no Ollama"
      constraint), and EVAL-P7.3 cannot show per-repetition judge reasoning.
      Files: `edit evals/judge_runner.py`, `create tests/unit/evals/test_judged_records.py`,
      `edit Makefile`.
      Add `--json-out` writing `evals/generations/<gen_id>/judged.jsonl`, one JSON object per
      `JudgedRecord`: `record_id`, `case_id`, `judge_kind`, `passed`, `score`, `detail`, `judge_model`, and
      the `repetition` carried through from the generation record. Mirror the `--json-out` precedent
      `evals/verdicts.py` already set for the two case-level runners in EVAL-P0.4.
      RED anchor: `tests/unit/evals/test_judged_records.py::test_json_out_writes_one_row_per_judged_record`
      fails — the flag does not exist.
      Validation: a 6-record fixture transcript produces 6 JSONL rows that round-trip back into
      `JudgedRecord`; `judge_model` is recorded on **every** row (so a transcript judged twice by different
      models stays attributable — the ISSUE-129 disagreement is unreadable otherwise); an infra failure
      writes `passed=false, score=null` and is distinguishable from a genuine fail, never silently dropped.
      **Blocks:** EVAL-P5.6, EVAL-P7.2, EVAL-P7.3, EVAL-P8.2. ✅ AUTO (EVAL-P1.6, 2026-08-07)

### Phase EVAL-P2 — Statistics, hand-implemented
**Goal:** A binary judge plus k repeats becomes a per-case pass rate with a Wilson interval and a flakiness
class — no statistics library, every number defensible line by line.
**Effort:** 2 h · **running total: 7.33 h**
**Constraint:** `math` only. **No new dependency** — `sklearn`, `scipy` and `statsmodels` are all absent from
the venv, and declaring one trips the CLAUDE.md ask-gate. (This also moots the proposal's
"`sklearn.metrics.cohen_kappa_score`, ~5 lines".)
**Notes:** Do **not** bolt k onto `summary.EvalSummary` — it is a count model whose `guarantee_demonstrated`
uses guard *cases*, and it is inside `--cov`. Add new modules and leave `summary.py` serving the legacy
headline until EVAL-P6 folds it in. Wilson at the k you can afford is wide and the report must say so:
3/3 ⇒ **[0.438, 1.000]**, 3/5 ⇒ **[0.231, 0.882]**. Print k next to every rate.
**Depends on:** EVAL-P1.4 (needs `repetition` on records).

- [x] **EVAL-P2.1** Wilson score interval. Files: `create evals/statistics.py`, `create tests/unit/evals/test_statistics.py`.
      `wilson_interval(successes, trials, z=1.96) -> tuple[float, float]` and `pass_rate(successes, trials)`.
      RED anchor: `tests/unit/evals/test_statistics.py::test_wilson_3_of_3` fails — module absent.
      Validation: a table-driven test pins (0,3)→[0.000, 0.562], (3,3)→[0.438, 1.000], (3,5)→[0.231, 0.882]
      to 3 dp, with the hand-worked arithmetic in the test docstring; `trials == 0` raises, never returns [0,1]. ✅ AUTO (EVAL-P2.1, 2026-08-06)

- [x] **EVAL-P2.2** Per-case statistics. Files: `create evals/case_stats.py`, `create tests/unit/evals/test_case_stats.py`.
      Frozen Pydantic `CaseStat(case_id, k, passes, pass_rate, ci_low, ci_high, classification)` with
      `classification: Literal["stable_pass", "flaky", "stable_fail"]`; `classify(passes, k)`;
      `aggregate(judged_records) -> tuple[CaseStat, ...]` grouped by `case_id` across repetitions.
      RED anchor: `tests/unit/evals/test_case_stats.py::test_two_of_three_classifies_flaky` fails.
      Validation: over a fixture transcript with k=3, a case at 2/3 reports `flaky` with CI [0.208, 0.939];
      3/3 reports `stable_pass`; 0/3 reports `stable_fail`; the list sorts by instability with flaky cases first. ✅ AUTO (EVAL-P2.2, 2026-08-06)

- [x] **EVAL-P2.3** Honest denominators. `runner._run_case` turns a 404 NPC into `passed: True, skipped: True`
      and `summary.summarize` counts it in `total_cases` — with only the demo world seeded that is **4 free
      passes out of 53**. Files: `edit evals/summary.py`, `edit tests/unit/engines/test_eval_summary.py`.
      Add `evaluated_cases` (excludes fully-skipped) and make `format_summary_lines` print it as the
      denominator alongside `total_cases`. **`evaluated_cases` is the canonical denominator frozen at
      EVAL-P0.4 (g)** — this step implements that decision, it does not re-open it.
      RED anchor: `tests/unit/engines/test_eval_summary.py::test_skipped_cases_excluded_from_evaluated_denominator` fails.
      Validation: a 53-case fixture with 4 fully-skipped cases reports `49 evaluated / 53 total` and no summary
      line quotes 53 as a pass-rate denominator. **`summary.py` is in `--cov`** — coverage must stay ≥80 %. ✅ AUTO (EVAL-P2.3, 2026-08-06)

### Phase EVAL-P3 — Deterministic graph scorers (no LLM)
**Goal:** Two LLM-free scorers over cached text — unsupported-entity rate and unpropagated-event references —
that measure the architecture's own thesis rather than generic output quality.
**Effort:** 2.5 h · **running total: 9.83 h**
**Constraint:** src-free **over HTTP**, not through `engine_adapter.py`: entity vocabulary from
`GET /v1/graph/nodes/{node_type}?limit&offset`, knowledge from `GET /v1/graph/edges/KNOWS_ABOUT/{src}/{dst}`
(both confirmed present in `live_openapi.json`). Scorers are **pure functions** over
`(text, vocabulary, known_ids)`; the HTTP fetch lives in a separate module so scorers unit-test with zero I/O.
**Notes:** These need a live engine + Neo4j, so they can **never** run inside `make check` — `test-cov` runs
`pytest tests/` with mocks and no Docker. Only their pure halves are gated. The proposal's "run them on every
save" is achievable but means leaving `docker-compose up -d` running, not a zero-cost loop.
**`KNOWS_ABOUT` is not the only license to speak.** The anti-hallucination fixture's own `knowledge_basis`
field cites **beliefs** (`ah_demo_sorn_walls_belief`) and **goals** (`ah_demo_sorn_guild_goal`) as valid
grounds; memories and `WITNESSED` edges too. A `KNOWS_ABOUT`-only metric **will flag correct answers as
violations** — so the metric is named *unpropagated-event reference rate*, and the excluded edge types are
enumerated in the module docstring. Extraction is **alias-table whole-word matching, not NER**: pronouns are
invisible, partial names ("the Captain") need the table, and an unnamed fabrication ("a merchant from the
eastern docks") is undetectable — those go in the README as documented limits, not the backlog.
**Depends on:** EVAL-P1.3.

- [x] **EVAL-P3.1** Vocabulary fetch. Files: `create evals/graph_vocabulary.py`,
      `create tests/unit/evals/test_graph_vocabulary.py`. Paged `GET /v1/graph/nodes/{node_type}` over
      Character / Location / Event / Faction into a frozen `GraphVocabulary` Pydantic model, cached to
      `evals/generations/<gen_id>/vocabulary.json` so scoring is replayable with the engine down.
      RED anchor: `tests/unit/evals/test_graph_vocabulary.py::test_paginates_until_short_page` fails — module absent.
      Validation: against a mock client returning 2 pages, the model holds every id from both pages and issues
      exactly 3 requests (two full, one short); re-running with a cache file present issues **zero** requests. ✅ AUTO (EVAL-P3.1, 2026-08-06)

- [x] **EVAL-P3.2** Unsupported-entity scorer (pure). Files: `create evals/entity_scorer.py`,
      `create evals/cases/entity_aliases.yaml`, `create tests/unit/evals/test_entity_scorer.py`.
      `unsupported_entity_rate(text, vocabulary, aliases) -> EntityScore` with `mentions`, `unsupported`, `rate`.
      RED anchor: `tests/unit/evals/test_entity_scorer.py::test_unknown_proper_noun_counts_as_unsupported` fails.
      Validation: on a fixture text naming `mira_innkeeper` (known), "the Captain" (alias → `captain_sorn`, known)
      and "Warden Aldous" (absent), the scorer returns `mentions=3, unsupported=1, rate=0.333`; a pronoun-only
      sentence returns `mentions=0` and the docstring states pronouns are out of scope. ✅ AUTO (EVAL-P3.2, 2026-08-06)

- [x] **EVAL-P3.3** Unpropagated-event-reference scorer (pure). Files: `create evals/knowledge_scorer.py`,
      `create tests/unit/evals/test_knowledge_scorer.py`.
      `unpropagated_references(text, event_vocabulary, npc_known_event_ids) -> KnowledgeScore`.
      RED anchor: `tests/unit/evals/test_knowledge_scorer.py::test_event_not_in_known_set_is_flagged` fails.
      Validation: `old_henryk` referencing `northern_war_begins` while its known-set excludes it yields one
      violation; the same text for `captain_sorn` (direct `KNOWS_ABOUT`, per the demo world table in `CLAUDE.md`)
      yields zero. The module docstring **lists** belief / goal / memory / `WITNESSED` as deliberately excluded
      grounds and states the resulting false-positive risk. ✅ AUTO (EVAL-P3.3, 2026-08-06)

- [x] **EVAL-P3.4** Wire both into the score pass. Files: `create evals/deterministic_pass.py`,
      `edit Makefile`, `create tests/unit/evals/test_deterministic_pass.py`.
      RED anchor: `tests/unit/evals/test_deterministic_pass.py::test_scores_every_record_without_llm` fails.
      Validation: `make eval-score TRANSCRIPT=<file>` scores a cached transcript and prints both rates with
      **no network call to Ollama** — asserted by a test that fails if `matchers._run_binary_judge` is invoked. ✅ AUTO (EVAL-P3.4, 2026-08-06)

### Phase EVAL-P4 — Retrieval decomposition over the existing annotations
**Goal:** Separate retrieval failure from generation failure, so a failing case can be attributed rather
than guessed at.
**Effort:** 2.25 h · **running total: 12.08 h**
**Constraint:** Reuse `retrieval_matchers.recall_at_k` / `precision_at_k` **verbatim**. New code is the
*join*, not the metric.
**Notes:** ~60 % of this already exists and the proposal's Phase 4/7 retrieval work is largely duplication.
`retrieval_demo.json` already carries `relevant_node_ids` per (npc, query) — precisely the "required fact
annotation" the proposal wants to invent, for **20** cases. What is genuinely missing is computing it against
the `retrieved_context` **captured in the transcript** (EVAL-P1.4) rather than a second in-process retrieval,
so retrieval quality and generation quality come from the same run.
⚠️ **Corrected 2026-08-02 (DEC-153 §5) — this phase had no real input.** EVAL-P4.2's cross-tab needs cases
carrying **both** `relevant_node_ids` **and** a pass/fail verdict. **Zero cases have both:** the 20 annotated
retrieval cases are ids `RET-001…` with no judge verdict, the 53 dialogue cases are `case_*.yaml` with a
verdict and no annotation, and the id-set intersection is **empty** (verified). As written, P4.2 was
buildable against fixtures and unbuildable against reality. EVAL-P4.0 below funds a **15-case** subset so the
join has real data; the remaining 38 stay Parked.
**Depends on:** EVAL-P1.4, EVAL-P2.2.

- [x] **EVAL-P4.0** Annotate the 15 highest-signal dialogue cases with `relevant_node_ids` (the P4.2
      prerequisite). Files: `edit evals/cases/case_*.yaml` (15 files), `create tests/unit/evals/test_case_annotations.py`.
      Choose the 15 from the **37 guard cases** (`case_adv_` / `case_neg_`) — that is where hallucination
      actually lives and therefore where retrieval-vs-generation attribution pays. Each gains a
      `relevant_node_ids: [...]` list naming the graph nodes a correct answer must have retrieved.
      RED anchor: `tests/unit/evals/test_case_annotations.py::test_annotated_case_count_is_at_least_15` fails
      because no `case_*.yaml` carries the key.
      Validation: ≥15 cases parse with a non-empty `relevant_node_ids`; every id in every list exists in the
      demo-world seed (assert against `demo_game/seeds/seed.py` node ids, so a typo fails the gate rather
      than silently scoring as a retrieval miss); unannotated cases still load unchanged. ✅ AUTO (EVAL-P4.0, 2026-08-07)

- [x] **EVAL-P4.1** Shared key→node-id extraction. `retrieval_runner._node_id_from_key` (`:58`) is needed by
      both runners. Files: `create evals/context_keys.py`, `edit evals/retrieval_runner.py`,
      `create tests/unit/evals/test_context_keys.py`.
      RED anchor: `tests/unit/evals/test_context_keys.py::test_rag_prefix_strips_to_node_id` fails — module absent.
      Validation: `rag:northern_war_begins` → `northern_war_begins`, `character:mira_innkeeper` → `mira_innkeeper`,
      a bare key round-trips; `make eval-retrieval` output unchanged. ✅ AUTO (EVAL-P4.1, 2026-08-07)

- [x] **EVAL-P4.2** Decomposition table. Files: `create evals/retrieval_join.py`,
      `create tests/unit/evals/test_retrieval_join.py`. Per record, compute context recall/precision of
      `retrieved_context` against the case's `relevant_node_ids`, then cross-tabulate
      `retrieval_hit × case_passed` into a 2×2.
      RED anchor: `tests/unit/evals/test_retrieval_join.py::test_retrieved_but_failed_is_a_generation_failure` fails.
      Validation: over a fixture transcript the table reports four counts — *retrieved & passed*,
      **retrieved & failed (generation failure)**, *not retrieved & failed (retrieval failure)*, and
      *not retrieved & passed (lucky)* — and the four sum to the count of **annotated** records. Records for
      unannotated cases are reported as an explicit excluded count with the denominator stated, never
      silently dropped (the whole phase exists because a silent empty join looked like a working table). ✅ AUTO (EVAL-P4.2, 2026-08-07)

### Phase EVAL-P5 — Calibration: model pre-label + human adjudication
**Goal:** A versioned, reproducible calibration artifact — **500** outputs pre-labelled by a reference model
and adjudicated by the maintainer — with **every scorer measured separately** as a full confusion matrix plus
Cohen's κ **and its bootstrap CI**, so the eval can state how much its own headline can be trusted.
**Effort:** 2.5 h of build time · **running total: 14.58 h** (+ **4–6 h of your adjudication**, done outside
a coding session — it is not `/expand-next` work, and it is the largest human cost in the program)
**Constraint:** The reference labeller must differ from **both** the generation model (`qwen2.5:7b`) **and**
the judge (`mixtral:8x7b`) — a direct extension of DEC-143's collision invariant. **Labeller = `claude-opus-5`
(🔶 DEC-152, ACCEPTED 2026-08-02).** Client is **raw `httpx` against the Anthropic REST API**; the `anthropic`
SDK is a new dependency and trips the ask-gate. `ANTHROPIC_API_KEY` from env only, never committed, never
logged. κ is hand-implemented (~15 lines on `math`) — `sklearn` is absent.
**Sizing (DEC-153 §7):** 500 labels ÷ 6 scorers ≈ **85 rows each**, giving κ a standard error of roughly
±0.10. At the original 250 that was ≈40 rows and ±0.15 — an uncertainty as wide as the thing being measured.
Cost is **not** the constraint: 500 labels on `claude-opus-5` ($5/$25 per Mtok) is ≈ **$4**, halvable again
via the Batches API since this is not latency-sensitive. **Your adjudication hours are the constraint** —
doubling the label count doubles them, and that was an explicit trade.
**Notes:** The proposal's framing — *"the labels already exist, so this is cheap"* — is **false**; grep for
`calibrat|human_verdict|kappa|confusion` returns zero repo-wide. Because you adjudicate model-proposed labels
rather than labelling cold, store **both** `pre_label` and `human_verdict` on every row: the disagreement rate
between them is then a free, publishable reference-model-vs-you number with no second pass. **Calibrate each
scorer separately** — keyword matchers, tone judge, affirms judge, refusal judge, and the two EVAL-P3 graph
scorers. An aggregate conceals which component drags. The real labels stay private; only the **schema** and a
synthetic sample are publishable (see *Post-program milestones*).
⚠️ **Two honesty caveats that belong in the report, not a backlog (DEC-153 §7).** (a) You wrote the criteria,
the prompts and the cases, so κ measures agreement with **the author's intent**, not with correctness — say
which one it is. (b) You adjudicate *model-proposed* labels, so agreement is inflated by anchoring; the
`pre_label`-vs-`human_verdict` disagreement rate measures disagreement but cannot separate "the model was
right" from "you were anchored". Blinding a subsample was considered and **not** funded — state the limit.
**Depends on:** EVAL-P1.3 (labels reference `record_id`), EVAL-P3 (graph scorers must exist to be calibrated).
**Decision:** 🔶 **DEC-152 ACCEPTED 2026-08-02** — reference-labeller model separation
(labeller ∉ {generation models} ∪ {judge model}, enforced like `JudgeModelCollisionError`), labeller fixed at
`claude-opus-5`. This **replaces the `DEC-149` reference that previously appeared here and at EVAL-P5.2**:
`DEC-149` is *"All five engines standardise on qwen2.5:7b"* (DECISIONS.md), an unrelated decision, and citing
it falsely marked P5.2's ask-gate cleared. See DEC-153 §1.

- [x] **EVAL-P5.1** Label record model. Files: `create evals/calibration_records.py`,
      `create tests/unit/evals/test_calibration_records.py`. Frozen Pydantic `CalibrationLabel(record_id,
      scorer, output_text, pre_label: bool, pre_labeller_model: str, human_verdict: bool | None,
      adjudicated_at: str | None, notes: str)` + JSONL read/write to `evals/calibration/labels_v1.jsonl`.
      RED anchor: `tests/unit/evals/test_calibration_records.py::test_unadjudicated_row_round_trips_with_null_verdict` fails.
      Validation: 3 rows round-trip through JSONL byte-identically; a row missing `pre_labeller_model` raises
      `ValidationError`; the **frozen output text** is stored inline, never a pointer to something regenerable. ✅ AUTO (EVAL-P5.1, 2026-08-07)

- [x] **EVAL-P5.2 — SUPERSEDED 2026-08-07 by `EVAL-P5.6`.** Not run as written. The maintainer elected to
      pre-label with Opus through the Claude CLI rather than an in-repo `httpx` client, which removes the
      API-key handling, the ~$4 batch cost and the `LabellerModelCollisionError` guard (the labeller is now
      chosen by the human at the prompt, not resolved in code). The transcript-join half of this task is
      real and survives as **EVAL-P5.6**; the prompt itself is committed at
      `evals/calibration/LABEL_PROMPT.md`. Original text kept below for provenance.
      Pre-labelling runner. Files: `create evals/label_runner.py`,
      `create tests/unit/evals/test_label_runner.py`, `edit Makefile`. `httpx.post` → Anthropic REST
      (`POST /v1/messages`, `model="claude-opus-5"`, `anthropic-version: 2023-06-01`), one pre-label per
      transcript record per scorer, with a `LabellerModelCollisionError` guard mirroring
      `judge_config.resolve_judge_model`. Target **500 rows** across the six scorers. Prefer the Batches API
      (`POST /v1/messages/batches`, 50 % cheaper, results keyed by `custom_id` and returned in **any** order)
      — this is a bulk offline job with no latency requirement.
      RED anchor: `tests/unit/evals/test_label_runner.py::test_labeller_equal_to_judge_model_raises` fails.
      Validation: against a mocked HTTP client, 5 records produce 5 `CalibrationLabel` rows with
      `human_verdict=None`; setting the labeller to `mixtral:8x7b` or to a discovered generation model raises;
      a missing `ANTHROPIC_API_KEY` fails fast with a named error and **never** appears in any log line.
      ✅ **DEC-152 ACCEPTED 2026-08-02** (labeller = `claude-opus-5`) — no longer a halt condition.
      *(Corrected 2026-08-02: this line previously cited `DEC-149`, which is the qwen2.5:7b fleet decision and
      says nothing about labellers. The ask-gate was therefore marked cleared by a decision that was never
      made. DEC-152 is the real one. See DEC-153 §1.)*

- [x] **EVAL-P5.3** Adjudication CLI. Files: `create evals/adjudicate.py`, `create tests/unit/evals/test_adjudicate.py`.
      Prints one row at a time (output text + `pre_label` + scorer), accepts keep/flip/skip, writes
      `human_verdict` + `adjudicated_at` back in place, and is **resumable** — re-running skips adjudicated rows.
      RED anchor: `tests/unit/evals/test_adjudicate.py::test_resume_skips_already_adjudicated_rows` fails.
      Validation: on a 5-row file with 2 adjudicated, the CLI presents exactly 3 rows; flipping one writes
      `human_verdict != pre_label` and leaves `pre_label` untouched. ✅ AUTO (EVAL-P5.3, 2026-08-07)

- [x] **EVAL-P5.4** Confusion matrices + κ. Files: `create evals/calibration.py`,
      `create tests/unit/evals/test_calibration.py`, `edit Makefile` (`eval-calibrate`).
      Per scorer: TP/FP/FN/TN, precision, recall, hand-implemented `cohens_kappa`, **and a bootstrap
      confidence interval on κ** (`kappa_interval(rows, resamples=2000, seed)` — `math` + `random` only, no
      new dependency). Plus the free pre-label-vs-human agreement rate.
      RED anchor: `tests/unit/evals/test_calibration.py::test_cohens_kappa_matches_worked_example` fails.
      Validation: κ pinned to 3 dp against a hand-worked 2×2 in the test docstring; perfect agreement → 1.000,
      chance-level → 0.000. **The CI is seeded and reproducible** — the same rows and seed yield the same
      bounds across runs, and a fixture of ~85 rows produces a visibly wide interval. `make eval-calibrate`
      prints **one matrix per scorer** — never a single aggregate — each κ rendered with its interval and its
      n adjacent, and the false-positive cell labelled as the dangerous one.
      **Rationale (DEC-153 §7):** a program created to stop reporting point estimates without error bars must
      not report its own trust metric as a point estimate without error bars. At ~85 rows κ's SE is ≈ ±0.10,
      so a κ of 0.60 is really ≈ [0.40, 0.80] — a difference that changes what the number licenses you to say. ✅ AUTO (EVAL-P5.4, 2026-08-07)

- [x] **EVAL-P5.5** Put the scorer on an axis of its own confusion matrix (**closes ISSUE-133**).
      `confusion_counts` (`calibration.py:73-88`) and `cohens_kappa` (`:115-149`) both compare `pre_label`
      against `human_verdict`, and `CalibrationLabel` has no field for the scorer's own verdict — `scorer`
      is only a grouping key (`:231`). So `make eval-calibrate` reports how often the reference labeller
      agrees with the maintainer, which this phase's own notes call the *free secondary* number, while the
      headline question ("can I trust `tone_judge`?") is not computed at all.
      Files: `edit evals/calibration_records.py`, `edit evals/calibration.py`,
      `edit tests/unit/evals/test_calibration.py`, `edit tests/unit/evals/test_calibration_records.py`.
      Add `scorer_verdict: bool` to `CalibrationLabel`. Make `scorer_verdict` vs `human_verdict` the
      headline matrix and keep `pre_label` vs `human_verdict` as a clearly-labelled secondary block. Both
      κ values get their own bootstrap CI and n.
      RED anchor: `tests/unit/evals/test_calibration.py::test_headline_matrix_compares_scorer_verdict_to_human`
      fails because no such field exists.
      Validation: a fixture where the scorer and the human agree 9/10 but the reference labeller agrees
      10/10 reports **two different** κ values, and the printed FP cell reads "scorer said pass, human
      said fail". A row missing `scorer_verdict` raises `ValidationError`.
      **Decision 2026-08-07 (human): option A.** Human adjudication time, local judge compute and CLI token
      cost are all identical with or without this field; only this version can change what gets fixed in the
      engine. Must land before any adjudication session — labels adjudicated against the old axis answer
      the wrong question and cannot be re-derived without redoing the hours. ✅ AUTO (EVAL-P5.5, 2026-08-08)

- [x] **EVAL-P5.6** Batch export + validating import for the CLI labelling pass (replaces EVAL-P5.2).
      Files: `create evals/label_export.py`, `create evals/label_import.py`,
      `create tests/unit/evals/test_label_export.py`, `create tests/unit/evals/test_label_import.py`,
      `edit evals/__main__.py`, `edit Makefile`.
      `label_export` writes batches of at most 25 items as JSON (`record_id`, `scorer`, `npc_id`,
      `player_message`, `criteria`, `output_text`, plus `vocabulary` for the two graph scorers) for
      `evals/calibration/LABEL_PROMPT.md` to consume. **It must never emit `scorer_verdict` or any judge
      verdict** — the artifact is void if the labeller can see the answer it is measured against.
      `label_import` reads the model's minimal JSONL (`record_id`, `scorer`, `pre_label`, `notes`), joins
      `output_text` from the transcript and `scorer_verdict` from the judged records, stamps
      `pre_labeller_model`, and writes validated `CalibrationLabel` rows.
      RED anchor: `tests/unit/evals/test_label_import.py::test_unknown_record_id_is_rejected_not_dropped`
      fails — module absent.
      Validation: a raw row naming a `record_id` absent from the transcript raises a named error rather than
      being skipped; a raw row carrying `output_text` or `scorer_verdict` is rejected as contaminated; 5 raw
      rows produce 5 rows with `human_verdict=None`; round-tripping through `write_calibration_labels` is
      byte-identical. Add verbs `label-export` / `label-import` and the matching make targets.
      **Depends on:** EVAL-P5.5 (schema) and, for full six-scorer coverage, EVAL-P6.1 (the deterministic
      records must exist in the transcript before they can be exported). Safe to build before P6.1 — the
      join is by `record_id` and the tests are fixture-driven — but do not *run* it against a pre-P6.1
      generation or four of the six scorers will silently have no rows. ✅ AUTO (EVAL-P5.6, 2026-08-08)

### Phase EVAL-P6 — One CLI; legacy targets become aliases
**Goal:** A single `python -m evals <verb>` entry point, with the seven legacy make targets reduced to thin
aliases so the gate stays green at every commit and no target is orphaned.
**Effort:** 1.5 h · **running total: 16.08 h**
**Constraint:** **No target is deleted in this phase.** Deletion is a separate final step once nothing
references them — that step is Parked. **DEC-148 ✅ ACCEPTED 2026-07-31 (ordering locked: coverage parity → aliases → delete last).**
**Notes:** **Blocked by a dependency the proposal never names.** `generate_runner._build_yaml_records_for_case`
records **only** `tone_judge` / `affirms_judge` (`_LLM_JUDGE_KINDS`, `:36`) — `min_length`, `keyword_none`,
`schema`, `in_set`, `range` and `keyword_any` all remain in `runner.py`'s inline pass, and grounded
anti-hallucination cases return `None` (`_build_ah_record:129`). So the transcript path today scores a **strict
subset** of `make eval` and cannot replace it. That is EVAL-P6.1 and it must land before any alias.
Separately: `judge_runner._to_result_dict` sets `case_id = record_id`, so each guard case emits two records and
`summary` reports **74** guard turns where `make eval` reports **37** — the two headlines are not comparable
(logged as **ISSUE-123**; closed here).
**Depends on:** EVAL-P1.3, EVAL-P2.3, EVAL-P3.4.

- [x] **EVAL-P6.1** Deterministic matchers off the transcript. Files: `edit evals/generate_runner.py`,
      `create evals/deterministic_records.py`, `create tests/unit/evals/test_deterministic_records.py`.
      Every non-judge expectation becomes a record with `judge_kind=None` plus the data the matcher needs;
      grounded anti-hallucination cases gain records too.
      RED anchor: `tests/unit/evals/test_deterministic_records.py::test_keyword_none_expectation_produces_a_record` fails
      because `_LLM_JUDGE_KINDS` filters it out.
      Validation: for a fixture case with `schema + keyword_none + tone_judge`, the transcript holds **3** records
      (2 deterministic, 1 judged), and scoring the transcript reproduces `make eval`'s per-case verdict exactly —
      asserted case-by-case against a recorded `make eval` result fixture.
      **Refinement 2026-08-07 (scope confirmed by the maintainer: full parity).** "Recorded `make eval` result
      fixture" cannot mean a live A/B: `runner.py` generates *and* scores in one pass, so its verdicts come
      from a different set of NPC responses than any separately-generated transcript, and the two would differ
      for reasons that have nothing to do with scoring. The testable property is **matcher equivalence** —
      build a fixture of `(expectation, response)` pairs covering every kind and assert that
      `matchers.evaluate()` and the transcript path return an identical `(passed, detail)` for each. That is
      deterministic, needs no live stack, and is the property the alias in EVAL-P6.3 actually depends on.
      Cover all ten kinds: `schema`, `keyword_none`, `keyword_any`, `keyword_all`, `min_length`, `in_set`,
      `range`, `substring`, `regex`, `context_block_expected` — plus grounded anti-hallucination cases,
      which return `None` today (`_build_ah_record:129`).
      **Add a guard test** that fails when a new `_eval_*` matcher appears in `matchers.py` without a
      corresponding recorder, so this cannot silently regress to a subset — the failure mode the whole
      phase exists to close.
      ✅ AUTO (EVAL-P6.1, 2026-08-07). Implemented as planned, with two additive deviations kept inside the
      phase's own scope: `eval_records.DeterministicMatcherKind` (a `Literal`, not a raw `str`, for
      `GenerationRecord.matcher_kind` — required-strict per the coding-style rules) is the single source of
      truth both `deterministic_records.covered_matcher_kinds()` and the guard test derive from; and
      `generate_runner.py`'s record-builder helpers were split into a new `evals/generation_records.py`
      (SRP: HTTP collection loop + CLI vs. per-case record construction) to keep `generate_runner.py` under
      the 300-line file cap after the new dispatch logic landed. `_post_dialogue` now returns the full parsed
      response body (was `npc_response` only) — `in_set`/`range` check `facial_expression.type`,
      `action.type`, `relation_deltas.*`, which the deterministic records must be able to replay.

- [x] **EVAL-P6.2** Fix the guard-turn double count (**closes ISSUE-123**). Files: `edit evals/judge_runner.py`,
      `edit tests/unit/test_judge_runner.py`. Group records back to `case_id` before `summarize`, so one case is
      one guard turn regardless of how many expectations it carries.
      RED anchor: `tests/unit/test_judge_runner.py::test_guard_turn_count_matches_case_count_not_record_count` fails
      (reports 2 for a single guard case).
      Validation: a fixture with 37 guard cases × 2 records reports **37** guard turns, matching `make eval`;
      mark ISSUE-123 `[FIXED]` and move it to `archive/ISSUES_RESOLVED.md`.
      ✅ AUTO (EVAL-P6.2, 2026-08-07). `group_by_case` groups by `(case_id, repetition)`, not `case_id` alone,
      so a future k>1 run (EVAL-P6.4) still counts each repetition as its own guard turn instead of collapsing
      them. Split into a new `evals/judge_case_grouping.py` alongside `judge_runner.py` for the same
      300-line-cap reason as EVAL-P6.1's `generation_records.py` split; `judge_runner._write_judged_jsonl`'s
      per-record JSONL output is unchanged, only the summarize/report path was double-counting. ISSUE-123
      moved to `archive/ISSUES_RESOLVED.md` as `[FIXED]`.

- [ ] **EVAL-P6.4** *(live; not `make check`-gated — requires engine + Neo4j + Ollama up)* **The first
      measured k=3 run.** Every statistic built in EVAL-P2 through EVAL-P5 has so far only ever seen
      fixtures: `evals/generations/baseline/` holds `verdicts.json` and `verdicts_ah.json` but **no
      `meta.json` and no `outputs.jsonl`**, and the only transcript on disk
      (`e2e/transcripts/eval_generation_latest.json`) is `version: 1`, which `read_transcript` now rejects
      by design. So no k>1 run has ever executed and no `retrieved_context` has ever been captured.
      **Run only after EVAL-P1.2, EVAL-P1.5, EVAL-P6.1 and EVAL-P6.2 have landed** — a run made before them
      records a false `prompt_version`, a placeholder `golden_set_version`, and scores a strict subset of
      `make eval`, so it has to be thrown away and regenerated.
      Preconditions that are easy to get wrong and produce a silently worthless artifact rather than a
      failing one: all three worlds seeded; `JUDGE_TIMEOUT_SECONDS=300` (a cold 27 GB mixtral load takes
      22.8 s against a 30 s default, and infra failures score `None`, i.e. inconclusive, not failed); and a
      mixtral prewarm before the judge pass.
      Expected wall clock from the EVAL-P0.4 rates: `k × (78 × 3.57 s + 115 × 8.43 s)` ≈ **62 min at k=3**.
      Judge policy for this run — **single judge (`mixtral:8x7b`), with the `qwen2.5:14b` disagreement
      stated as a known limit** (human decision, 2026-08-07). ISSUE-129 stays open; the headline remains
      judge-dependent and must say so.
      Validation: `evals/generations/<gen_id>/` contains `meta.json` + `outputs.jsonl`; every record carries
      `repetition` in `{0,1,2}`, `duration_ms > 0` and a non-empty `retrieved_context`; `make eval-score` and
      the EVAL-P4.2 cross-tab both produce non-empty tables. Record the resulting `gen_id` in this task's
      DONE marker — EVAL-P5.6, EVAL-P7 and EVAL-P8 all consume it by name.
      **This task is for a human session. The unattended loop must not start it.**

- [x] **EVAL-P6.3** Verb dispatch + aliases. Files: `create evals/__main__.py`, `edit Makefile`,
      `create tests/unit/evals/test_cli_dispatch.py`. Verbs: `generate`, `score`, `judge`, `calibrate`,
      `report`, `retrieval`. All seven legacy targets (`eval`, `eval-report`, `eval-anti-hallucination`,
      `eval-llm`, `eval-llm-demo`, `eval-retrieval`, `eval-combined`) become one-line aliases delegating to it.
      RED anchor: `tests/unit/evals/test_cli_dispatch.py::test_unknown_verb_exits_2_with_verb_list` fails.
      Validation: `python -m evals --help` lists all six verbs; each legacy `make` target still runs and
      produces the same exit code as before; `make check` green.
      ⚠️ **ask-gate:** rewrites seven Makefile targets — a shared public surface.
      ✅ **DONE 2026-08-07** — ask-gate cleared by explicit human instruction ("fix p6.3"). Three
      deviations from the spec as written, all recorded in **DEC-155**: (1) **eight** verbs, not six —
      `anti-hallucination` is required for `eval-anti-hallucination` to delegate at all, and `adjudicate`
      is added because the EVAL-P5 workflow needs it; the six specced verbs are all present.
      (2) `eval-llm` / `eval-llm-demo` stay direct `pytest` invocations — they are test-suite runs, not
      harness modules, so aliasing them would make the CLI shell out to pytest. (3) `__main__.py`
      prepends `evals/` to `sys.path` because the package mixes flat and package-absolute imports
      (**ISSUE-132**); unifying them is out of scope for a phase whose constraint is a green gate at every
      commit. Also widened `calibration.main` / `adjudicate.main` to accept `argv` and added a sync
      `retrieval_runner.main`, so all eight targets share one `main(argv) -> int` contract.

### Phase EVAL-P7 — Engine-developer eval dashboard
**Goal:** A local dev-facing dashboard that reads the run artifacts and makes flakiness, calibration and
per-case history legible — the surface that eventually replaces the CLI as the way the suite is driven.
**Effort:** 2.5 h · **running total: 18.58 h**
**Constraint:** Lives **inside `evals/`** as its own small FastAPI app (`python -m evals dashboard`), importing
the evals package directly — **no API layer**, and `evals/` stays independently publishable. It is **not** the
existing designer dashboard served from `src/npc_engine/api/` at `/dashboard` (`make dashboard`) — that one is
game-designer-facing and stays exactly where it is. Jinja templates + inline SVG; HTMX for partial refresh.
**No node/npm in this repo.** **DEC-148 ✅ ACCEPTED 2026-07-31.**
**Notes:** **Do not start before EVAL-P1/P2/P3 have landed** — the artifact schema this reads must be settled or
the UI gets rewritten. Three views only; the run-comparison view depends on `compare`, which is Parked.
**This phase is the designated cut if the budget overruns** — it sits last precisely so that cutting it
costs nothing already built.
**Depends on:** EVAL-P1.3, EVAL-P2.2, EVAL-P3.4, EVAL-P5.4.

- [x] **EVAL-P7.1** App skeleton + run list. Files: `create evals/dashboard/__init__.py`,
      `create evals/dashboard/app.py`, `create evals/dashboard/templates/runs.html`,
      `create tests/unit/evals/test_dashboard_runs.py`. Lists `evals/generations/*/meta.json` sorted newest
      first with gen_id, k, pass rate, prompt version, git SHA, timestamp.
      RED anchor: `tests/unit/evals/test_dashboard_runs.py::test_run_list_renders_gen_ids_newest_first` fails — module absent.
      Validation: against a tmp dir holding 3 `meta.json` files, `GET /` returns 200 and the three gen_ids in
      descending timestamp order; an **empty** directory returns 200 with an explicit empty-state message,
      not a traceback. ✅ AUTO (EVAL-P7.1, 2026-08-08)

- [x] **EVAL-P7.2** Run detail. Files: `create evals/dashboard/templates/run_detail.html`,
      `edit evals/dashboard/app.py`, `create tests/unit/evals/test_dashboard_detail.py`.
      Headline pass rate **with k rendered adjacent to it**, the calibration badge (per-scorer κ from
      EVAL-P5.4), both EVAL-P3 deterministic rates, the full config block, and the flaky table sorted by
      instability.
      RED anchor: `tests/unit/evals/test_dashboard_detail.py::test_headline_renders_k_adjacent_to_rate` fails.
      Validation: for a k=3 fixture the page contains the literal string `k=3` within the headline element —
      a k=3 number must be visually impossible to mistake for a k=15 number — and the flaky table lists
      2/3 cases above 3/3 cases. ✅ AUTO (EVAL-P7.2, 2026-08-08)

- [x] **EVAL-P7.3** Per-case drill-down. Files: `create evals/dashboard/templates/case_detail.html`,
      `edit evals/dashboard/app.py`, `create tests/unit/evals/test_dashboard_case.py`.
      All k outputs side by side, judge reasoning per repetition, the retrieved context, and the
      expected-vs-actual for each expectation.
      RED anchor: `tests/unit/evals/test_dashboard_case.py::test_all_k_outputs_render_side_by_side` fails.
      Validation: a k=3 case page shows 3 distinct output panes each labelled with its `repetition`, and each
      pane lists that repetition's `retrieved_context` item keys. ✅ AUTO (EVAL-P7.3, 2026-08-08)

### Phase EVAL-P8 — Run-to-run comparison (promoted from Parked, DEC-153 §4)
**Goal:** Answer the question the rest of the program cannot: **did this change make the engine better?**
**Effort:** 1.5 h · **running total: ~20.1 h** (+ ~4 h live wall clock for two test generations)
**Constraint:** Pure functions over two saved transcripts — no engine, no Ollama, no prompt-version selector.
`compare` reads two `evals/generations/<gen_id>/` directories and never re-runs generation.
**Notes:** The program otherwise builds run identity, k repeats, Wilson intervals, flakiness classes,
calibration and a dashboard — an entire apparatus whose only decision-relevant use is comparison, which was
Parked. Worse, the statistic that *works at affordable k* was planned nowhere: per-case Wilson at k=3 spans
[0.438, 1.000] for 3/3, so a case that regressed 100 % → 50 % sits inside its own interval. The **paired
case-level** test is the fix — n = 53 cases, not n = 3 repeats — and it detects real shifts even at k=1.
**This phase is not a cut candidate**; EVAL-P7 is.
**Depends on:** EVAL-P1.4 (two comparable generations), EVAL-P2.2 (`CaseStat`).

- [x] **EVAL-P8.1** Paired case-level significance (`math` only, no new dependency).
      Files: `create evals/paired_stats.py`, `create tests/unit/evals/test_paired_stats.py`.
      `mcnemar_exact(b, c) -> float` (exact binomial two-sided, not the χ² approximation — at 53 cases the
      discordant counts are small enough that χ² is wrong) and
      `paired_compare(before: tuple[CaseStat, ...], after: tuple[CaseStat, ...]) -> PairedResult` with
      frozen Pydantic `PairedResult(improved, regressed, unchanged, p_value, verdict)` where
      `verdict: Literal["better","worse","no_detectable_change"]`.
      RED anchor: `tests/unit/evals/test_paired_stats.py::test_mcnemar_exact_matches_worked_example` fails — module absent.
      Validation: pinned to 3 dp against a hand-worked table in the test docstring; (b=0, c=0) raises rather
      than returning p=1.0; a fixture where 8 cases improve and 1 regresses reports `better`; a fixture where
      3 improve and 3 regress reports `no_detectable_change` **even though the pass count rose**. ✅ AUTO (EVAL-P8.1, 2026-08-08)

- [x] **EVAL-P8.2** `compare` verb over two generation directories.
      Files: `create evals/compare.py`, `edit Makefile`, `create tests/unit/evals/test_compare.py`.
      Load both transcripts → `case_stats.aggregate` each → inner-join on `case_id` → `paired_compare` →
      per-case delta table sorted by regression first. **Report the intersection size and name every case
      present in one run but not the other** — a silently shrunken denominator is the failure mode here.
      RED anchor: `tests/unit/evals/test_compare.py::test_cases_missing_from_one_run_are_named_not_dropped` fails.
      Validation: `make eval-compare BEFORE=<gen_id> AFTER=<gen_id>` prints the verdict with its p-value,
      the k of **both** runs adjacent to every rate, and the four-way delta table; comparing a run against
      itself yields `no_detectable_change` with p = 1.0 and zero discordant pairs. ✅ AUTO (EVAL-P8.2, 2026-08-08)

- [ ] **EVAL-P8.3** *(live; requires the full stack)* **Second measured run and the first real comparison.**
      EVAL-P8.2's unit tests are fixture-driven, so `compare` can be green while never having compared two
      real generations. Generate a second k=3 run at a different commit (any change worth measuring — a
      prompt-version bump is the cheapest honest one), then run `compare` against EVAL-P6.4's `gen_id`.
      Expected wall clock ≈ **62 min**, plus the judge pass.
      Validation: the comparison names the intersection size and every case present in one run and not the
      other; the verdict is one of `better` / `worse` / `no_detectable_change` with its exact McNemar
      p-value; and the k of both runs is printed next to every rate. Sanity check first by comparing
      EVAL-P6.4's run against itself — that must yield p = 1.0 with zero discordant pairs before any
      cross-run number is believed.
      **This task is for a human session. The unattended loop must not start it.**

## Program 2 — Metric validity and the portfolio artifact (EVAL-P9..P14)

**Status: RELEASED to the loop 2026-08-07** (human decision). Phase ids continue the `EVAL-P<n>` sequence
because `test_real_roadmap_parses_and_verifies_clean` asserts the in-fence phases are a contiguous `EVAL-P`
prefix; any other name would fail that test on release.

⚠️ **Read the flag list at the queue's closing marker before assuming this programme can complete
unattended.** Eight of its tasks are flagged because their inputs do not exist yet: the capability battery
needs *your* authoring (EVAL-P9.3), the calibration follow-through needs an adjudicated label set that has
not been produced, and the multi-turn and portfolio phases need a live stack and a real run artifact
respectively. The loop can build the harness for all of it tonight; it cannot produce the measurements, and
a green queue here does **not** mean the metrics got better.

**Why this program exists (measured, 2026-08-07).** Program 1 makes the numbers *precise*. It does not make
them *valid*. The case inventory is:

| Bucket | Count |
|---|---|
| `case_neg_*` (must not say X) | 24 |
| `case_adv_*` (must not be tricked) | 13 |
| `case_pos_*` (must say/do X) | **7** |
| `case_00x`, `case_voice_*`, moderation, reputation | 9 |
| anti-hallucination fixture | 26 refusal / **16 grounded** |

Roughly **63 of 95 cases test "don't do the wrong thing"; ~26 test "do the right thing."** 32 of the 118
expectations are `keyword_none`. The published headline — *"0 lore hallucinations across 37 guard turns"* —
is therefore **maximised by refusing more**, and the EVAL-P0.4 baseline shows it is already happening:
refusal **24/25 (96%)** against grounded **11/15 (73%)**, four of them NPCs denying facts they hold in the
graph. An engine change that made NPCs more evasive would register as an improvement. No Wilson interval,
kappa or McNemar test detects that, because it is a construct-validity failure upstream of all of them.

**Audience ordering (human decision, 2026-08-07): resume/portfolio first, then engine development, then
studio.** This is why EVAL-P13 (writeup + dashboard polish) sits ahead of the engine-development work
(fast subset, regression gate, breadth) rather than last: for a reader who spends five minutes on the repo,
legible rigour — intervals, calibration, an un-gameable headline — is the differentiator, and coverage
across the other 40 engine directories is not. It is also why EVAL-P7 stops being the designated cut.

**Budget (human decision, 2026-08-07): up to ~3 h wall clock for a full run, overnight.** From the P0.4
rates: 95 cases at k=3 is ~62 min; +35 capability cases takes it to ~85 min; 6-8 measured multi-turn
scenarios at k=3 must fit in the remaining ~90 min, and EVAL-P12.1 measures whether they do before anything
depends on it.

### Phase EVAL-P9 — Capability battery: make the headline un-gameable
**Goal:** ~35 new `case_pos_*` so the capability rate has a denominator comparable to the guard battery,
and an evasive engine visibly loses points instead of silently gaining them.
**Effort:** ~1.5 h harness + **4-5 h of your authoring** (the second number is the real cost)
**Constraint:** Case content is yours. A case encodes what an NPC *should* say, which is a product decision
no unattended session can make. The loop's job is to remove the mechanical 80% — finding which facts each
NPC can legitimately speak to — not to invent intent.
**Notes:** New cases change `golden_set_version` (EVAL-P1.5), so runs before and after are **not** directly
comparable and `compare` will correctly refuse to pretend otherwise. Land the whole battery in one commit so
there is exactly one discontinuity, and record the pre-battery baseline `gen_id` next to it.
**Depends on:** EVAL-P6.1, EVAL-P6.4.

- [x] **EVAL-P9.1** Capability case contract + coverage rule. Files: `create docs/CAPABILITY_CASES.md`,
      `create tests/unit/evals/test_capability_coverage.py`.
      Define what a `case_pos_*` asserts: a fact the NPC demonstrably holds (KNOWS_ABOUT, BELIEVES, a memory,
      a witnessed event, or a goal), a player message that legitimately elicits it, and an expectation that
      fails on refusal as well as on fabrication. Add a coverage test: every Character with at least one
      grounded knowledge edge in the demo world has at least one capability case.
      RED anchor: `tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case`
      fails — 7 capability cases cannot cover the seeded NPCs.
      Validation: the test names the specific uncovered NPCs rather than reporting a bare count, so the
      output is a work list. ✅ AUTO ⚠️ UNVERIFIED (EVAL-P9.1, deliberate work-list test: 9 demo NPCs uncovered until EVAL-P9.3 authoring session, 2026-08-08)

- [x] **EVAL-P9.2** Draft generator over the graph. Files: `create evals/case_drafts.py`,
      `create tests/unit/evals/test_case_drafts.py`, `edit evals/__main__.py`, `edit Makefile`.
      For each (NPC, grounded fact) pair reachable over the graph API, emit a **draft** YAML case into
      `evals/cases/_drafts/` with the npc_id, the grounding edge, a generated player message and a
      `keyword_any` expectation seeded from the fact's own tokens. Drafts are never loaded by the runner.
      RED anchor: `tests/unit/evals/test_case_drafts.py::test_draft_is_written_to_drafts_dir_not_cases_dir` fails.
      Validation: a fixture graph with 3 NPCs and 5 grounded facts yields 5 drafts, each naming its grounding
      edge in a `# grounded_by:` comment; `_load_cases` still returns exactly the promoted cases and never a
      draft; running twice is idempotent. ✅ AUTO (EVAL-P9.2, 2026-08-08)

- [ ] **EVAL-P9.3** *(live; requires the seeded stack)* Generate the drafts, then **review and promote ~35**
      into `evals/cases/`. This is the authoring session — edit the player message, tighten the expectation,
      delete the drafts that are not worth a case, and add a `tone_judge` or `affirms_judge` expectation
      where a keyword check would be gameable. Aim for the split `neg 24 / adv 13 / pos ~42`.
      Validation: `make eval` loads the promoted cases with no schema errors; the EVAL-P9.1 coverage test is
      green; `golden_set_version` changes exactly once, in one commit, with the pre-battery `gen_id` recorded
      in the commit message.
      **This task is for a human session. The unattended loop must not start it.**

- [x] **EVAL-P9.4** `capability_rate` as a first-class metric. Files: `edit evals/summary.py`,
      `edit evals/case_stats.py`, `edit tests/unit/engines/test_eval_summary.py`.
      Classify every case as `guard` or `capability` from its id prefix and grounding, and compute both rates
      with their own Wilson intervals and denominators. Do **not** average them into one score — the whole
      point is that they move in opposite directions under evasion.
      RED anchor: `tests/unit/engines/test_eval_summary.py::test_capability_and_guard_rates_are_reported_separately` fails.
      Validation: a fixture with 40 guard and 42 capability cases reports two rates, two n's and two
      intervals; a case that matches neither classifier raises rather than being silently dropped into either. ✅ AUTO ⚠️ UNVERIFIED (EVAL-P9.4, confirmed regression: tests/unit/evals/test_capability_coverage.py::test_every_grounded_npc_has_a_capability_case (pre-existing from EVAL-P9.1 [66be773], not introduced by this task), 2026-08-08)

### Phase EVAL-P10 — Paired headline and the evasion gate
**Goal:** Make the trade visible and mechanical: no guard number is ever printed without its capability
counterpart, and a run that buys guard points with capability points is called a regression.
**Effort:** ~1.5 h
**Constraint:** Pure reporting and comparison logic over artifacts that already exist. No new live runs.
**Depends on:** EVAL-P9.4, EVAL-P8.2.

- [x] **EVAL-P10.1** Refuse to emit an unpaired headline. Files: `edit evals/summary.py`, `edit evals/report.py`,
      `edit tests/unit/engines/test_eval_summary.py`.
      `format_summary_lines` renders guard and capability adjacent, each with k, n and interval, and raises
      when asked to render a summary carrying only one of them.
      RED anchor: `tests/unit/engines/test_eval_summary.py::test_summary_without_capability_rate_raises` fails.
      Validation: the rendered report contains both rates within the same block; no code path can produce a
      report quoting the guard rate alone. ✅ AUTO (EVAL-P10.1, 2026-08-08)

- [x] **EVAL-P10.2** Evasion regression rule in `compare`. Files: `edit evals/compare.py`,
      `edit evals/paired_stats.py`, `edit tests/unit/evals/test_compare.py`.
      Add `verdict: "regression_evasion"` when capability falls while guard rises, evaluated on the paired
      per-case table rather than on the headline rates, so it survives a changed case set.
      RED anchor: `tests/unit/evals/test_compare.py::test_capability_down_guard_up_is_called_evasion` fails.
      Validation: a fixture where 6 capability cases regress and 4 guard cases improve reports
      `regression_evasion` **even though the total pass count rose** — the exact shape that would otherwise
      read as progress. ✅ AUTO (EVAL-P10.2, 2026-08-08)

- [x] **EVAL-P10.3** Over-refusal rate on grounded cases. Files: `create evals/refusal_rate.py`,
      `create tests/unit/evals/test_refusal_rate.py`.
      Score the 16 grounded anti-hallucination cases plus the capability battery for refusal-when-grounded,
      using the existing `refusal_judge`, and report it with its interval next to the other two rates.
      RED anchor: `tests/unit/evals/test_refusal_rate.py::test_grounded_refusal_is_counted_as_a_failure` fails.
      Validation: replaying the P0.4 grounded set reproduces **4/15 over-refusals** — the number this metric
      exists to have caught, checked against a recorded fixture rather than a live run. ✅ AUTO (EVAL-P10.3, 2026-08-08)

### Phase EVAL-P11 — Calibration follow-through: act on kappa
**Goal:** Turn the EVAL-P5 calibration artifact from a number you have into a decision you made.
**Effort:** ~2 h, **plus a re-adjudication sample if any scorer fails its threshold**
**Constraint:** This phase is *conditional on the measured kappa values*. If every scorer clears the
threshold, most of it collapses to writing that down. Do not pre-build remediation for a scorer that turns
out to be fine.
**Notes:** Program 1 measures scorer trust and stops. A calibration artifact that never changes a scorer is
an expensive way to feel rigorous. The P0.4 run already produced one confirmed judge false positive
(`case_neg_injection_001`, ISSUE-129) and a judge disagreement that flips the headline between "0" and "1".
**Depends on:** EVAL-P5.5, EVAL-P5.6, and a completed adjudication pass.

- [ ] **EVAL-P11.1** Threshold policy. Files: `create docs/SCORER_TRUST_POLICY.md`,
      `create tests/unit/evals/test_trust_policy.py`.
      State, before looking at the numbers, what kappa licenses what claim — e.g. below 0.60 a scorer's rate
      may be shown but not published; below 0.40 it is not shown at all. Encode it as a function so a report
      cannot quote a rate its own calibration does not support.
      RED anchor: `tests/unit/evals/test_trust_policy.py::test_low_kappa_scorer_cannot_be_published` fails.
      Validation: a scorer at kappa 0.35 is refused publication by the policy function and the refusal names
      the scorer, its kappa and its interval.

- [ ] **EVAL-P11.2** ⏸️ *(blocked: needs adjudicated kappa — no calibration labels exist yet)*
      Remediate the failing scorers. Files: `edit src/npc_engine/prompts/eval/*.yaml`,
      `edit tests/unit/evals/test_calibration.py`.
      For each scorer below threshold, rewrite its criteria (prompt-only change, versioned in `prompts/`),
      then re-label and re-adjudicate a ~30-row sample for that scorer alone and confirm kappa moved.
      Validation: the re-adjudicated sample shows a higher kappa with a non-overlapping lower bound, or the
      change is reverted and the scorer is recorded as unfixed rather than quietly kept.

- [ ] **EVAL-P11.3** ⏸️ *(blocked: needs two judged transcripts adjudicated against your verdicts)*
      Settle the judge on evidence (**closes ISSUE-129**). Files: `edit evals/judge_config.py`,
      `edit project-harness/DECISIONS.md`.
      Judge one adjudicated transcript with both `mixtral:8x7b` and `qwen2.5:14b`, compute each judge's kappa
      against your verdicts, and pick the winner in a DECISIONS entry naming both numbers.
      Validation: the decision cites two kappas with intervals and n; ISSUE-129 moves to the archive; the
      chosen judge becomes the documented default and every prior headline is annotated with which judge
      produced it.

### Phase EVAL-P12 — Measured multi-turn: promote the differentiator
**Goal:** Turn 6-8 binary e2e scenarios into rates with intervals, so gossip propagation, grief persistence
and reputation drift — the things the engine is actually *for* — produce numbers instead of a green tick.
**Effort:** ~3 h build + measured live time (EVAL-P12.1 determines it)
**Constraint:** **Reset strategy is `preconditions.reset_world()` per repetition (human decision,
2026-08-07).** Its completeness is *unverified*: it restores what `WorldBaseline` knows about, and anything
a scenario mutates outside that — emotion store, session cache, tick counter — survives into the next
repetition and correlates the repeats. EVAL-P12.1 exists to find that out before any interval is computed
over it. If reset is incomplete, the honest output is sequences without intervals, not intervals anyway.
**Notes:** The two worlds use different vocabularies — `scenario_gossip_chain` drives `npc_1`, `npc_6`,
`loc_market`, while `evals/` drives `aldric_merchant`, `old_henryk`, `market_square`. Reconciling them is
real work and is EVAL-P12.2, not a footnote.
**Depends on:** EVAL-P2.2 (`CaseStat`), EVAL-P1.6 (judged records), EVAL-P6.4.

- [ ] **EVAL-P12.1** *(live; requires the seeded stack)* Measure what `reset_world` actually clears.
      Files: `create e2e/scripts/measure_reset_fidelity.py`, `create docs/RESET_FIDELITY.md`.
      Run a mutating scenario, reset, and diff the full graph plus every in-process store the API exposes.
      Enumerate exactly what survives, and time the reset.
      Validation: a table of surviving state with a verdict per item (acceptable / correlates repeats), and a
      measured per-reset cost feeding the EVAL-P12.4 budget. **If anything material survives, EVAL-P12.4
      reports sequences and no Wilson intervals** — computing intervals over correlated trials is precisely
      the error this whole programme exists to stop.
      **This task is for a human session. The unattended loop must not start it.**

- [ ] **EVAL-P12.2** Reconcile the two world vocabularies. Files: `create evals/world_map.py`,
      `create tests/unit/evals/test_world_map.py`.
      A declarative mapping from scenario ids (`npc_1`, `loc_market`) to eval-world ids
      (`aldric_merchant`, `market_square`), so one measured scenario can run against the seeded eval world.
      RED anchor: `tests/unit/evals/test_world_map.py::test_unmapped_scenario_id_raises` fails.
      Validation: an unmapped id raises and names it; the mapping is total over the 6-8 promoted scenarios,
      asserted by a test that enumerates their ids rather than trusting the map to be complete.

- [ ] **EVAL-P12.3** Sequence runner. Files: `create evals/sequence_runner.py`,
      `create tests/unit/evals/test_sequence_runner.py`.
      Run one scenario k times with `reset_world` between repetitions, recording per-repetition outcome,
      duration and the reset cost. Reuses `CaseStat` so flakiness classification comes free.
      RED anchor: `tests/unit/evals/test_sequence_runner.py::test_reset_is_called_between_every_repetition` fails.
      Validation: with k=3 against a mock, reset is invoked exactly 3 times and never *after* the last
      repetition; a scenario that throws mid-run records a failed repetition rather than aborting the set.

- [ ] **EVAL-P12.4** *(live; wall-clock budget comes from EVAL-P12.1's measurement)*
      Promote 6 scenarios and report their rates. Files: `edit evals/sequence_runner.py`,
      `edit Makefile`, `create tests/unit/evals/test_sequence_rates.py`.
      Start with `gossip_chain`, `grief_persistence`, `reputation_drift`, `memory_consolidation`,
      `time_passage`, `mood_contagion` — chosen because each maps to a claim a studio would ask about.
      RED anchor: `tests/unit/evals/test_sequence_rates.py::test_scenario_rate_carries_k_and_interval` fails.
      Validation: output reads like `gossip reaches the 2-hop target 13/15 (k=3) [0.621, 0.963]`, with k
      adjacent to every rate, and the run fits the remaining wall-clock budget measured in EVAL-P12.1.

### Phase EVAL-P13 — The portfolio artifact
**Goal:** Make the rigour legible in five minutes to someone who will never run the suite.
**Effort:** ~2.5 h
**Constraint:** Nothing new is measured here. If a number is not already produced by EVAL-P9..P12, it does
not go in. The failure mode of this phase is inventing a metric to have something to show.
**Notes:** Ordered ahead of the engine-development tier by the audience decision of 2026-08-07. The pitch is
not "the engine scores well" — it is "the engine is measured honestly", which is rarer and, for this reader,
worth more. Every headline carries n, k, judge and an interval; every known limit is stated rather than
omitted.
**Depends on:** EVAL-P7.3, EVAL-P9.4, EVAL-P10.1, EVAL-P12.4.

- [ ] **EVAL-P13.1** Methodology writeup. Files: `create docs/EVAL_METHODOLOGY.md`.
      One page per technique, each with *why the naive alternative is wrong*: Wilson over normal approximation
      at small n; exact McNemar over chi-squared at 53 cases; kappa with a bootstrap CI over a bare kappa;
      `evaluated_cases` over `total_cases`; capability paired with guard. Include the anti-metric section —
      what this suite cannot see (pronouns, unnamed fabrications, single-turn only, one judge).
      Validation: every claim links to the module that computes it and the test that pins it; a reader can
      check any number without running anything.

- [ ] **EVAL-P13.2** ⏸️ *(blocked: needs a real run artifact to render)* Dashboard headline card. Files: `edit evals/dashboard/templates/run_detail.html`,
      `edit evals/dashboard/app.py`, `edit tests/unit/evals/test_dashboard_detail.py`.
      One card carrying the paired rates with intervals, the per-scorer kappa badge, the judge name and the
      run config block — the screenshot that goes in the README.
      RED anchor: `tests/unit/evals/test_dashboard_detail.py::test_headline_card_shows_both_rates_and_judge` fails.
      Validation: the card renders both rates, both n's, k, the judge model and the git SHA; a run whose
      calibration does not license publication renders the EVAL-P11.1 refusal in place of the rate.

- [ ] **EVAL-P13.3** ⏸️ *(blocked: every README number must be copied from a committed artifact,
      never typed — none exist yet)* README metrics section. Files: `edit README.md`.
      The headline block, the dashboard screenshot, and a three-line honest-limits note. Link the
      methodology doc.
      Validation: every number in the README appears verbatim in a committed report artifact; no figure is
      hand-typed, and a stale-number check names any that drift.

### Phase EVAL-P14 — Multi-turn track v2: the separate schema (bones)
**Goal:** The design, not the build. A specification complete enough that a later session can implement it
without re-deciding anything — because EVAL-P12 deliberately bends the single-turn schema to fit sequences,
and that bend has a known breaking point.
**Effort:** ~2 h of design; the implementation is its own multi-week programme and is **not** scoped here.
**Constraint:** Produces documents and one schema module. No runner, no dashboard, no migration.
**Notes:** EVAL-P12 works because six scenarios can be squeezed into a record shape built for single turns.
It stops working when a scenario needs per-turn retrieval capture, per-turn judging, or branching. Writing
the v2 schema now, while the constraints are fresh from P12, costs 2 h; writing it after P12's compromises
have hardened into five call sites costs far more.
**Depends on:** EVAL-P12.4 (the compromises must be real before they can be designed away).

- [ ] **EVAL-P14.1** Sequence transcript schema. Files: `create docs/SEQUENCE_SCHEMA.md`,
      `create evals/sequence_records.py`, `create tests/unit/evals/test_sequence_records.py`.
      Frozen Pydantic: `SequenceRun(run_id, scenario_id, k, config, repetitions)`,
      `Repetition(index, reset_receipt, turns)`, `Turn(index, actor, message, response, world_epoch, tick,
      retrieved_context, duration_ms)`. `reset_receipt` records what the reset actually cleared, from
      EVAL-P12.1 — so every repetition carries its own independence evidence rather than assuming it.
      RED anchor: `tests/unit/evals/test_sequence_records.py::test_repetition_without_a_reset_receipt_raises` fails.
      Validation: a 3-repetition, 5-turn run round-trips; a repetition missing its receipt raises; the model
      is frozen and carries no field the harness cannot populate.

- [ ] **EVAL-P14.2** Independence and statistics policy. Files: `create docs/SEQUENCE_STATS_POLICY.md`.
      State which statistics are valid under which reset fidelity: full reset permits Wilson and McNemar;
      partial reset permits sequence reporting and order-effect tests only. Include the order-effect check
      (does repetition 3 systematically differ from repetition 1) as the empirical test of the assumption.
      Validation: the policy names, for each metric the dashboard can render, the reset fidelity it requires
      — so an incomplete reset downgrades the output automatically rather than by remembering to.

- [ ] **EVAL-P14.3** ⏸️ *(blocked: the model is validated against EVAL-P12.4's measured run time)*
      Cost model and migration note. Files: `edit docs/SEQUENCE_SCHEMA.md`.
      Wall-clock model as a function of scenarios x k x turns x reset cost, using EVAL-P12.1's measured
      numbers, and the explicit list of what EVAL-P12 would have to give up to migrate. State the trigger
      condition for starting the build — e.g. more than 10 scenarios, or the first scenario needing per-turn
      judging — so the decision is made by a condition rather than by enthusiasm.
      Validation: the model predicts EVAL-P12.4's measured run time within 25%; if it cannot, the model is
      wrong and the schema built on it is suspect.

<!-- LOOP:QUEUE end -->
<!-- ^ MOVED HERE 2026-08-07: Program 2 (EVAL-P9..P14) is released to the overnight loop.
     Everything below this marker is human-session work and is structurally unreachable
     at 3am — Parked, Post-program milestones, REORG PR-9, the Next/Next+1 programs and
     the two open bullets inside "## Completed" all live here.

     Program 2 is released with EIGHT tasks deliberately flagged, because the loop skips
     flagged tasks without blocking and would otherwise drain a whole programme of code
     against inputs that do not exist — finishing the night having measured nothing, the
     exact failure DEC-153 §3 narrowed the original fence to prevent. Flagged and why:
       EVAL-P9.3   authoring — only a human can say what an NPC *should* say
       EVAL-P11.2  needs adjudicated kappa; no calibration labels exist yet
       EVAL-P11.3  needs two judged transcripts adjudicated against each other
       EVAL-P12.1  live stack; measures reset fidelity
       EVAL-P12.4  live stack; budget comes from P12.1
       EVAL-P13.2  needs a real run artifact to render
       EVAL-P13.3  README numbers must be copied from a committed artifact, never typed
       EVAL-P14.3  cost model is validated against P12.4's measured time -->

### Parked (out of budget)

Not compressed into optimistic estimates — genuinely out of scope for this program. Each line says why.

- ~~**`compare` / A-B diff (~1.5 h).**~~ **PROMOTED 2026-08-02 to Phase EVAL-P8** (DEC-153 §4). The original
  reason for parking it — "cannot be tested without two full generations" — was true but not disqualifying:
  the ~4 h is *wall clock*, not build effort, and it buys the only statistic in the program that answers
  whether a change helped. The runtime prompt-version selector it was also blocked on turned out to be
  unnecessary: `compare` reads two saved generation directories and never switches anything at runtime.
- **Required-fact annotation for the remaining 38 dialogue cases (~1.75 h).** Mechanical but large.
  **15 of the 53 are now funded as EVAL-P4.0** (DEC-153 §5) because EVAL-P4.2 has literally no input without
  them; the other 38 widen context recall/precision from a subset to the whole dialogue suite.
- **Golden-set versioning: `added_in` / `retired_in` + intersection diffing (~1 h).** Was parked as "only pays
  off once `compare` exists". `compare` now exists (EVAL-P8), so **this is the first thing to pick up if
  budget frees** — EVAL-P8.2 handles a changed case set by naming the difference, which is correct but manual;
  versioning makes it automatic.
- **LLM `seed` support (~1 h).** `LLMGenerateProtocol.generate()` has no `seed` and `ollama_adapter.py` never
  sets `options.seed`. Adding it changes a Protocol shared by three adapters → ask-gate. Until then `RunConfig`
  **honestly omits seed** and the report says runs are `temperature=0.15`, not deterministic.
- **Judge-noise vs system-noise split (~1 h).** Genuinely uncommon and cheap to code once the loop exists —
  but each measurement costs another ~115 `mixtral` calls, which the budget cannot absorb.
- **Deleting the seven legacy make targets (~0.5 h).** Deliberately after EVAL-P6, once nothing references them.
- **`evals/` under `mypy` + `check-docstrings` (~1 h).** Unbounded until EVAL-P0.3's ruff pass reveals the true
  violation count in the 13 existing modules.
- **Judge-cost reduction (~1 h, high value).** `runner._guard_expectations` injects **both** a `tone_judge` and
  an `affirms_judge` into all 37 demo guard cases — that is why the suite costs 115 judge calls per run rather
  than ~41. Merging or gating the two injected judges is the single largest cost lever in the suite and it is
  free. **Decide at EVAL-P0.4 (DEC-153 §9).** The old promotion condition — *"if EVAL-P0.4's measured timings
  come in worse than expected"* — was circular while the loop fence let P1..P7 run ahead of P0.4, which never
  executed. With the fence narrowed to EVAL-P0, **P0.4 now runs before anything that spends judge calls**, so
  the condition is executable as written. Preference order if it fires: **gate** the second judge (run it only
  conditionally — ~50–70 % saving, semantics unchanged) over **merging** the two into one prompt (~65 %, but it
  changes what the 37 guard cases measure and would break comparability with the Stage-A baseline).

### Post-program milestones

Not parked — **deferred with intent**, to be scheduled after EVAL-P5 lands and the artifact schema stops moving.

- **Publishable extraction (~2 h): 8-case synthetic fixture set + README methodology section + committed
  example artifacts.** Promoted out of Parked to its own milestone 2026-08-02 (DEC-153 §6). The src-free
  constraint is enforced in every phase of this program, so the tax is already being paid; this is the only
  thing that buys the benefit. **Decision point: after EVAL-P5.4.** Writing it earlier means rewriting it
  when the schema shifts. Note the honest scope: `evals/` is *import*-free, not *engine*-free (EVAL-P3 fetches
  vocabulary over HTTP, EVAL-P1.1 reads engine YAML by path), so the publishable artifact is the **harness +
  schemas + synthetic fixtures + methodology**, not a suite a stranger can point at their own engine.

**Batching for `/expand-next`:** EVAL-P0 is one session (P0.1 is done; P0.3 is an ask-gate and P0.4 is a live
run, so **both need a human session** — see the fence note below). EVAL-P1 is its own session (4 steps, one
commit each). EVAL-P2 + EVAL-P4 fit one session together (P4 now has 3 steps — P4.0 is annotation, not TDD).
EVAL-P3 is its own session. EVAL-P5 is one session **plus** 4–6 h of offline adjudication. EVAL-P6 is one
session. EVAL-P7 is one session — and is the cut if anything before it overruns. EVAL-P8 is one session and
is **not** a cut candidate.

**Loop fence state (DEC-153 §3, updated 2026-08-06):** the `<!-- LOOP:QUEUE end -->` marker now sits **just
above "### Parked (out of budget)"**, so the queue spans **EVAL-P0..EVAL-P8** and the overnight loop can reach
every open task in this program. It moved because the reopen condition fired: EVAL-P0.4 (live baseline) and
EVAL-P0.3 (ask-gate, lint scope) were both ticked by human sessions on 2026-08-06. EVAL-P0 is now complete —
`compute_next` will start at EVAL-P1.1. Everything below the marker (Parked, Post-program milestones, PR-9,
the Next / Next+1 programs) stays unreachable to an unattended session, which is the point of keeping the
fence rather than deleting it.

**Ordering against other programs:** nothing competes. `REM-W0..W8` is fully drained; `REORG-PR6..PR8` shipped
and `PR-9` is optional/deferred; `P0`/`INTEG` are complete and `P1`/`P2` moved to `UNREAL_DEFERRED.md`. Of the
`Next+1` block, `EVAL-01` (per-stage latency timer, in-engine) stays independent and still gates `PERF`;
**`EVAL-05` (engine-quality eval expansion) is superseded by this program** and should be struck when reached.
**`EVAL-02` and `EVAL-04` are NOT superseded** — they are rescoped as the multi-turn / cross-session program
(DEC-153 §8), which measures the thing this program deliberately does not: whether an NPC remembers you across
sessions. `EVAL-03` folds into the Parked LLM-`seed` work, which is its real prerequisite.

---

## Active — Folder reorganisation (REORG-PR6..PR9)

> Branch: `refactor/folder-reorg`. Full per-PR details, exact file lists, and domain tables:
> **`~/.claude/plans/review-the-codebase-and-greedy-thimble.md`**.
> **PRs 1–5 committed** — `api/routes/` (a9a7d0b), `api/` (3d18596), `retrieval/` (88b9333),
> `demo_game/ui/` (0c18a6a), `demo_game/` (827212d).
> Verification per PR: `make test` (2542 passed + 8 pre-existing ISSUE-119 skips) +
> `make test-demo` (1093 passed) + `make check-layers`. Facade `__init__.py` pattern throughout.

- [x] **PR-1** `src/npc_engine/api/routes/` → 8 domain sub-packages; single wiring file `router_registry.py` updated. ✅ a9a7d0b
- [x] **PR-2** `src/npc_engine/api/` → `errors/`, `helpers/`, `dashboard/` sub-packages; `dependencies.py` re-exported from new `wiring/` sub-package. ✅ 3d18596
- [x] **PR-3** `src/npc_engine/retrieval/` → `context/`, `embedding/`, `graph_rag/`, `dialogue_context/`. ✅ 88b9333
- [x] **PR-4** `demo_game/ui/` → `panels/`, `boards/`, `widgets/`, `layout/`. ✅ 0c18a6a
- [x] **PR-5** `demo_game/` root → `pollers/` (17), `beats/` (3), `workers/` (1), `seeds/` (2), `branches/` (3), `runners/` (3). Makefile `demo-run` updated to `demo_game.runners.run`. ✅ 827212d
- [x] **PR-6 `src/npc_engine/graph/`** — the big one. ✅ 2026-06-23. 130 modules → 24 domain sub-packages (`gossip/ faction/ political/ quest/ reputation/ economy/ knowledge/ intrigue/ character/ needs_goals/ relations/ event/ location/ scheduling/ military/ emotion/ memory/ intent/ narrative/ idempotency/ group/ world_state/ generic/ infra/`); root slimmed 136 → 5 facades (`graph_reader`, `graph_writer`, `graph_admin_service`, `graph_edit_validator`, `graph_rag_queries`). Convention = full-path imports (matches PR-3), one commit per domain, `rules_baseline.txt` paths rewritten in-PR, conformance + SEV-04 path assertions updated. 2533 tests pass; 0 new lint/check-rules/layer violations. Pre-existing gate red (PR-2/3 lint+baseline drift; anti_hallucination WIP) logged as ISSUE-120/121.
- [x] **PR-7 `tests/unit/`** — 345 files → 9 mirror-source subdirs (`conformance/`, `api/`, `engines/`, `graph/`, `retrieval/`, `llm/`, `world/`, `config/`, `setup/`; `utils/` pre-existing). `__init__.py` per new subdir. Makefile `smoke`/`test-v14-*` paths updated. Path assertions in `test_architecture_conformance`, `test_check_layers`, `test_docstring_audit` + 14 other files updated (depth +1). 2533 tests pass; 8 pre-existing ISSUE-121 failures unchanged. ✅ 2026-06-23.
- [x] **PR-8 `demo_game/tests/`** — 78 files → 6 mirror-source subdirs (`ui/`, `pollers/`, `beats/`, `scenarios/`, `core/`, `seeds/`). `conftest.py` stays at tests root. `__init__.py` per new subdir. Path assertion in `test_sev37_demo_hygiene.py` updated (depth +1). 1093 demo tests pass. ✅ 2026-06-23.
- [ ] **PR-9 (optional) `graph/repositories/`** — 39 files → mirror the PR-6 domain split. Defer until PR-6 lands and navigation need is confirmed.

**Batching for `/expand-next`:** PR-6 is a session on its own (domain-by-domain sweep). PR-7 + PR-8 are mechanical moves that can run in a single session. PR-9 is optional cleanup.

---

## Active — ISSUES.md remediation program (REM-*)

> Drains the open `project-harness/ISSUES.md` backlog. Full file-level plan with rationale and the
> user-approved design decisions: **`~/.claude/plans/go-through-the-issues-md-frolicking-yao.md`**.
> Decisions baked in (from planning Q&A, 2026-06-19): ISSUE-071 = full SystemStateContext slice;
> ISSUE-107 = add `memories_recalled` to `DialogueResponse`; ISSUE-112 = wire `src_character_id`
> actor onto events; engine slices 094/096/097/108 all in scope; ISSUE-105 = split
> `dependencies_engines` into submodules; ISSUE-104 = all 5 OCP residuals; ISSUE-083 deferred;
> ISSUE-051 (WONTFIX) + ISSUE-092 (Redis, blocked on Unity phase) excluded.
> **Sequencing:** safe hygiene → tests → size limits → OCP → engine slices → headline features.
> Each wave is independently committable; close each issue (`[FIXED]` + move to
> `archive/ISSUES_RESOLVED.md`) and log non-obvious choices in DECISIONS.md as it lands.

- [x] **REM-W0/W1a (done 2026-06-19)** — ISSUE-056, 064, 072, 076 archived (already fixed in code);
  ISSUE-106 (`inspect.iscoroutinefunction`), ISSUE-109 (local `_KNOWLEDGE_STATE_KNOWS`), ISSUE-098
  (shared `get_player_location_reader`/`get_relation_reader` singletons). All verified green.
- [x] **REM-W1b — docstring sweep** — ISSUE-103/115: replace `Purpose: (auto-detected — review)` across
  113 `src/npc_engine/` files (graph 22, engines 16, type_registry 13, retrieval 13, schema 11, api 11, …)
  with accurate one-liners; add a `check-docstrings` guard rejecting the placeholder. Grep returns zero when done.
  **✅ 2026-06-19:** 73 files updated (40 already fixed in prior sessions); `docstring_audit.py` guard added;
  5 unit tests green; `make check` 86.11% cov. Closes ISSUE-103/115.
- [x] **REM-W2 — stale tests + coverage** — ISSUE-116 (`test_seed_chain_quests` assertions),
  ISSUE-111 (`scenario_territorial_war` MilitaryEngine ctor), ISSUE-101 (`schedule_queries` tests),
  ISSUE-110 (`evals/runner` HTTP-loop tests), ISSUE-102 (scheme-board panel behavioral assertions).
  **✅ 2026-06-19:** fixed always-upsert skip assertions (116); rewrote stale military tick test to real
  contract (111); 13 new schedule_queries unit tests (101); 9 eval runner HTTP-loop/main() tests (110);
  9 behavioral draw assertions for scheme board panel (102). `make check` 86.81% cov.
- [x] **REM-W3 — size limits** — ISSUE-114 (split 3 >40-line fns in `quest_reward_repository`),
  ISSUE-105 (split `dependencies_engines.py` into a package, mirror `dependencies_advanced/`),
  then ISSUE-095 (hoist `get_proactive_queue` import once the split breaks the cycle).
  **✅ 2026-06-19:** extracted 4 helpers from quest_reward_repository (114); split monolith into
  dependencies_engines/{core,quest,tick_slots}/__init__ (105); hoisted get_proactive_queue import (095).
  2 R006 + 1 R001 entries removed from baseline (136 grandfathered). All 2491 tests pass, 86.83% cov.
- [x] **REM-W4 — OCP residuals** — ISSUE-104: registries/enums for emotion-model factory, TTS backend,
  shared mood→VAD table, LLM `__init__` self-registration, `SchemeStepKind` enum (mirror `register_backend`).
  **✅ 2026-06-19:** emotion registry (`register_emotion_model`/`registered_emotion_models` + dispatcher);
  `engines/tts/factory.py` TTS registry (`register_tts_backend`/`build_tts_client`); `MOOD_LABEL_TO_VAD`
  exported from `emotion_state` (removed local dup in `mood_contagion_engine`); `SchemeStepKind(str,Enum)` in
  `covert_event_factory`; `config.py` `Literal` → `str` + registry validators for both. 14 new unit tests.
  2505 passed, 86.87% cov. Closes ISSUE-104.
- [x] **REM-W5 — engine slices** — ISSUE-112 (event actor + WITNESSED; node-schema change),
  ISSUE-108 (atomic `advance_step` via `emit_scheme_step_atomic`), ISSUE-097 (in-memory plateau tracker),
  ISSUE-096 (per-NPC traits via existing `trait_service`/`trait_queries` into `EmotionUpdater`),
  ISSUE-094 (`need`/`event` proactive trigger producers). Each: regression test + DECISIONS note.
  **✅ 2026-06-19:** ISSUE-112 — `EventTemplate.src_character_id` activates WITNESSED edges (DEC-133);
  ISSUE-108 — `advance_step` routed through `emit_scheme_step_atomic` + `SchemeStepInput` gains event
  fields (DEC-134); ISSUE-097 — in-memory `_plateau_tracker` on `DirectorTick`; no graph writes (DEC-135);
  ISSUE-094 — `_collect_need_candidates` / `_collect_event_candidates` via `IntentGraphPort` injection
  (DEC-136); ISSUE-096 — `TraitReadPort` + `_get_model_for(npc_id)` in `EmotionUpdater` (DEC-137).
  All 5 DECISIONS written; all tests green; `make check` 86.94% cov.
- [x] **REM-W6 — headline features (P2)** — ISSUE-071 (SystemStateContext Tier-0 block: route resolves
  trade/quest facts → `context_builder` + new prompt YAML), ISSUE-107 (`memories_recalled` field +
  two-session memory-recall e2e scenario).
  **✅ 2026-06-19:** ISSUE-071 — `SystemStateContext` Pydantic model + `resolve_system_state` in
  `engines/dialogue/system_state_context.py`; wired through `DialogueContextPort.build_context`,
  `Neo4jDialogueContextAdapter`, `context_builder._build_tier0_items` (priority=97, pinned), and
  `api/routes/dialogue.py`; rule injected via `prompts/dialogue/system_state_v1.yaml` into
  `build_system_prompt` (DEC-138). ISSUE-107 — `memories_recalled: tuple[str, ...]` added to
  `DialogueResponse`; port return type changed to `tuple[str, list[str]]`; `_extract_used_memory_ids`
  in adapter parses JSON; IDs threaded via closure in handler; 5 mock files updated; e2e scenario
  `scenario_memory_recall_e2e.py` written (DEC-139). `make check` green: 2523 passed, 86.88% cov.
- [x] **REM-W7 — demo dry-run** — ISSUE-100 (FIXED 2026-06-22): the failure was a cp1252
  `UnicodeEncodeError` on the ACT-8 `→` cue glyph (printed before the dry_run guard, so live Windows
  runs crashed too), *not* a missing guard. Wired the existing `ensure_utf8_stdout()` into `run.py:main()`;
  regression test `demo_game/tests/test_run_dry_run_encoding.py`. Archived.
- [x] **REM-W8 — rules baseline backlog (P2)** — ISSUE-053 (FIXED 2026-06-22, DEC-140): the named clusters
  (prints/swallows/raise/Cypher-leak/demo-imports) are already cleared; the remainder was only R001 file-size +
  R006 fn-length. "Done = empty" was unreachable without violating prior waivers, so done was redefined to
  "every baseline entry documented-waived; remove only on a real complexity-reducing fix." High-value clear:
  `_emit_tokens_out` DRY consolidation cleared `stream_text` (137 → 136). Remainder catalogued under DEC-140.
  Archived.

---

## Next — Shippable demo game (B2B proof-slice)

> **End goal: license the engine to studios (B2B).** The thing that closes that sale is not a bigger engine
> — it's proof that the (invisible) simulation *carries a real experience players react to*, plus a recognizable
> integration path. So the near-term deliverable is a **small, downloadable, distributable demo game**: a
> ~10-minute experience built on one **legible emergent hook**, with the engine's runtime made shippable to a
> player's machine. **Do NOT grow this into a full game** — it is a proof artifact, instrumented for the pitch.
>
> **Decisions baked in (see DEC-124):**
> - **Dual LLM path.** (A) run the model **locally** (bundle/first-run-install Ollama + a size-tiered model);
>   (B) **bring-your-own API key** + provider choice (works on any machine, no GPU). (A) is the differentiator;
>   (B) is the universal fallback and is nearly free given `LLMClientProtocol` + the factory registry.
> - **Stay on Neo4j for now.** The Neo4j Community **GPLv3** copyleft question for a *bundled, distributed*
>   build is **explicitly deferred** — revisit once a demo actually runs and the licensing question is concrete
>   (commercial license vs. an embeddable Cypher store e.g. Kùzu). Logged as an open decision, not a blocker.
>
> **Sequencing rule:** P0 (deployment + LLM paths — *platform-agnostic*, actionable now) → P1 (the game slice —
> *gated on SHIP-01 platform pick*) → P2 (B2B proof wrap). P0 wastes no work regardless of the P1 platform.

### Phase P0 — Make the runtime shippable + dual LLM path (platform-agnostic)
- **Goal:** a player can run the whole stack (engine + Neo4j + model) from a download, choosing local
  inference **or** an API key on first launch — no Docker, no manual Ollama/model pull, no GPU required for path B.
- **Constraints:** DIP — new LLM backends register via the factory (OCP, no engine edits); auth on all routes;
  the bundled local backend reuses the existing FastAPI app unchanged (the game is still a pure REST/WS client).
- [x] **SHIP-01 (decision)** — pick the game-client platform. **✅ Unity (DEC-125).** Doubles as the studio
  integration reference (a studio can copy the C# REST/WS client; ties into the deferred `Phase X — Unity SDK`).
  Alternatives (web/Ren'Py) rejected: faster to "players react" but not an engine integration proof.
- [x] **SHIP-02 (path B — BYO API key)** — **✅ DEC-126:** `OpenAICompatibleAdapter` (backend `"openai"`)
  behind `LLMClientProtocol`, registered in `engines/llm/factory.py`. One adapter serves OpenAI/OpenRouter/
  Groq/Together/DeepSeek/LM Studio via configurable `OPENAI_API_URL` + player-supplied `OPENAI_API_KEY`;
  model is per-engine. No engine-file edits (pure OCP add). Structured output uses `json_object` mode
  (strict `json_schema` deferred — DEC-126). 18 unit tests green; `make check` green (2 pre-existing
  seed failures unrelated — ISSUE-116).
- [x] **SHIP-03 (path A — local inference)** — first-run flow that installs/launches Ollama and pulls a model
  on demand (resumable), with a **size-tiered** model choice (e.g. 3B/7B/14B) defaulted by detected VRAM.
  Exit: a fresh machine reaches a working local dialogue without the user touching a terminal.
  **✅ DEC-127:** `npc_engine.setup` package (rank-1 peer): `vram_detector` (nvidia-smi), `model_tiers`
  (3B/7B/14B thresholds), `ollama_manager` (is_running/is_installed/launch/pull_model async), `first_run_flow`
  async orchestrator → `FirstRunResult`. `scripts/setup_local.py` CLI entry point. 33 unit tests green.
- [x] **SHIP-04 (backend packaging)** — package the FastAPI engine as a launchable local server the game
  process starts/stops (e.g. PyInstaller), and define the Neo4j launch strategy for an end-user machine
  (Neo4j stays — DEC-124). Exit: double-clicking the game brings up engine + graph + model with no Docker.
  **✅ DEC-128:** detect-and-launch strategy (mirrors SHIP-03 Ollama pattern). `neo4j_manager.py`
  (is_running/is_installed/launch via httpx + subprocess), `stack_launcher.py` (Neo4j → Ollama →
  uvicorn orchestrator), `scripts/launcher.py` (PyInstaller entry point, env-driven Ollama toggle),
  `packaging/npc_engine.spec` (PyInstaller build recipe). `make package` builds the standalone binary.
  19 unit tests green; all gate checks pass.
- [x] **SHIP-05a (wizard backend — P0)** — platform-agnostic data layer for the first-run wizard (DEC-129):
  `wizard_config.py` (`LLMPath` enum + `WizardConfig` Pydantic model + `load_wizard_config` /
  `save_wizard_config` persisting to `~/.npc_engine/wizard_config.json`) and `path_validator.py`
  (async `validate_path_a`: Ollama running + model present; async `validate_path_b`: HTTP probe of
  the configured API endpoint + key). No UI. Exit: config round-trips through JSON; path-A and
  path-B validators return typed results; `make check` green.

### Phases P1 (game slice) + P2 (B2B proof wrap) — **DEFERRED**
> Moved verbatim to **`project-harness/UNREAL_DEFERRED.md`** (2026-07-31). Covers `SHIP-05b..09`
> and `SHIP-10/11`. Step IDs preserved. `SHIP-10`'s latency half lives on as `EVAL-01` below.

### Open decisions for this program (need a `DECISIONS.md` call when reached)
- [x] **OD-Ship-platform** — SHIP-01 resolved to **Unity** (DEC-125): integration-reference dual use.
- [ ] **OD-Ship-graph** — Neo4j GPLv3 resolution for a distributed build. **Direction set (DEC-132):**
  evaluate-and-likely-adopt **Kùzu** (MIT, embedded, no JVM/Bolt) — wins on licensing, footprint/FPS, **and**
  graph latency at once. Gated on a time-boxed porting spike (PERF-04); Cypher-dialect cost over `graph/` is
  the open unknown. (Advances the earlier "deferred until a demo runs" stance — DEC-124.)

---

## Next+1 — Integration readiness → measurement → evidence-gated perf

> Source: 2026-06-19 adversarial roadmap critique (multi-lens, code-grounded). Reshapes three proposed phases
> (setup routes / expanded evals / Python→compiled rewrite). **Hard ordering: INTEG → EVAL → PERF.** INTEG
> lands on `main` before Unity (it unblocks SHIP-05b). EVAL + PERF overlap Unity dev but EVAL precedes PERF.
> **No long-lived rewrite branch** — PERF is incremental on `main`, gated by EVAL's harness.
> Decisions: **DEC-131** (integration bootstrap), **DEC-132** (perf strategy + Kùzu direction).

### Phase INTEG — Integration-ready engine surface (lands on `main`, gates SHIP-05b) ✅ 2026-06-23
- **Goal:** a cold machine + a fresh native-Unity client complete first-run setup and reach a working dialogue
  with no manual key/config step. Completes P0.
- **Constraints:** auth on all non-bootstrap routes; setup routes call `setup/` validators (no logic in route);
  localhost bind; DEC-131 bootstrap.
- [x] **INTEG-01** — `POST /setup/validate` → `validate_path_a`/`validate_path_b` (typed `ValidationResult`);
  `validate_api_url_safety` guards api_url against private/metadata IPs + http-external SSRF. ✅ f8c2dc6
- [x] **INTEG-02** — `GET/POST /setup/config` → `load_wizard_config`/`save_wizard_config`, round-trips
  `~/.npc_engine/wizard_config.json`. ✅ f8c2dc6
- [x] **INTEG-03** — `/setup/*` + `/readiness` auth-exempt in `ApiKeyMiddleware` (DEC-131); localhost-only
  by 127.0.0.1 bind; `setup_router` registered in `router_registry`. ✅ f8c2dc6
- [x] **INTEG-04** — launcher polls `GET /readiness` (background uvicorn task + `_poll_readiness`); emits
  `NPC_ENGINE_READY` to stdout; `docs/INTEGRATION.md` written (startup sequence, error envelope, auth posture). ✅ f8c2dc6
- [x] **INTEG-05** — no-CORS + plaintext-cloud-key posture documented in `docs/INTEGRATION.md` (§Security posture). ✅ f8c2dc6
- **Effort:** ~1 session. **Blocks:** SHIP-05b.

### Phase EVAL — Multi-turn behaviour + latency harness (precedes PERF; absorbs SHIP-10 latency)
- **Goal:** measure how well the engines behave **and** where time goes — the SHIP-10 pitch numbers + the
  regression net that makes PERF safe. Additive (new files) → `main`/short branches.
- **Rescoped 2026-08-02 (DEC-153 §8).** This block is **not** superseded by the `EVAL-P0..P8` pipeline; the two
  are complementary and the overlap is now resolved item by item. `EVAL-P0..P8` measures **single-turn**
  quality. This block owns **cross-session and multi-turn** behaviour — which is what a studio buyer actually
  asks about ("does the NPC remember me next week"), and which nothing in the pipeline touches.
- [ ] **EVAL-01** — per-stage latency timer in `dialogue_handler` + `context_builder` (LLM / graph groups /
  assembly); p50/p95 + RAM-by-process; **split interactive (dialogue/trade) vs background, cold-start isolated.**
  Absorbs SHIP-10's latency half. Exit: a real per-turn breakdown on the floor PC.
- [ ] **EVAL-02** — golden-transcript regression suite (mock LLM) for dialogue/gossip/emotion/quest. Exit: a
  behavior-altering change fails a test. **Still live** — `EVAL-P1`'s transcript schema and `EVAL-P3`'s
  LLM-free scoring pass are *inputs* to this, not replacements: a scoring pipeline is not a regression net.
  Build it on the v2 transcript rather than inventing a second format.
- [ ] ~~**EVAL-03**~~ — content-determinism pin (same seed ⇒ same distortion/quest content). **Folded into the
  Parked "LLM `seed` support" item** (DEC-153 §8): `LLMGenerateProtocol.generate()` has no `seed` and
  `ollama_adapter.py` never sets `options.seed`, so the pin is unbuildable for LLM-generated content until
  that lands. The non-LLM half already exists as the SEV-22 RNG test.
- [ ] **EVAL-04** — memory-recall-over-time eval (tick-N retention of tick-M facts). **Still live, and the
  highest-value item in this block** — it is the only planned measurement of the engine's headline claim
  (persistent memory) and the pipeline program explicitly does not cover it.
- [ ] ~~**EVAL-05**~~ — engine-quality eval expansion. **Superseded by `EVAL-P0..P8`** — struck 2026-08-02.
- **Effort:** ~2-3 sessions. **Blocks:** PERF.

### Phase PERF — Evidence-gated performance (incremental on `main`, after EVAL; DEC-132)
- **Goal:** cut felt interactive latency + RAM/FPS contention by the highest-leverage means, verified against
  EVAL's harness. Optimise the interactive path; leave background sim slow-but-throttled. Compiled core only if profiled.
- **Constraints:** every step gated by EVAL-01 numbers + green golden transcripts; no long-lived branch.
- [ ] **PERF-00** — preload the model at stack launch (warmup call in `stack_launcher.py`) → kills the
  first-dialogue cold-start spike. Cheapest, biggest felt win.
- [ ] **PERF-01** — stream first token: interactive client uses the existing WS `chunk` path, not the blocking
  sync `/dialogue` → perceived latency = time-to-first-token.
- [ ] **PERF-02** — `asyncio.gather` the independent graph reads in `context_builder.py:516-534`.
- [ ] **PERF-03** — cache improvement (raise hit-rate / warm cold path) — the "after-refactor" work, pulled first.
- [ ] **PERF-04** — Kùzu evaluation → likely adoption (DEC-132 / OD-Ship-graph): time-boxed porting spike;
  measure RAM (no JVM) + latency (no Bolt) + dialect cost. Exit: go/no-go with numbers.
- [ ] **PERF-05** — throttle/de-prioritize background ticks (`MAX_CONCURRENT_TICKS` + wider intervals) so sim
  never contends with render or dialogue.
- [ ] **PERF-06** — model-tier/VRAM tuning for the floor PC (16 GB RAM / 8-12 GB VRAM; 7B realistic at 8 GB VRAM).
- [ ] **PERF-07** — selective PyO3/Rust extension of ONE proven CPU-bound hot function — **only if** EVAL-01
  shows a meaningful CPU-bound share. Keep the Python architecture/tests/DI. **Not a wholesale rewrite** (DEC-132).
- **Note (trade path):** the trade *mechanic* (`trade_engine.py`, `trade_handler_sync.py`) is deterministic
  pricing + atomic graph transfers, **no LLM** → follows the graph wins (PERF-02/03/04), not preload/stream;
  conversational *bartering* is the normal dialogue turn with negotiation context injected
  (`negotiation_context.py`) and inherits PERF-00/01.
- **Effort:** ~3-5 sessions for 00-06; PERF-07 optional/open-ended. **Depends on:** EVAL-01/02/03.

---

## Completed ✅ — Phases F/G/H (slice-2: activate → surface → make-it-a-game, 2026-06-11→12)

> The Phase A–E program built each capability as a **slice 1** (engine logic + graph + tests, mostly
> new-file-add) but deliberately deferred the **wiring** (scheduler tick / composition-root injection /
> WS delivery) and the **API read routes**. The demo is a pure REST/WS client (zero `src/` imports), so a
> built engine is only usable by the demo once it (a) **runs** in the live system and (b) is **reachable**
> via a route. **Phase F closes both gaps; Phase G then builds the demo on top.** Deferred-item source:
> `project-harness/expansion/OVERNIGHT_LOOP.md` §Deferred follow-ups. Driver for execution: `/expand-next`
> (or `/expand-parallel` for the conflict-free wiring/route batches).
> **Sequencing rule:** F → G → H. Every G step depends on an F route/wiring it surfaces; Phase H consumes the
> F routes (plus four small H0 legacy enablers) and is otherwise pure demo-side. The demo-expansion analysis
> behind Phase H lives in `project-harness/demo-expansion/` (see its `RECONCILIATION.md` for what the
> EXP-201..230 program changed under it). H1 (economy) and H2 (content) are mostly type-A and can start
> before H0/H3; H3 (legacy-engine panels) waits on its H0 enabler.

### Phase F — Activate & expose (engine wiring + API routes)
- **Goal:** every built-but-dormant Phase A–E engine **runs** in the tick loop / composition root **and**
  is **reachable** by the demo via a REST/WS route. Exit-of-phase: the demo client can observe, for a live
  NPC, its relationship phase, the NPC's model of the player, active schemes, director beats, and receive
  proactive lines over WS.
- **Effort:** ~3 sessions · **Leverages:** `api/dependencies_engines.py` (scheduler composition root — already
  wires proactive + reputation engines), the tick scheduler, `dialogue_ws.push_proactive_line` (exists),
  `engines/relationship/standing.py`.
- **Constraints:** DIP — all wiring through `api/dependencies.py` / `dependencies_engines.py` (sole composition
  roots); `scheduler→api` delivery uses the DEC-098 in-process queue (no upward import); the new
  F3.5 `dialogue_turn` node + edge needs a fresh `DECISIONS.md` entry before it lands; routes are additive (auth on all).

#### F1 — Tick & composition-root wiring (make the engines actually run)
- [x] **F1.1 (EXP-201 s2)** — call `write_relationship_phase` after the relation delta in `dialogue_handler`. Exit: a phase transition is persisted during a live dialogue turn (integration test).
- [x] **F1.2 (EXP-209+210 s2)** — wire `trigger_router` into the tick scheduler (form proactive intents from memory/need/event) **and drain `ProactiveQueue` → `push_proactive_line`** over the dialogue WS. Exit: an idle connected player receives an NPC-initiated line end-to-end (WS integration test). *(memory source live; need/event are a clean router seam, deferred — ISSUE-094.)*
- [x] **F1.3 (EXP-219 s2)** — inject `TraitModulatedEmotionModel` into `EmotionUpdater` via the composition root (config-selectable vs `VadEmotionModel`). Exit: emotion deltas are trait-modulated in a live tick. *(global demo-default traits via `build_emotion_model`; per-NPC trait fetch deferred — ISSUE-096.)*
- [x] **F1.4 (EXP-226 s2)** — wire `PlayerModelEngine` into the scheduler (update each NPC's model of the player per tick window). Exit: `player_model` nodes update on tick (integration test). *(`PlayerModelTick` over co-located pairs; new scheduler slot + composition wiring.)*
- [x] **F1.5 (EXP-227 s2)** — wire the drama `director` into the scheduler (evaluate `decide()` on idle/plateau; emit the beat via the events engine). Exit: the director injects a beat during a live idle run. *(`DirectorTick` gates `EventHandler.run_tick` on `decide()`; idle + HOSTILE paths live; plateau-tick tracking deferred — ISSUE-097.)*
- [x] **F1.6 (EXP-229 s2)** — wire `SchemingEngine` into the scheduler (advance active scheme steps per tick) + **detection** by reviving `engines/investigation` (discover schemes). Exit: a scheme advances a step across ticks and an investigating NPC can surface it. **✅ DEC-107 resolved → Option A: `SchemeAdvanceTick` mints a registry-valid covert Event per step (event_type=scheme_advance, is_public=False) via the validated write path; `SchemeDetectionTick` flips active→discovered when a witnessed scheme has ≥ N steps (schema-free). Both self-gated scheduler slots.**
- [x] **F1.7 (EXP-212 s2)** — add a forgetting-decay tick that prunes/decays `is_forgettable` non-pinned memories on a schedule. Exit: low-salience memories decay over ticks (integration test). *(`MemoryDecayTick` self-gates on `MEMORY_DECAY_TICK_INTERVAL`, charge-weighted decay; batch-pruning/deletion deferred — decay satisfies the exit.)*

#### F2 — API read surfaces (so the demo can SEE the new state)
- [x] **F2.1** — `GET` relationship **phase** for an NPC↔player (extend `routes/relationship.py`, which today returns only standing). Exit: route returns `relationship_phase` + `phase_started_at_tick`. *(via `get_relation_phase_row`; also fixed the route's latent `response_model` envelope mismatch.)*
- [x] **F2.2 (EXP-226)** — `GET` player-model (the NPC's model of the player) via a new `routes/player_model.py`. Exit: route returns perceived_trust/intent for (npc, player). *(`GET /npc/{npc_id}/player-model/{player_id}`, reads F1.4 PlayerModel nodes.)*
- [x] **F2.3 (EXP-229)** — `GET` active schemes for an NPC (+ discovered flag) via a new `routes/schemes.py`. Exit: route returns the NPC's active schemes + steps. **✅ `GET /v1/npc/{id}/schemes` → schemes (any status) with discovered flag + ordered covert steps, via `scheme_reader.get_schemes_with_steps_for_npc`.**
- [x] **F2.4 (EXP-209/227)** — confirm/add the proactive **pending-intents** route (`GET /v1/dialogue/pending`) and a director-beat read. Exit: the demo client can poll pending NPC-initiated intents + recent director beats. *(pending route already existed — confirmed; added `DirectorBeatLog` + non-destructive `GET /v1/dialogue/director-beats`.)*
- [x] **F2.5 (EXP-228, optional)** — read surface that marks `is_deception=true` beliefs (for the buyer-facing "tell"). Exit: a route/flag distinguishes deception beliefs without leaking them as truth. *(beliefs read now returns the `is_deception` edge flag; content unchanged.)*

#### F3 — Engine correctness & cleanup (so the activated engines behave well)
- [x] **F3.1 (EXP-202 s2)** — replace the random `SECRET_BASE_PROBABILITY` gossip secret-share gate with a `Standing` threshold (gate secret-sharing by standing). Exit: secret-share probability tracks standing band. *(`secret_share_policy`: per-band probs, HOSTILE/WARY=0 → ALLIED highest; band derived from per-pair trust, no new read.)*
- [x] **F3.2 (EXP-204 s2)** — surface NPC **mood** (canonical `EmotionStore`, DEC-099) into the dialogue context (needs already surfaced). Exit: dialogue context carries a mood line. *(already wired end-to-end: `EmotionStore`→`dialogue_handler`→tier0→`npc.emotion.current_mood`; locked with a canonical-wins regression test.)*
- [x] **F3.3 (EXP-228 s2)** — wire `classify_deception_belief` into the **live** anti-hallucination eval loop (`_classify_case`). Exit: a planted `is_deception` belief is not scored as a hallucination failure, while ordinary unsupported claims still are. *(`_response_reflects_planted_deception` rescues a refusal_fail → `deception_intended`; consumes F2.5's is_deception read.)*
- [x] **F3.4 (EXP-214 cleanup)** — DI-inject `MemoryEngine` into `quest_lifecycle_engine` via the composition root (remove the `__init__` instantiation). Exit: no module-level engine instantiation; `make check` green. *(injected via `get_memory_engine()` singleton; default-fallback keeps direct callers working.)*
- [x] **F3.5 (EXP-230 s2)** — migrate session persistence from the current JSON-blob-on-Character-property to a **first-class `dialogue_turn` node** carrying the *existing* temporal convention (`occurred_at_game_time` + integer `tick`, same fields events/memories use), anchored to the NPC and player. Fixes the `player_id` property-key collision (OQ-9), removes per-player property sprawl, and makes turns queryable/orderable/prunable (keep-last-N by deleting oldest `tick`). Add an index on `(npc_id, player_id, tick)`. **Needs a DECISIONS entry (new node type + edge).** Exit: turns persist as `dialogue_turn` nodes ordered by `tick`; distinct player ids never collide; `SessionStore` round-trips via the nodes on restart. *(NB: a unified reified `GameTime` node — time-as-a-node that events/memories/turns all link to — is intentionally NOT this task; it is a separate, repo-wide architecture decision, valuable only if cross-entity temporal correlation becomes a feature, and must be bucketed (per-day) to avoid supernodes. Do not couple it to session persistence.)*
- [x] **F3.6 (EXP-217 seed)** — seed player `KNOWS_ABOUT` edges so `GET /player/{id}/events` returns data for the demo player. Exit: the player-events endpoint returns seeded events on a fresh `make demo-seed`. *(`_PLAYER_KNOWS_ABOUT`: player_demo knows northern_war_begins + market_fire, seeded after the player exists.)*

### Phase G — Demo expansion (use the now-live engines)
- **Goal:** surface the activated engines in the pygame demo — connect the built-but-static panels to live
  data, add new panels/beats for the cognition layer, and add an "intrigue" scenario that exercises
  deception + scheming + player-model. This is the recordable, sells-the-engine demo.
- **Effort:** ~2.5 sessions · **Leverages:** the F2 routes, existing panels (`RetrievalPanel`, `FactionBoard`,
  `RightPanel` tabs), `EngineClient`, the scripted runner + interactive window.
- **Constraints:** pure demo-side (zero `src/` imports); each G step consumes an F2 route (do not start a G
  step whose route isn't live); demo file-size waivers apply (DEC-029/032/034/036/049/074/075/105).

#### G1 — Connect built-but-static surfaces to live data
- [x] **G1.1 (EXP-207 s2)** — live-wire the facial-expression glyph (window updates `left_panel` per dialogue turn). Exit: glyph updates live during play.
- [x] **G1.2 (EXP-208 s2)** — retrieval-explainer poller (auto-refresh the RETRIEVAL panel each turn via `get_retrieval_debug`). Exit: panel updates live.
- [x] **G1.3 (EXP-221 s2)** — render the PART_OF location breadcrumb in the live window draw loop. Exit: breadcrumb shows for nested locations live.
- [x] **G1.4 (EXP-201)** — show relationship **phase** (per NPC) in the relationship/left panel via F2.1. Exit: the NPC's phase is visible and updates.

#### G2 — New demo surfaces for the cognition engines (need F2 routes)
- [x] **G2.1 (EXP-226)** — "What they think of YOU" player-model panel (via F2.2). Exit: panel shows the focused NPC's perceived_trust/intent.
- [x] **G2.2 (EXP-229)** — intrigue/scheme board: active NPC schemes + steps, hidden vs discovered (via F2.3). Exit: schemes render; discovery flips a step's state. **✅ INTRIGUE right-panel tab (`ui/scheme_board_panel.py`) + `NpcSchemesPoller` over `client.get_schemes`; HIDDEN/DISCOVERED badge + ordered steps.**
- [x] **G2.3 (EXP-227)** — surface director beats (a "something stirs" cue when the director injects) (via F2.4). Exit: an injected beat shows in the window.
- [x] **G2.4 (EXP-209/210)** — proactive dialogue in the **interactive** window end-to-end (NPC hails the player live over WS; highlight + prefill already built in EXP-225). Exit: an idle player is hailed live in the window. *(already live via `NpcInitiativePoller`→pending-intents→hail bubble+highlight+prefill, fed by the F1 intent_formation engine; locked with poller tests.)*
- [x] **G2.5 (EXP-228)** — deception "tell" affordance: a subtle buyer-facing reveal when an NPC states a flagged false belief (via F2.5). Exit: the demo can reveal a deception without breaking the in-fiction illusion.

#### G3 — Content & scenarios that exercise the new layer
- [x] **G3.1** — a scripted **"Intrigue"** scenario (new `demo_game/scenarios/`) that drives deception + scheming + player-model into one recordable arc (works under `--cinematic`). Exit: `make demo-run` plays the intrigue arc end-to-end. *(ACT 12: `DeceptionRevealScene` + `PlayerModelDisplay` in the demo SCENES; both respect dry_run/cinematic. Scheme beat deferred — F1.6.)*
- [x] **G3.2** — seed enrichment so the new panels have data on first run (scheme seeds, KNOWS_ABOUT from F3.6, a deception setup). Exit: panels are non-empty on a fresh `make demo-seed`. *(deception belief seeded — `lira_fence` is_deception; KNOWS_ABOUT from F3.6; player-model data comes from the scheduler tick; scheme seeds await F1.6.)*

### Phase H — Demo-game expansion (consume the APIs; make the demo a *game*)
- **Goal:** turn the demo from a tech-demo into a game — a multi-objective win/lose **economy**, more **content**
  with real **branching**, and the **legacy gameplay engines** (treaty/oath/investigation/chapter/story-pacing)
  that Phase G does not cover. Phase G surfaces the *cognition* layer; Phase H adds *economy + content + legacy*.
- **Effort:** ~3–4 sessions · **Leverages:** existing `EngineClient` (gold/quest/reputation/pledge methods),
  `game_end_checker.py`, the 14-tab `RightPanel` + poller framework, `seed.py` (KE-6 idempotent), EXP-218's
  `POST /quest/{id}/choose` route, EXP-223's 8-NPC/4-location world.
- **Source analysis:** `project-harness/demo-expansion/` (DEMO_INTENT/DORMANT_ENGINES/CONTENT_PLAN/ECONOMY_DEPTH/
  FEASIBILITY/DEMO_EXPANSION_ROADMAP/OPEN_QUESTIONS) + `RECONCILIATION.md`. Each H item cites its `DEMO-Dx` mini-spec.
- **Constraints:** pure demo-side (zero `src/` imports) **except** the named **H0** enablers; each demo item
  consumes an existing/F/H0 route; demo file-size waivers apply (DEC-029/032/034/036/049/074/075/105); the
  D3 `evaluate_game_end` rewrite must stay ≤40 lines / ≤3 nesting (extract `check_win_multi`/`compute_grade`).
- **Baseline (verified 2026-06-12):** `game_end_checker.py` still single-win (2/3 factions ≥ 50) + inert single-lose
  (`iron_legion`→`loc_guard_barracks`); world is 8 NPCs / 4 locations / 3 alliable factions.

#### H0 — Small legacy-engine enablers (engine-side; routes/client the demo needs that Phase F does not add)
> Engine work, tracked separately; orchestrator lands each before its H3 consumer. None need schema (DEC-free).
- [x] **H0.1 (E-1, DEMO-D1-01)** — `EngineClient.break_pledge` wrapper over the existing `pledges.py:114` break endpoint. Exit: client can break a pledge; unblocks oath-break (H3.1).
- [x] **H0.2 (E-2, DEMO-D1-02)** — `EngineClient.create_treaty`/`get_faction_treaties`/`break_treaty` over the existing `treaties.py` route (no route change). Exit: client can broker/list/break treaties; unblocks H3.2 + the treaty win path (H1.1).
- [x] **H0.3 (E-3, DEMO-D1-03)** — new read-only `api/routes/investigations.py` (`GET`) over `investigation_engine.get_investigation_context` + `EngineClient.get_investigation`. Exit: client reads investigation context (alibi/contradiction half not covered by EXP-229 schemes). Reuse F2.3 `schemes.py` for the discovery half.
- [x] **H0.4 (E-4, DEMO-D1-04)** — new read-only `api/routes/chapters.py` (`GET /chapters/current`) over `chapter_engine.get_current_chapter` + `EngineClient.get_current_chapter`. Exit: client reads the current chapter/act; unblocks H3.4.
- [x] **H0.5 (DEMO-D2-06 dep)** — `EngineClient.post_quest_choice` wrapper over EXP-218's existing `POST /quest/{id}/choose`. Exit: the demo can resolve a quest branch choice; unblocks the branch primitive (H2.1).

#### H1 — Win/lose economy depth (Pillar 3 · mostly type-A · delta to `game_end_checker.py`)
- [x] **H1.1 (DEMO-D3-01)** — multi-objective win: faction-standing **OR** wealth **OR** quest-chain (**OR** brokered treaty via H0.2). Exit: any one path triggers a win; faction/wealth/quest paths need no enabler.
- [x] **H1.2 (DEMO-D3-02)** — currency win/lose axis (`WEALTH_WIN_THRESHOLD`; bankruptcy `BANKRUPTCY_LOSE_THRESHOLD` armed after gold was once positive) over `GoldPoller`. Exit: gold can win or lose the game.
- [x] **H1.3 (DEMO-D3-03)** — faction tension/overreach: gains with one faction cost a rival via `adjust_npc_reputation` (`client.py:1414`) as a branch/quest effect (type-A; server-side auto-decrement deferred type-C). Exit: a rival penalty fires on a friendly action.
- [x] **H1.4 (DEMO-D3-04)** — tick deadline pressure: relative `DEADLINE_TICKS` from a latched start tick via `get_clock_state().current_tick`. Exit: missing objectives by the deadline loses (needs auto-tick on).
- [x] **H1.5 (DEMO-D3-05)** — ≥2 distinct reachable failure states (bankruptcy H1.2 + deadline H1.4 + an authored `CONTROLS` legion trigger via `upsert_edge`), with a `failure_reason` → `LOSE_SUBTITLES` end-card. Exit: the inert single-lose is replaced by ≥2 player-caused losses.
- [x] **H1.6 (DEMO-D3-06)** — end-screen score/grade `compute_grade(...) → S/A/B/C` over the win axes. Exit: a graded end-card renders.

#### H2 — Content & branching (Pillar 2 · type-A · rebaselined from 8 NPC / 4 loc)
- [x] **H2.1 (DEMO-D2-06)** — branch primitive: `branch_node.py` + `branch_state.py` + `branch_effects.py` (typed effects: belief/rep/world-state/quest, OCP one-file-per-effect) + `ui/branch_panel.py`, resolving choices over existing client methods + H0.5. Exit: a player choice forks outcomes in the running demo.
- [x] **H2.2 (DEMO-D2-01)** — cast expansion 8→14 NPCs; split NPC data into `demo_game/seed_npc_data.py` (data-only) to respect the size rule. Exit: new NPCs seed idempotently (KE-6).
- [x] **H2.3 (DEMO-D2-02)** — locations 4→7 + a district tier via `post_part_of` (`client.py:776`, already live). Exit: nested locations seed; breadcrumb shows them (EXP-221).
- [x] **H2.4 (DEMO-D2-03)** — factions 3→5 alliable. Exit: two new factions seed with standings the economy can read.
- [x] **H2.5 (DEMO-D2-04)** — quests ~6→18 across 6 chains over the full quest lifecycle (`post_quest_*`). Exit: chains are acceptable/completable and feed H1.1's quest-chain win path.
- [x] **H2.6 (DEMO-D2-05)** — rival quest variants + a `GameController` accept-guard (can't accept opposing-faction quests simultaneously). Exit: accepting one rival quest locks the other.
- [x] **H2.7 (DEMO-D2-08)** — promote Village/Tavern eval worlds to playable Free-Play: de-hardcode `game_end_checker` win/lose constants to be per-world (new `world_objectives.py` `WorldObjectives` bundle + `WORLD_OBJECTIVES` registry; checker predicates + `GameEndPoller` take an `objectives` param defaulting to `DEMO_OBJECTIVES`). Exit: all three worlds are pickable + winnable.
- [x] **H2.8 (DEMO-D2-07)** — replayable scenario forks: `BranchBeat` in scripted scenes (`scenarios/`) over H2.1, with a persisted `BranchState`. Exit: a scripted scenario replays to a different outcome.

#### H3 — Legacy gameplay-engine surfaces (Pillar 1 · consume H0 enablers)
- [x] **H3.1 (DEMO-D1-01/D2-11)** — oath panel + `pledge_poller`: swear/list (type-A over `post_pledge`/`get_pledges_for_npc`) + break (H0.1). New `pledge_poller.py` + `ui/oath_panel.py` (OATH tab, swear/break buttons). Exit: the player swears, breaks, and the list updates.
- [x] **H3.2 (DEMO-D1-02/D2-09)** — treaty board (H0.2): broker/break treaties between factions. New `treaty_poller.py` (merges all-faction treaties) + `ui/treaty_panel.py` (TREATY tab). Exit: a brokered treaty is a visible objective (feeds H1.1 treaty win path).
- [x] **H3.3 (DEMO-D1-03)** — investigation "solve-the-crime" panel (H0.3): surface alibi/rumor contradictions, each clue showing its graph provenance. New `ui/investigation_panel.py` (INVESTIGATE tab). Exit: a crime is solvable from graph contradictions. (Scheme-discovery overlay deferred to F2.3 / DEC-107.)
- [x] **H3.4 (DEMO-D1-04/D2-10)** — chapter act/season banner (H0.4). New `chapter_poller.py` + `_draw_chapter_banner()` HUD overlay. Exit: the current act renders and advances.
- [x] **H3.5 (DEMO-D1-05)** — story-pacing tension HUD: render `max_event_severity`/`quest_generation_rate` from `get_world_state` as a pressure gauge. New `tension_poller.py` + `_draw_tension_hud()` colour-coded severity bar. Exit: a live tension meter updates. (type-A, no enabler.)

#### Deferred (type-C — needs a `DECISIONS.md` call; not in the overnight set)
- [ ] **H-D1 (DEMO-D1-06b)** — engine military battle sim with a balanced player military verb (army strength + verb). See OPEN_QUESTIONS OQ-5.
- [ ] **H-D2 (DEMO-D3-03s)** — server-side automatic cross-faction standing decrement (emergent rival tension). See OPEN_QUESTIONS OQ-6.

---

## Completed ✅ — Expansion program (2026-06-11→12 · EXP-201..230, slice 1)

> Source: `project-harness/expansion/EXPANSION_ROADMAP.md`; mini-specs in `ENGINE_GAPS.md` /
> `NEW_ENGINES.md` / `DEMO_EXPANSIONS.md`; seams in `FEASIBILITY.md`; granted decisions DEC-097..104.
> **Reconciliation:** the analysis was run without the prior execution backlog and re-proposed shipped
> work; a code-grounded verification dropped 10 already-built items and renumbered the real remainder
> to **EXP-201..230** (collision-free with the legacy EXP-10..57 scheme). Mapping + per-item deps live
> in `project-harness/expansion/EXPANSION_INDEX.md` (the execution driver).
> **Throughline:** the simulation computes correctly but is invisible to the dialogue layer and the
> buyer — most work is connective (wire computed state into what the player sees and the LLM reads).
> **Execution:** `/expand-parallel` autonomous loop — see `project-harness/expansion/OVERNIGHT_LOOP.md`.

### Phase A — "Make it visible" (no schema)
- **Goal:** connect computed engine state to player + buyer; turn the scripted demo into a recordable pitch.
- **Effort:** ~1 session · **Leverages:** relationship/reputation engines (wired), parsed-but-unrendered demo data.
- **Constraints:** demo is a pure REST/WS client (zero `src/` imports); no graph schema change.
- [x] **EXP-201** relationship affinity phase engine (slice 1: `derive_phase` + `relation_phase_writer`, new files; unit tests green, a397661). Slice-2 call-site wiring in `dialogue_handler.py` deferred.
- [x] **EXP-202** standing → dialogue tone (slice 1; 0ad8c02). STANDING line in prompt + system_v1 tone rule; secret-share gate = slice 2 deferred.
- [x] **EXP-203** relation-delta first-contact fix (creates edge instead of swallowing error; f511d42). first-contact delta persists; regression test green.
- [x] **EXP-204** need fed into dialogue context (slice 1; DEC-099; e0ec882). Top unmet need surfaces as optional Tier-B item; mood slice 2 deferred.
- [x] **EXP-205** proactive dialogue act in scripted runner (demo; 6007e04). ACT-11 NPC-initiated beat plays.
- [x] **EXP-206** temporal memory readout (demo; 62975ea). Memory panel shows occurred_at + historical marker.
- [x] **EXP-207** facial-expression glyph rendering (demo; ff126b4). Portrait zone renders glyph; live wiring is a follow-up.

### Phase B — "Prove the moat"
- **Goal:** surface the (already-built) anti-hallucination + retrieval evals to the buyer.
- **Effort:** ~0.5 session · **Notes:** EXP-31/32 eval runners already shipped; only the demo panel remains.
- [x] **EXP-208** retrieval-explainer panel (demo; 1caaa04). RETRIEVAL tab renders retrieved items; live poller wiring is a follow-up.

### Phase C — "Close the agentic loop" (schema: DEC-097/098)
- **Goal:** NPCs act on their own state and reach the player; memory becomes player-scoped + decaying.
- **Effort:** ~1.5 sessions · **Leverages:** ProactiveDialogue/IntentFormation engines (wired but undelivered), `push_proactive_line()` helper.
- **Constraints:** DEC-098 (scheduler→api queue), DEC-097 (memory.yaml fields). Orchestrator applies schema before the batch. EXP-211 + EXP-212 share `memory.yaml`/`memory_engine.py`/`context_builder.py` → one worker.
- [x] **EXP-209** unified proactive-trigger surface (slice 1; dc18e67). `select_trigger` router; scheduler wiring = slice 2.
- [x] **EXP-210** proactive delivery queue (slice 1; e958799). `ProactiveQueue`; dialogue_ws drain = slice 2.
- [x] **EXP-211** player-scoped memory recall (c571ae7). `subject_player_id` + player-scoped reader surfaces memory in context.
- [x] **EXP-212** salience forgetting curve (c571ae7). `compute_salience`/`is_forgettable` + `MEMORY_FORGET_THRESHOLD`; decay sched = slice 2.

### Phase D — "Deepen the systems" (schema: DEC-100/101)
- **Goal:** richer gossip drift, interactive economy, visible politics, more game.
- **Effort:** ~2 sessions · **Leverages:** distortion registry, NegotiationStore, location PART_OF (fixed).
- **Constraints:** EXP-223 needs faction-count review in `game_end_checker.py`; EXP-207 & EXP-221 both edit `left_panel.py` (one worker); EXP-205 & EXP-222 both edit `run.py` (one worker).
- [x] **EXP-213** belief/confidence-aware distortion routing (7be05fe). Receiver confidence biases distortion type (deterministic).
- [x] **EXP-214** commitment memory formation (DEC-100; 0adc89f). Quest accept forms a kind=commitment memory.
- [x] **EXP-215** belief contradiction detection + dedup (2ac16eb). Duplicate/contradictory learned beliefs skipped pre-write.
- [x] **EXP-216** trade dispatch → NegotiationStore (fc56e75). Composition root wires NegotiationBacked default.
- [x] **EXP-217** player-observable event summary endpoint (42682f4). `GET /player/{id}/events` + reader + tests green.
- [x] **EXP-218** quest branching on player choice (DEC-101; d9b318a). `choose` + `POST /quest/{id}/choose`; null auto-unlocks.
- [x] **EXP-219** personality-modulated emotion model (6ca22af). `TraitModulatedEmotionModel` 2nd impl; wiring = slice 2.
- [x] **EXP-220** faction standing board (demo; 69f7c80). FACTION tab shows standings.
- [x] **EXP-221** location hierarchy breadcrumb (demo; 8e14e11). PART_OF breadcrumb builder; draw wiring = slice 2.
- [x] **EXP-222** cinematic / recording mode (demo; 6c69444). `--cinematic` formatted run; default unchanged.
- [x] **EXP-223** richer world (demo; 36bec00). +3 NPCs +1 location in existing factions; faction count intact.
- [x] **EXP-224** mood-contagion visualiser (demo; 5e1f230). Emotion panel shows a contagion pair (DEC-105 size waiver).
- [x] **EXP-225** proactive window surface (demo; c26c224). Intent NPC highlighted + input pre-filled.

### Phase E — "Emergent cognition" (flagship; schema: DEC-102/103/104)
- **Goal:** NPCs that model the player, hold/act on false beliefs, and pursue multi-step covert goals.
- **Effort:** ~3+ sessions · **Leverages:** relationship phase (EXP-201), knowledge_extraction, events/story_pacing.
- **Constraints:** new node/edge types applied just-in-time by orchestrator (DEC-102/103/104); EXP-228 requires the anti-hallucination eval to treat `is_deception=true` as intended; EXP-229 revives `investigation` for detection. STOP + surface if the type-registry gate can't be made green.
- [x] **EXP-226** player-model / theory-of-mind engine (DEC-102; 4148fef). player_model node upsert/read via HAS_PLAYER_MODEL; wiring = slice 2.
- [x] **EXP-227** player-aware drama director engine (7b0f1d9). `decide` injects a beat on idle/plateau/hostile; wiring = slice 2.
- [x] **EXP-228** NPC deception / false-belief engine (DEC-103; 3b42061). NPC plants a flagged false belief; eval has a deception carve-out (live wiring = slice 2).
- [x] **EXP-229** long-horizon covert scheming engine (DEC-104; f985fbe). Form/cap/advance a scheme via scheme node+edges; detection = slice 2.
- [x] **EXP-230** session history persisted across restart (c30df84). save/load_to_graph + lifespan hooks (best-effort); dedicated node = follow-up.

### Already shipped — dropped from this program (verified in code 2026-06-11)
EXP-14 (emotion persistence, write-through), EXP-20-equiv (world-state quest triggers wired),
analysis EXP-93 (ISSUE-060 bribe fix — `adjust_npc_reputation` already in `run_scenes.py:242`),
EXP-72 (gossip distortion diff — `gossip_chain.py:128`), EXP-76 (degradation label), EXP-78 (relation
ticker), EXP-31/32 (retrieval + anti-hallucination eval runners), EXP-15 (distortion prompts YAML),
EXP-95 (scenario picker), plus EXP-80/81/85/92 demo beats.

---

## Parked backlog (carried forward, not active)

- [ ] **S17.9** — Legacy niche-engine expansions + demo integration (succession, clique, investigation,
  skill, military, treaty). Low commercial value; kept in code, no active dev. (NB: `investigation` is
  revived inside EXP-229's detection half.)
- [ ] **S21.6** — File-size rule cluster, `demo_game/` scope (`client.py` 1524L, `seed.py` 1265L,
  `run.py`, `run_scenes.py`, `game_controller.py`, `ui/*`, `scenarios/*`). Demo code, high split
  risk, low value; several already waived (DEC-029/032/034/049/074/075).
- **Phase X — Engine SDKs (Unity / Unreal)** — moved verbatim to
  **`project-harness/UNREAL_DEFERRED.md`** (2026-07-31). `SX.1`–`SX.4` preserved there.

---

## Engine Scope Decisions (reference)

| Engine | Status | Decision |
|--------|--------|----------|
| gossip, emotion, need, mood, routine, agenda | works, ticks | Showcased (Phases 1, 6) |
| quest_generation, quest (lifecycle) | works | Showcased (Phases 2–3) |
| memory_consolidation | works | Showcased (S6.3 — headline feature) |
| chapter, story_pacing | works | Promoted to gameplay (Phase 7) |
| faction_politics, oath, treaty | complete | Completed + showcased (S2.3, S2.4, S6.2) |
| military | implemented | Implemented S6.5 (ISSUE-031) |
| reputation + gossip | works | Productized (Phase 8 networked reputation) |
| relationship, planning, knowledge_learning, economy/currency | works | Built in legacy EXP backlog (EXP-50/51/52/53/40) |
| secrets, leverage, pledges, beliefs | works | One consequence surfaced (S6.2) |
| succession, clique | works, niche | Graveyard — kept in code |
| investigation, skill | works, niche | Graveyard — investigation revived in EXP-229 |

---

## Testing Strategy (forward)

`make test` + `make test-demo` green before every merge. New work ships with tests.
`make check` (lint · check-rules · check-layers · check-docstrings · type · check-harness · test-cov ≥80%)
is the canonical health gate. Green as of Phase 25 completion (1967 passed, 22 skipped, 85.70% coverage).

---

## Sign-off Review (2026-06-22)

> Code-grounded verification of all non-archived work items against the live codebase.
> 32 spot-checks run; all 32 VERIFIED. Goal: sign off on the engine, push `feat/shippable-demo-game` → `main`, begin Unity.

### ✅ Done — verified in codebase

**Engine quality remediation (REM-W series, 2026-06-19)**
- REM-W0/W1a: ISSUE-056/064/072/076 archived; ISSUE-106/109/098 initial fixes applied.
- REM-W1b: Docstring sweep — 73 files updated; `scripts/docstring_audit.py` guard added; `make check` 86.11%. Closes ISSUE-103/115.
- REM-W2: Stale tests + coverage — ISSUE-116/111/101/110/102; 13+9+9 new tests. `make check` 86.81%.
- REM-W3: Size limits — ISSUE-114/105/095; `dependencies_engines/` split into package; `get_proactive_queue` hoisted. 86.83%.
- REM-W4: OCP residuals — ISSUE-104; `register_emotion_model`, `register_tts_backend`, `SchemeStepKind`, `MOOD_LABEL_TO_VAD`, config registry validators; 14 new tests. 86.87%.
- REM-W5: Engine slices — ISSUE-112 (`src_character_id`/WITNESSED), ISSUE-108 (`emit_scheme_step_atomic`), ISSUE-097 (`_plateau_tracker`), ISSUE-094 (`IntentGraphPort`/need+event producers), ISSUE-096 (`TraitReadPort`/per-NPC traits). DEC-133–137. 86.94%.
- REM-W6: Headline features — ISSUE-071 (`SystemStateContext` Tier-0 block + `system_state_v1.yaml`), ISSUE-107 (`memories_recalled` in `DialogueResponse` + e2e scenario). DEC-138–139. 2523 passed, 86.88%.

**Shippable runtime (SHIP series)**
- SHIP-01: Unity selected as game-client platform (DEC-125).
- SHIP-02: `OpenAICompatibleAdapter` registered in `engines/llm/factory.py` (DEC-126); 18 tests.
- SHIP-03: `npc_engine.setup` package — `vram_detector`, `model_tiers`, `ollama_manager`, `first_run_flow`; `scripts/setup_local.py`; 33 tests (DEC-127).
- SHIP-04: `neo4j_manager`, `stack_launcher`, `scripts/launcher.py`, `packaging/npc_engine.spec`; `make package` (DEC-128); 19 tests.
- SHIP-05a: `wizard_config.py` + `path_validator.py` in `setup/` (DEC-129).

**Phase F — Activate & expose (engine wiring + API routes)**
- F1.1–F1.7: relationship phase write-through, proactive queue drain, trait-modulated emotion injection, `PlayerModelEngine` tick, drama director tick, `SchemingEngine` + `SchemeDetectionTick`, memory-decay tick.
- F2.1–F2.5: relationship phase route, player-model route, schemes route, pending-intents + director-beat route, `is_deception` flag on beliefs read.
- F3.1–F3.6: secret-share standing gate, mood surfaced in dialogue context, deception belief anti-hallucination carve-out, `MemoryEngine` DI-injected into quest lifecycle, `dialogue_turn` node persistence, player `KNOWS_ABOUT` seed edges.

**Phase G — Demo expansion**
- G1.1–G1.4: live facial-expression glyph, RETRIEVAL panel poller, location breadcrumb, relationship phase panel.
- G2.1–G2.5: player-model panel, `scheme_board_panel.py` (INTRIGUE tab), director-beat surface, proactive NPC hail in interactive window, deception "tell" affordance.
- G3.1–G3.2: scripted "Intrigue" scenario; scheme/deception/player-model seed data.

**Phase H — Make the demo a game**
- H0.1–H0.5: `break_pledge`, treaty client methods, investigations route + client, chapters route + client, `post_quest_choice` wrapper.
- H1.1–H1.6: multi-objective win, currency win/lose axis, faction tension penalty, tick deadline pressure, ≥2 failure states + `failure_reason`, grade end-card.
- H2.1–H2.8: `branch_panel.py` primitive, 14-NPC cast + `seed_npc_data.py`, 7 locations + district tier, 5 factions, 18 quests across 6 chains, rival quest lock, `world_objectives.py` multi-world, replayable scenario forks.
- H3.1–H3.5: `oath_panel.py`, `treaty_panel.py`, `investigation_panel.py`, chapter banner, tension HUD.

**Expansion program (EXP-201..230) and Phases 0–26** — fully archived; see archive entries at top of file.

---

### ❌ Not Done — open items

#### Engine hygiene (P2/P3 — minor, non-blocking)
| ID | Item | Priority | Notes |
|----|------|----------|-------|
| ~~REM-W7 / ISSUE-100~~ FIXED | `make demo-run ARGS=--dry-run` failed near ACT 8 — root cause was a cp1252 `UnicodeEncodeError` on the `→` cue glyph, not a guard | P3 | Fixed 2026-06-22 by wiring `ensure_utf8_stdout()` into `run.py:main()`; also hardens live Windows runs. Archived. |
| ~~REM-W8 / ISSUE-053~~ FIXED | grandfathered `check-rules` violations in `scripts/rules_baseline.txt` | P2 | Fixed 2026-06-22 (DEC-140): named clusters already cleared; R001/R006 remainder is cohesive-by-design debt, documented-waived; high-value DRY clear cleared `stream_text`. Archived. |
| ISSUE-083 | Voice judge residual: `captain_sorn` voice judge borderline-fails (secondary-source phrasing habit) | P3 | Anti-hallucination gate unaffected; purely voice colour |
| ~~ISSUE-098~~ FIXED | Four factories in `dependencies_engines/` each create their own `PlayerLocationReader()` instead of sharing a singleton | P3 | Resolved 2026-06-22: shared `get_player_location_reader()` singleton already wired; regression test added. Archived. |

#### Unity game slice + B2B proof wrap — **DEFERRED**
Both tables (`SHIP-05b..09`, `SHIP-10/11`) moved verbatim to
**`project-harness/UNREAL_DEFERRED.md`** (2026-07-31).

#### Future phases (sequenced after Unity dev begins)
| Phase | Goal | Effort |
|-------|------|--------|
| INTEG-01..05 | Setup routes (`/setup/validate`, `/setup/config`), localhost-only auth exemption, `docs/INTEGRATION.md` | ~1 session |
| EVAL-01..05 | Per-stage latency timer, golden-transcript regression suite, content-determinism pin, memory-recall eval, engine-quality scorecard | ~2–3 sessions |
| PERF-00..07 | Model warmup, first-token streaming, `asyncio.gather` graph reads, cache hit-rate, Kùzu spike, tick throttle, VRAM tuning, optional PyO3 | ~3–5 sessions |

#### Deferred / type-C (needs DECISIONS call before starting)
| ID | Item |
|----|------|
| H-D1 | Engine military battle sim with balanced player military verb |
| H-D2 | Server-side automatic cross-faction standing decrement |
| OD-Ship-graph | Neo4j GPLv3 / Kùzu evaluation spike (DEC-132 direction set; spike not yet run) |

#### Parked backlog (no active dev; kept in code)
| ID | Item |
|----|------|
| S17.9 | Legacy niche-engine expansions (succession, clique, skill, military) |
| S21.6 | `demo_game/` file-size rule cluster (`client.py` 1524L, `seed.py` 1265L, …) — several already waived |
| Phase X | Engine SDKs — **moved to `project-harness/UNREAL_DEFERRED.md`** (2026-07-31) |

---

### Verdict

**The engine is ready for `main`.** All claimed completions are verified in the codebase (32/32). Remaining open items are P2/P3 hygiene (REM-W7/W8) or future milestones gated on Unity development. None block engine functionality, test coverage (86.88%), or the packaged runtime.

**Recommended merge sequence:**
1. Run `make check` one final time on `feat/shippable-demo-game` to confirm green.
2. Merge `feat/shippable-demo-game` → `main`.
3. Open a `feat/unity-game` branch; start with SHIP-05b (Unity wizard screen, drives SHIP-05a validators already shipped).
4. Tackle REM-W7 + REM-W8 on a short cleanup branch if desired before or during Unity dev.
