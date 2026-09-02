# NPCSystem — Engine Roadmap

**Status (2026-08-28):** the active and only program is the **2026-08 remediation program**,
sequenced from the strategic codebase review. 145 findings → 118 canonical problems after
[adversarial triage](review-2026-08/TRIAGE.md) → 37 work items in 8 phases.

**Substance lives in [FIX_PLANS.md](review-2026-08/FIX_PLANS.md).** This file holds sequence,
state, and the self-contained task specs the overnight loop executes. Every task carries a
**RED anchor** — a check that fails today and passes after — because the review's root cause was
checks binding to an artifact's form rather than the behaviour it stands for. A task without a
red-first anchor cannot be verified and must not be ticked.

**Phase order is a dependency order, not a priority order.** R1 before R2 (do not wire gates that
cannot fail into CI). R2 before R3 (do not verify a product fix with an instrument a fixed string
beats). Within R2, R2.4 must land in its own commit before R2.5 or the guard-rate delta is
unattributable.

### Carry-forward notes

*Cheap context for the next session. Add a line when a task creates something downstream work
needs; delete it once consumed. Keep ≤10 lines.*

- Baselines: `review-2026-08/BASELINE_2026-08-28.md`. R2.4 and R2.2 are *expected* to move
  numbers; an unexplained move is a finding, not a side effect.
- Fast gates were green at program start (`lint`, `check-rules` 133, `check-evals-rules` 72,
  `check-layers`, `check-docstrings`). A red fast gate is caused by the work in hand.
- Integration tests need the override: `docker compose -f docker-compose.yml -f
  docker-compose.test.yml up -d`, then `NEO4J_URI=bolt://localhost:7687`. Base compose alone
  cannot reach bolt (DEC-232).
- Plans were written against `619dab2`; confirm each cited location before editing.
- R0 is complete (`332d5af`). Key rotation remains outstanding and is human-only.

### History

| What | Where |
|---|---|
| Full pre-remediation roadmap (phases 0–26, EXP/F-G-H/SEV programs, eval P0–P31, 210 ticked items) | `archive/ROADMAP_pre-remediation_2026-08-28.md` |
| Phases 0–13 | `proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 | `archive/ROADMAP_phase14-26_2026-06-11.md` |
| The review itself | `CODEBASE_REVIEW.md`, `review-2026-08/` |

### R0 — Security · **complete 2026-08-28** (`332d5af`)

- [x] **R0.1** `/setup/*` unauthenticated remote read of a plaintext API key · CR-L05-11 · ISSUE-227 · DEC-231
- [x] **R0.2** Neo4j bolt unreachable from host, so `tests/integration` had never run · ISSUE-232 · DEC-232

Outstanding and human-only: **rotate the wizard API key** if port 8000 was ever reachable off-box.

<!-- LOOP:QUEUE start -->
<!-- Everything between these markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside this fence — deliberate.
     Scope agreed 2026-08-28: R1, R2 (to R2.4), R4, and the safe half of R3.
     A task tagged ⏸️, "ask-gate", or "(live" is skipped without spending a session.
     R5, R6, R7 sit outside the fence: R6 would have the loop rewrite its own driver
     mid-run, and R7.1 is a 145-function refactor. -->

### Phase R1

Gate integrity. Nothing downstream is trustworthy until gates can fail. Plans: `FIX_PLANS.md#r1`.

- [x] **R1.1** Make `check-rules` signatures line-count-bearing; two-tier size limit
Files: `scripts/check_rules.py`, `scripts/rules_baseline.txt`, `scripts/evals_baseline.txt`
Spec: record the line count at grandfathering time in the signature; fail when a grandfathered
file exceeds its recorded size. Two tiers per DEC-226: soft advisory at 400 (no gate, no waiver
list), hard unwaivable gate at 800. Re-baseline once, in this same commit.
RED anchor: append a no-op comment line to `demo_game/client.py` and run `make check-rules`.
Today it stays GREEN — `check_rules.py:27` states "Signatures are file-level … stable across
edits", and that file gained 481 lines while grandfathered. After the fix it must go RED.
Revert the comment before committing.
Validation: `make check-rules` green on a clean tree; a synthetic 801-line file reds with no
waiver available. Four non-test files already exceed 800 (client.py 1901, seed.py 1677,
game_window.py 925, evals/calibration.py 875) — they are R7.2, not this task.
Blocks: R7.2. CR-L06-05 +2. ✅ AUTO (R1.1, 2026-08-28)

- [x] **R1.2** Give `check-test-quality` and `check-human-gates` real exit codes
Files: `scripts/check_test_quality.py`, `scripts/check_human_gates.py`, `Makefile`
Spec: `check_test_quality.main()` ends `return 0` unconditionally and its docstring admits it
("Exits 0 always"). Make it return 1 above a recorded baseline, ratchet-style. `check_human_gates`
keeps its content — it is the only tracker of 16 blocked human tasks — but gains `--strict`.
Per decision 2026-08-28, `--strict` goes in a NEW `make check-blocking` target, NOT in
`make check`: it reds immediately on 6 OPEN gates and would kill every loop task.
RED anchor: add a test file containing only `def test_nothing(): pass`, run
`make check-test-quality`, assert exit 1. Today `echo $?` prints 0 regardless of what it reports.
Delete the file afterwards.
Validation: `python scripts/check_human_gates.py --strict; echo $?` prints 1 while gates are OPEN;
`make check` does not include check-blocking. CR-L06-03, CR-L06-01. ✅ AUTO (R1.2, 2026-08-28)

- [x] **R1.3** Remove the two gates that audit unchangeable inputs
Files: `scripts/check_conservation.py`, `scripts/check_label_survival.py`, `Makefile`
Spec: drop `check-conservation` and `check-label-survival` from `make check` and delete
`_check_identity_2`. `check_conservation.py:164` reads `all_slots = compare_slots` then line 169
asserts `ok=(compare_slots == all_slots)` — a literal `x == x`, introduced in a commit labelled a
bug fix. Identities 1 and 3 are real: move them to `make eval-generate`, where their data changes.
RED anchor: `grep -n 'all_slots = compare_slots' scripts/check_conservation.py` returns a row
today and must return none after. Behavioural: corrupt one row in a generation dir's
`judged.jsonl` and confirm `make eval-generate` reds on Identity 1.
Validation: `make check` no longer lists either target; `make check` still green.
CR-L06-09, CR-L03-07. ✅ AUTO (R1.3, 2026-08-28)

- [x] **R1.4** Delete `check-harness` H3 — it reads an archived path and can never fire
Files: `scripts/check_harness_honesty.py`, `Makefile`
Spec: H3 warns when ISSUES.md has open tickets but NEXT_SESSION.md claims none. NEXT_SESSION.md
exists only at `archive/stale-2026-06/NEXT_SESSION.md`, so H3 is permanently inert. Delete H3,
keep H1/H2. Also fix the ordering defect: the only hard check sits behind `lint`, which runs
first in `make check` and short-circuits it. Do NOT recreate NEXT_SESSION.md to satisfy a gate.
RED anchor: `grep -c H3 scripts/check_harness_honesty.py` returns >0 today, 0 after. Then prove
H1 still earns its place: remove a required DECISIONS heading and confirm `make check-harness`
reds.
Validation: `make check-harness` green on a clean tree. CR-L06-07, CR-L13-06. ✅ AUTO (R1.4, 2026-08-28)

- [x] **R1.5** Make `check-docstrings` read content, not the substring `Layer:`
Files: `scripts/docstring_audit.py`, plus any module whose `Layer:` value is wrong
Spec: verify the `Layer:` value is a declared layer name AND matches the file's directory.
Do NOT extend the gate to function docstrings — CR-L05-03 shows compliance tracks whatever is
gated (100% on gated fields, 28% on ungated, with ungated `demo_game/` scoring higher than gated
`src/`), so gating more fields buys conformance, not quality. Per decision 2026-08-28, fix wrong
values in this same commit; if the count is large enough to need mass unsupervised edits, HALT
and ask instead.
RED anchor: change `Layer: graph` to `Layer: banana` in any `graph/` module and run
`make check-docstrings`. Today it stays GREEN — only the substring is checked. Must go RED.
Revert afterwards. Second counterfactual: move a file between layer directories without updating
its docstring; the gate must red.
Validation: `make check-docstrings` green on a clean tree. CR-L06-08, CR-L14-07. ✅ AUTO (R1.5, 2026-08-28)

- [x] **R1.6** Close the three rule-scope gaps
Files: `scripts/check_rules.py`, `scripts/rules_baseline.txt`
Spec: R005 (Cypher leak) scans a `_CYPHER_SCAN_DIRS` set excluding `api/`, `auth/`, `data/`,
`cache/`, `mutation/` — extend to all non-`graph/` packages. R004 matches the literal string
`raise Exception(`, never written in 967 commits, while missing both real violations inside
`utils/errors.py`, the file its own rule names — match `raise Exception`/`BaseException` with
optional whitespace plus an AST check for `class X(Exception)` outside `utils/errors.py`. Add
`scripts/` (7,821 LOC) to the R001/R006 scan set.
RED anchor: three, all green today and all must red. (a) add `session.run("MATCH (n) RETURN n")`
to `src/npc_engine/api/routes/quest/quest.py`; (b) add `raise Exception("x")` to any engine;
(c) add a 45-line function to `scripts/check_rules.py`. Revert all three.
Validation: `make check-rules` green on a clean tree after re-baselining `scripts/`.
CR-L02-04, CR-L05-05, CR-L08-04. ✅ AUTO (R1.6, 2026-08-28)

- [ ] **R1.7** ⏸️ ask-gate — DEC-224 is written; this task records the counterfactual audit
Files: `project-harness/DECISIONS.md`
Spec: DEC-224 (a gate must pass a recorded counterfactual before joining `make check`) is already
filed. What remains is the audit it implies: for each `make check` target, confirm its commit
references a counterfactual or the gate leaves. That is a judgment call per gate.
Skipped by the loop deliberately — needs a human.
Validation: `make check` lists 10 targets, not 14, once R1.2–R1.4 land.

- [x] **R1.8** Build the four approved new gates, warn-only
Files: `scripts/check_migrations.py`, `scripts/check_api_stability.py`,
`scripts/check_engine_logs.py`, `scripts/check_dead_tests.py`, `Makefile`
Spec: build them per DEC-224 — each ships with its own recorded counterfactual. Warn-only was
superseded on 2026-08-31: every surviving gate is **blocking**, with today's violation count as a
recorded baseline and any increase RED. That removes the warn-only state entirely, which is the
state R1 exists to eliminate, and needs no promotion criterion to remember later.
Landed as THREE gates, not four. `check_dead_tests` was deleted before commit: it duplicated
`check_test_quality` (same tree, same AST approach, overlapping EMPTY_TEST_BODY rule, a second
waiver marker), and as written it found 0 of the ~70 it predicted — any `ast.Call` counted as
signal. Its one real rule became `check_test_quality`'s sixth pattern, NO_ASSERTION, baselined at
25. The engine-log gate's "0% across 118 sites" was also wrong: 42 of 59 measured, now the baseline.
`check_migrations` reads a `MIGRATES = [(node_type, field)]` declaration in `scripts/migrations/`
rather than a root `migrations/` dir of `.cypher` files — the repo has one migration system and
now keeps one. Blocked debt: ISSUE-234 (25 assertion-free tests), ISSUE-235 (42 engine log sites).
RED anchor: one per gate, each pinned by a test rather than only demonstrated once —
(a) a required field with no migration reds, and greens once a migration declares it
(`test_check_migrations.py`); (b) a `/v1` response model that loses a field reds
(`test_check_api_stability.py`); (c) an engine `logger.info` without `duration_ms` above
baseline reds (`test_check_engine_logs.py`); (d) a test that calls the SUT and asserts nothing
is NO_ASSERTION (`test_check_test_quality.py`). 68 tests across the four files.
Validation: three gates exist, three run blocking, `make check` green. CR-L04-06, CR-L12-07,
CR-L05-02, CR-L14-06. ✅ AUTO (R1.8, 2026-08-31)

### Phase R2

Measurement. Holds the fifth CRITICAL. Nothing downstream is measurable until R2.1 lands.
Plans: `FIX_PLANS.md#r2`.

- [x] **R2.1** CRITICAL — unit tests make live network calls; CI records `None` model digests
Files: `evals/run_config.py`, `evals/engine_adapter.py`, `tests/unit/evals/test_run_config.py`,
`tests/unit/conftest.py`
Spec: `run_config.resolve()` falls back to `_engine_adapter.fetch_model_digest` (twice) and
`fetch_ollama_version` when no injector is passed (`run_config.py:260-262`), so 15 of 17 "unit"
tests make three real HTTP attempts each. Two changes: (a) require the injector under
`tests/unit/` via an autouse fixture that raises on real `httpx` use; (b) **make a `None` digest
fatal** in any run — per decision 2026-08-28, fatal everywhere, not just when publishing. Both
fetchers are documented to return `None` on failure, so on a CI runner with nothing on :11434 the
connection is refused instantly, the tests pass, and the run records
`generation_model_digest=None` — destroying the only field that makes a score attributable to a
model, which is exactly what the planned local-model swap depends on.
RED anchor: `python -m pytest tests/unit/evals/test_run_config.py -q` must complete in **under
5 s with no network**. Today it exceeds 120 s (collection 0.07 s, execution times out). Second
anchor: `test_resolve_raises_when_digest_unavailable` — call `resolve()` with a digest fn
returning `None`, assert it raises. Today it returns a RunConfig with `None` and no error.
Validation: `make test` unchanged in pass count; eval runs without Ollama now fail loudly.
CR-L15-01.

- [x] **R2.2** ⏸️ (live) — Neo4j in CI; gate `demo_game/`
Files: `.github/workflows/ci.yml`, `Makefile`, `.mypy_baseline_demo`,
`scripts/check_integration_baseline.py`, `scripts/integration_baseline.txt`
Spec: needs CI credentials and a push to observe the result, and R2.2 must model CI on
`docker-compose.test.yml` (DEC-232), not the base compose — bring it up as
`docker compose -f docker-compose.yml -f docker-compose.test.yml up -d neo4j`, **naming the
service**: a bare `up -d` also starts `app`, which needs a Dockerfile build and an `env_file`
`.env` that is not in the repo, so compose errors out. Wait for **bolt** to answer, not for the
container to report healthy (DEC-235 / ISSUE-232). Skipped by the loop — it cannot
observe a CI run. Depends on R2.1 and ISSUE-232 (done).
Corrected 2026-08-31: **no Ollama.** Zero tests under `tests/integration/` call an LLM, and
`requires_llm` is not a registered marker (`pyproject.toml` has only `asyncio`, `demo`,
`llm_eval`). CI runs `make check` wholesale (DEC-238), which first folds `test-cov-v13` and
`test-cov-full-report` into `check:` — they are `verify-v13` prerequisites, not `check` ones, so
dropping the duplicated CI steps without folding them in would delete two gates. 17 → 19 targets.
The integration gate ratchets on a **node-id allowlist**, not a bare count and not an expected
red: a count lets a newly-broken test hide behind a newly-fixed one. It must also assert a
minimum executed count — `_skip_if_no_neo4j()` calls `pytest.skip()`, so a job with missing env
vars passes green with all 34 tests skipped, which is the vacuity this task exists to remove.
Settles ISSUE-236.
Validation: re-run CR-L14-02's counterfactual in CI — stub 10 graph repository methods to return
constants and push; CI must red. Today it stays green (34 integration tests skip).
CR-L06-06, CR-L14-02, CR-L15-06, CR-L06-10, CR-L12-08, CR-L09-07.

- [x] **R2.3** Wire `check-base-rate`; delete `check-engine-coverage`
Files: `Makefile`, `scripts/check_base_rate.py`, `scripts/check_engine_coverage.py` (delete),
`docs/CAPABILITY_CASES.md`, `docs/CASE_SET_POLICY.md`, `docs/ENGINE_EVAL_COVERAGE.md`
Spec: L9 resolved this escalated conflict and it is not re-litigated. Wire `check_base_rate.py`
(386 lines — it measures the CR-L03-01 breach directly). Delete `check_engine_coverage.py` plus
its contract and test (658 lines, reachable from no `make` target and no CI job). Three docs
advertise both targets; correct them.
RED anchor: `grep -n 'check-base-rate' Makefile` returns 0 rows today. After wiring,
`make check-base-rate` must run and RED against the current corpus, whose YAML guard-case base
rate is 1.000 — a battery every responder passes.
Validation: `git grep -l check_engine_coverage` returns nothing outside `review-2026-08/`.
CR-L09-02, CR-L13-03.

- [x] **R2.4** Delete the guaranteed-pass assertions — own commit, before R2.5
Files: `evals/cases/**`
Spec: delete the 18 of 36 forbidden-keyword assertions that cannot fail, the dead `keyword_none`
expectation blocks, and the 3 `moderation_everyone_*` cases. **This must be its own commit.** If
it lands together with R2.5 the guard rate moves for two reasons at once and the delta is
unattributable — the same error that produced the 0.914 figure.
RED anchor: `make check-base-rate` measures exactly 1.000 today. After this task it must measure
below 1.000. Record the new rate in the commit message; it is the denominator everything later is
judged against.
Validation: the published guard score is EXPECTED to fall. That is the fix working, not a
regression. Diff against `BASELINE_2026-08-28.md` and state the delta.
Depends on R2.3. Blocks R2.5. CR-L03-08.

- [x] **R2.5** ✅ DONE 2026-09-02 — headline split, 0.914 retracted, engine≤null enforced
Files: `scripts/hedge_responder_probe.py`, `evals/report.py`, `evals/scorer_trust_policy.py`,
`evals/dashboard/headline.py`, `README.md`
Spec: **the loop stops here by agreement (2026-08-28).** Retracting a published claim is a
product decision, and the correct action depends on what the null baseline measures *after* R2.4
— which is not knowable in advance. The standing rule agreed is: never publish a headline where
engine ≤ null. Detail in `FIX_PLANS.md`. CR-L03-01, CR-L03-02.

**Gate answered (2026-09-01): split the headline permanently — DEC-243.** One rate per
expectation set; no combined guard figure is emitted anywhere. Landed:
(1) the split itself — `EvalSummary` loses `guard_rate`/`guard_ci_*`/`guard_passes`, `TrendRow`
gains `guard_adversarial`/`guard_anti_hallucination`, README drops `guard_rate` from its citable
vocabulary; (2) the null probe generalised so it can score guard batteries at all — its refusal
was why the baseline had never been taken; (4) the retraction banner on the now-tracked report.
(c) "retract 0.914 from the README" was already satisfied — verified: the README quotes no guard
rate, only the citation policy.

**ISSUE-256 — FIXED 2026-09-02 (step 3a below).** The null probe scored a case's AUTHORED
expectations only; the runner scored `_expected_with_guards` — authored plus injected
`min_length`, fallback `keyword_none`, `tone_judge`, `affirms_judge`. The first null measurement
was therefore not the engine's comparand. Both now score through one shared definition.

**Step 3 landed 2026-09-02, and it closes R2.5 — unfavourably, which is the point.**

*3a (ISSUE-256, now FIXED):* `expected_with_guards` hoisted into `evals/guard_expectations.py`;
the runner and the null probe import one definition. Re-measured once on the shared expectation
set with both LLM judges live: the canned hedge still scores **37/37 = 1.000** on the adversarial
battery. The rate did not move; its meaning did. The guards catch empty, canned and AI-revealing
responses, and a fluent hedge is none of those, so they do not discriminate against this null.

*3b (CR-L03-02, DEC-244):* the interval now decides — publication needs κ **and** the CI lower
bound ≥ 0.60 — and `headline.py` computes a real CI via `calibration.kappa_interval` instead of
passing `(0.0, 0.0)`. Note the review's phrasing understated this: the interval was not merely
ignored, it was **fabricated at the call site**. Measured blast radius: `tone_judge` flips
PUBLISH → refused, at κ=0.8493 with a CI of [−0.0100, 1.0000].

*3c (DEC-245):* no battery publishes a rate at or below its recorded null, per population and
never a union, in both the console and the markdown emitter. The null lives in
`evals/null_baseline.json` with its provenance (DEC-242's rule). Today only `adversarial` has a
recorded null, so only that headline refuses.

**Consequence:** the adversarial rate is no longer publishable at all, and R2.5 concludes with
the guarantee one battery short. Restoring it is case authoring, not a rule change — logged as
**ISSUE-257** (re-author the 37 adversarial cases so a hedge fails them).

- [x] **R2.6** ❌ RETIRED 2026-09-02 by DEC-250 — instrument repairs stop; the claim is retired
Spec: unparseable-verdict handling, aggregator join, reproducibility gate, MDE vs headroom,
model-digest content addressing, plus the case-existence filter (ISSUE-237). Each changes a
number, so none may run before the baseline is trustworthy.
CR-L03-03, CR-L03-06, CR-L03-09, CR-L03-10, CR-L03-11, CR-L16-08.
Revised 2026-08-31:
(a) **The aggregator join (CR-L03-06) is promoted AHEAD of R2.5.** One generation reports two
guard denominators — `trend_v1.jsonl` says `guard.n = 78`, the published report says `170/186`.
R2.5's engine-vs-null comparison and its rows-per-case halt condition are both computed against
whichever is right, so the join is measured and fixed first.
(b) **CR-L03-09** ("a third of the corpus has never been scored") was dropped by omission from
this line; it is in `FIX_PLANS.md`'s R2.6 heading and body. Plan it or descope it with a reason.
(c) **MDE vs headroom cannot start as specified** — `evals/mde.py` has no `mde()` and no
`headroom()`, and three rival κ families circulate (ISSUE-244). Calibration is authoritative;
reconcile and recompute before any judge-retirement call.
(d) The unparseable-verdict fix removes failures from the denominator, so the overall rate
**rises** — and `check-base-rate` reds on a rise. Its baseline re-record belongs there, not on
the case-existence filter, which moves the rate down where the ratchet is already content.

- [x] **R2.7** ❌ RETIRED 2026-09-02 by DEC-250 — apparatus frozen until R3 is green
Spec: trend stack (integrate then re-decide — 1 row today), sequence subsystem (keep and split,
8 consumers), token-budget re-measurement gate. CR-L03-05, CR-L03-12, CR-L10-01, CR-L01-07.
Corrected 2026-08-31: the re-measurement gate targets **`MEASURED_ROSTER_CEILING_TOKENS = 1151`**
(`tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py:45`, DEC-215), not
`TIER0_MAX_TOKENS = 380` — 380 is a design allocation from `docs/PROMPT_DESIGN.md:91`, never
measured, so it cannot be re-measured. Whether 380 is right is a runtime/product question for R3;
note `MEASURED_TIER_MAXIMA` records tier_a/b/c and has no tier-0 entry at all. Trend and sequence
are **510** and **808** lines of Python, not the 1,309 / 1,714 quoted (ISSUE-242). The trend
re-decision needs two rows sharing a model digest, which row 1 can never satisfy (ISSUE-246).

**R2.7b (ceiling re-measurement gate) — ✅ DONE 2026-09-01, DEC-242.** The measurement moved out
of the test into `scripts/ceiling_baseline.json` with its NPC / arm / corpus_sha / date, the
config test reads the artifact, `make check-ceiling-baseline` joined `make check` (21 → 22
targets), and `make probe-ceiling ARGS="--record --corpus-sha <sha>"` rewrites it. The gate does
not itself re-measure — that needs a live stack — it enforces that the number under test is a
recorded measurement that states what it measured.

**R2.7a (trend re-decision) — still blocked, and the block is structural.** ISSUE-246's exit
condition is two rows sharing a model digest. `trend_v1.jsonl` has one row, it carries no digest
field, and that generation's `meta.json` records `generation_model_digest: null`. Row 1 cannot
acquire a comparand retroactively, because a digest is a property of the run that produced it.
Unblocking needs a NEW generation run with CR-L15-01's fatal-`None`-digest fix already in place;
until that generation exists there is no second row, nothing to compare, and nothing to test.
It is a prerequisite, not a task — do not plan work against it.

### Phase R4

Subtraction and documentation. Mechanical and well-specified. Plans: `FIX_PLANS.md#r4`.

- [x] **R4.1** Delete the unreferenced archive; gitignore the one-shot prompt pattern ✅ AUTO (2026-08-28) — 229 files / 26,794 lines, DEC-225
- [ ] **R4.2** Document the two fresh-clone steps
Files: `README.md`, `CONTRIBUTING.md`
Spec: a fresh clone cannot boot. Two undocumented steps: `git config core.longpaths true` (the
archive deletion removed the deep paths, but the setting is still needed on Windows) and
`cp .env.example .env` — `.gitignore:61` ignores `.env` and only `.env.example` is tracked.
Add both to the quickstart. Also add the integration-test invocation from DEC-232.
RED anchor: verification command, not a test — `grep -c longpaths README.md CONTRIBUTING.md`
returns 0 today and must return ≥1 after.
Validation: follow the quickstart verbatim in a fresh clone and reach a running server.
CR-L16-01.

- [x] **R4.3** Delete dead code and phantom guards ✅ DONE 2026-09-02, DEC-246/247
Files: `tests/unit/engines/test_military_engine.py`, `src/npc_engine/engines/military/`,
`demo_game/` UI panels, `scripts/migrations/add_faction_support.py`, `docs/API.md`,
`docs/DATA_MODELS.md`, dead tests across `tests/`
Spec: delete the `session_kwarg` tests and 76 phantom docstring lines —
`military_engine.py:34` is `async def run_tick(self, *, tick_id: int)`, no `session` parameter,
while 61 references guard it. A live trap, not cosmetic. Collapse the duplicated `_draw_no_data`
helpers. Delete `add_faction_support.py` (dead since 2026-06-04) and its two doc mentions. Per
decision 2026-08-28, delete the 47 zero-call and 23 assertion-free tests — a test that calls
nothing or asserts nothing cannot fail — but **HALT and log a question on any test whose intent
is ambiguous** rather than guessing.

**Corrected 2026-09-02 — three of this spec's numbers do not reproduce, and one premise is
false.** Measured at HEAD with `__pycache__` excluded (its inclusion is what produced them):
`session_kwarg` references are **16 across 15 files**, not 61; phantom `**_` docstring lines are
**23 across 22 files**, not 76; the test-quality scan reports **25 NO_ASSERTION and 0 zero-call**,
not 47/23. And "a test that asserts nothing cannot fail" is **false for this population** — all
25 call the SUT and fail when it raises, which is the entire contract of
`test_save_swallows_graph_error`, `test_exception_does_not_propagate` and
`test_main_does_not_crash_on_cp1252_stdout`.

Two findings sharpen the trap rather than soften it: **no `run_tick` in `src/` accepts `**_`**
(the shim is gone from every signature), and **not one of the 15 tests passes `session=`** — so
a test "fixed" to actually pass it would `TypeError` on all 15. Both ends documented a contract
false at both ends; `tick_scheduler.py` carried 27 more of the same.

Landed: 23 phantom docstrings + 27 scheduler signatures corrected; 7 tests renamed to what they
actually assert and 8 deleted as verified strict subsets (DEC-246); `_draw_no_data` collapsed to
two shared helpers, not one — the three wrapping copies and the two single-line copies render
differently; `add_faction_support.py` deleted with both doc mentions repointed at
`schema_bootstrap.py`; 25 assertion-free tests annotated and the baseline ratcheted 25 → 0
(DEC-247). Nothing was ambiguous, so no HALT was needed.
RED anchor (corrected): `grep -rn session_kwarg tests/ src/ --include=*.py | grep -v __pycache__
| wc -l` returned 16, now 0; `grep -rn add_faction_support docs/` returned 2 files, now 0;
`python scripts/check_test_quality.py` reported 25 findings, now 0.
Validation: `make test-demo` still passes 1,116 tests after the `_draw_no_data` collapse; `make
check` green. CR-L14-01, CR-L09-06, CR-L08-07, CR-L14-06, CR-L04-02.

- [x] **R4.4** ✅ DONE 2026-09-02 — `CLAUDE.md` 483 → 230, narrative moved to skills, DEC-248/249
Files: `project-harness/CLAUDE.md`, `.claude/skills/*`
Spec: scope agreed 2026-08-28 — **stays in CLAUDE.md** (paid every session): the layer model and
forbidden cross-layer patterns, and the ask-before-doing list plus the issues/decisions protocol.
**Moves to skills**: code style, documentation formats, testing discipline, coding principles.
**Deleted**: the 4-field engine-log mandate (0% compliance across 118 sites — now gated by R1.8
instead), the "every session reads ISSUES.md" mandate, the 3 pre-merge checklist items naming
things that do not exist. Rewrite DIP-strict to require 2+ implementors or 3+ callers. Replace
every factual claim with a pointer to the file holding the truth.
Skipped by the loop: deciding what an agent must read before its first tool call is a judgment
call, and getting it wrong degrades every later session. Depends on R1 complete.

**Landed 2026-09-02 at 483 → 230 lines** (the spec's "476" was measured wrong; it was 483).
Two corrections to the spec's assumptions. First, `.claude/skills/` **had never existed**, and
`.gitignore:64` was `.claude/` — the directory form — so every skill file would have been
silently untracked; a negation under a directory-form exclusion is inert, verified in a throwaway
repo. `.gitignore` now excludes `.claude/*` and negates the two shared directories (DEC-248).
Second, the engine-log mandate's compliance is 0 of **~76** engine logger sites, not 118 — the
numerator was right, the denominator was not.

One factual claim was **kept, not pointer-ised**: the Stack table's LLM row, because
`tests/unit/evals/test_model_identity.py` parses it and reds when it disagrees with any engine's
`llm_config.yaml`. Removing it in the first draft reddened `make check`. The rule is therefore
"no *ungated* copies" — a copy a gate pins cannot drift silently. DEC-249 also records the
skills failure mode: CLAUDE.md is auto-loaded, a skill is only invoked, so an unloaded skill
silently stops enforcing its rule. Every strict rule stays named in CLAUDE.md for that reason,
with `make check` as the real backstop. Closes ISSUE-251.
Validation: `wc -l project-harness/CLAUDE.md` ≤ 250 (476 today); every remaining numeric claim
reproduces from its cited command (26 of 109 fail today). CR-L09-04 +7.

- [ ] **R4.5** Ledger hygiene — reused IDs, stale P1s, dead queue file
Files: `project-harness/ISSUES.md`, `project-harness/DECISIONS.md`,
`project-harness/archive/ISSUES_RESOLVED.md`, `project-harness/SKILLS_QUEUE.md`, `scripts/`
Spec: repair the 5 reused DEC ids and 2 reused ISSUE ids — assign the duplicates new ids and
leave a redirect line at the old heading. Close ISSUE-145 (stale P1, root cause fixed under other
ids) and ISSUE-122 (prescribes a fix already present when filed), moving both to the archive.
Retire `SKILLS_QUEUE.md` (dead ~90 days, still normatively referenced). Fix the three scripts
sharing one hardcoded stale corpus default.
RED anchor: write a duplicate-id detector over `DECISIONS.md` + `ISSUES.md` +
`archive/ISSUES_RESOLVED.md`. It returns 7 collisions today and must return 0. Keep the detector
— it is cheap and this recurred.
Validation: `grep -c 'ISSUE-145' project-harness/ISSUES.md` returns 0 (moved to archive).
CR-L07-02, CR-L07-01, CR-L07-04, CR-L07-06, CR-L07-07, CR-L07-08.

- [ ] **R4.6** Documentation repair — delete numbers from prose, cite the files
Files: `project-harness/HARNESS_GATES.md`, `CONTRIBUTING.md`, `README.md`, `CHANGELOG.md`,
`docs/API.md`, `src/npc_engine/retrieval/context/context_builder.py`, `Makefile`
Spec: **delete drifting numbers rather than correcting them** — correcting schedules the next
drift. `HARNESS_GATES.md:33-34` says "57 today" and "256 today" against a live 133 and 0,
untouched 85 days: replace both with a new `make harness-status` target that prints live values,
and fix the "one command" table that lists 5 of the 14 gates. `CONTRIBUTING.md`: 5 links to a
`project/` directory that does not exist, plus a missing seed step. `README.md`: the "Key files"
table points at a dead source layout, "What's next" lists finished work as open TODOs, and
"Migration scripts" names two absent files. `docs/API.md`: add the 6 newest live routes.
`CHANGELOG.md`: 96 commits stale. `context_builder.py`'s size-justification comment understates
the file (799 lines) by 78%.
RED anchor: `grep -rn 'project/' CONTRIBUTING.md README.md CHANGELOG.md` returns 5+ rows today
and must return 0. Second: a 5-line script asserting every path in README's "Key files" table
exists — fails today on the source-layout rows.
Validation: `make harness-status` prints numbers matching `wc -l scripts/rules_baseline.txt` and
`cat .mypy_baseline`. CR-L13-01, CR-L13-02, CR-L13-04, CR-L13-08, CR-L13-09, CR-L10-02,
CR-L08-08, CR-L06-12.

- [ ] **R4.7** Delete the remaining one-shot artifacts
Files: `live_openapi.json`, `Makefile`, `project-harness/`
Spec: delete `live_openapi.json` (182,118 bytes, dated 2026-06-24, zero code consumers — verified
by `git grep`) and add a `make openapi` target that regenerates it on demand. This replaces a
stale committed artifact with a command, which is the R4.6 principle applied to a file.
RED anchor: `git grep -l live_openapi.json` returns rows outside `review-2026-08/` today and must
return none after. `make openapi` must produce a schema that differs from the deleted file —
proving the committed one was stale.
Validation: `make check` green. CR-L08-09, CR-L13-11.

### Phase R3

**THIS IS THE ACTIVE PHASE (DEC-250, 2026-09-02).** Everything before it is done, retired or
frozen. Work order is fixed: **R3.6 → R3.1 → R3.2 → R3.4**. R3.6 is report-only and goes first so
the eight unknown integration failures are sized before anything is committed to. R3.1 must
precede R3.2 — the degradation ladder's bare `except Exception` would swallow a
`GraphUnavailableError` before any handler saw it.

**Programme exit condition (DEC-250):** R3 green and the integration suite at zero unexplained
failures. Not an empty issue list — that never happens. Anything found after that is ordinary
backlog, not programme scope.

Product correctness — the safe half. Gossip (R3.3) and the fallback-policy decision are outside
the loop's scope. Needs services: bring up the test override first. Plans: `FIX_PLANS.md#r3`.

- [x] **R3.1** ✅ DONE 2026-09-02 — Stop the degradation ladder swallowing infrastructure errors
Landed as `DEGRADABLE_EXCEPTIONS = (TimeoutError, LLMTimeoutError, LLMRequestError)`; everything
else propagates. **Spec corrected (DEC-251):** "LLM timeout, retrieval miss" names two things
that cannot arrive — `llm_client.py:102-107` already converts both LLM errors into a successful
`full` tier, and a retrieval miss is an empty list, not an exception. Only `TimeoutError` is
reachable. Four unit tests asserted the bug and were rewritten. Side effect and a fix:
`dialogue.py:97`'s 400 handler was unreachable dead code and is now live.
Files: `src/npc_engine/engines/dialogue/degradation.py`,
`src/npc_engine/api/routes/dialogue/dialogue.py`
Spec: `degradation.py:107` and `:119` are bare `except Exception` blocks that log and fall
through to the next tier, ending at a canned 200. Narrow both to the exceptions that SHOULD
degrade (LLM timeout, retrieval miss) and let infrastructure errors propagate. **This blocks
R3.2** — a `GraphUnavailableError` raised by R3.2 would be caught by the first of these and
converted into a successful response before any handler ran. The review filed these separately
and never linked them.
RED anchor: `tests/integration/test_degradation.py::test_graph_outage_is_not_degraded_to_canned`
— inject a `ServiceUnavailable` from the graph factory, assert it propagates. Today it returns
HTTP 200 with the canned tier.
Validation: `make check` green. Errors that used to degrade silently now surface — that is the
point, and it will look like new breakage. CR-L01-04.

- [x] **R3.2** ✅ DONE 2026-09-02 — CRITICAL — implement the Neo4j→503 contract
Wrapped `GraphDB.get_session()`, the single driver boundary: an exception in any caller's
`async with` body returns at the `yield`, so one narrow catch covers ~250 repository sites and 87
`run_in_tx` paths. 503 handler returns the canonical `ErrorEnvelope` with a **redacted** message
(never `str(exc)` — it renders the bolt URI, L1-02/SEV-16). **RED anchor re-anchored:**
`tests/integration/` has no conftest, no fixtures and no `TestClient`, so "stop the container" was
not executable; an unreachable bolt port raises a genuine `ServiceUnavailable` instead.
`TokenBudgetExceededError` fixed as specified **and** `ContextBudgetError`, the twin that is
actually raised. Also closed triage cause A (2 tests): a bare `count(r)` aggregate always returns
one row, so both faction `raise` guards were unreachable.
Files: `src/npc_engine/graph/` driver boundary,
`src/npc_engine/api/errors/exception_handlers.py`, `src/npc_engine/utils/errors.py`
Spec: `grep -rn "raise GraphUnavailableError" src/` returns 0 rows; so does
`grep -rn "503" src/npc_engine/api/`. `register_exception_handlers()` registers four handlers,
none for it, so the catch-all returns 500 — while three docstrings promise the contract. Catch
`neo4j.exceptions.ServiceUnavailable` and `SessionExpired` at the driver boundary, raise
`GraphUnavailableError(uri=..., cause=...)`, register a 503 handler returning the canonical
`ErrorEnvelope`, and make `TokenBudgetExceededError` subclass `StructuredNPCSystemError` rather
than bare `Exception` (`errors.py:301`). Implement rather than delete the claim: the Unreal
DemoGame is a real client and must distinguish "retry" from "your request is broken".
RED anchor: `tests/integration/test_graph_outage.py::test_neo4j_outage_returns_503` — stop the
neo4j container, POST `/v1/dialogue`, assert 503. Today it returns 500. Assert the body is an
`ErrorEnvelope`, not a canned dialogue reply — that guards against regressing to R3.1's failure.
Validation: needs `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d`.
Depends on R3.1. CR-L08-03, CR-L02-01, CR-L01-06, CR-L05-01.

- [x] **R3.4** ✅ DONE 2026-09-02 — Engine wiring — the four independent fixes
(a) `memory_consolidation_engine` wired; its `run_tick` was dead in production — the HTTP route
is `POST /memories/consolidate/{npc_id}` and calls `consolidate()`, not `run_tick()`. (b) Guard
at the composition root, not `TickScheduler.__init__` — 26 of 28 slots are legitimately Optional
for tests. Slot list derived from `inspect.signature`, so a future unwired slot reds it
automatically. (c) Event-sampling seed logged. (d) Source-string test replaced; counterfactual
measured — with the mapping deleted the new test reds and the old one stayed green.
**Triage cause B refuted:** two tests, two unrelated causes, neither the `None`-slot bug.
Files: `src/npc_engine/api/dependencies_engines/__init__.py`,
`src/npc_engine/scheduler/tick_scheduler.py`, `src/npc_engine/engines/`, `tests/`
Spec: four small independent fixes. (a) Pass
`memory_consolidation_engine=get_memory_consolidation_engine()` into `get_tick_scheduler()` — one
kwarg. Note the corrected claim: the engine is NOT dead code, it is reachable via
`POST /memories/consolidate` (`memories.py:275`); only the tick path never runs it. (b) Add a
composition-root assertion that every `TickScheduler` engine slot is non-`None` —
`tick_scheduler.py:530` silently no-ops a `None` slot, which is the general form of (a).
(c) Log the event-sampling RNG seed, as gossip already does. (d) Replace the source-string test
that "guards" the retrieval-profile 4xx without exercising it.
RED anchor: (a) assert `TickScheduler` runs consolidation on a tick — today
`self._memory_consolidation_engine is None` short-circuits. (b) set any engine slot to `None`,
assert startup raises — today it starts and silently skips. (d) delete the 4xx-raising code and
assert the test reds — today it passes, because it asserts on source text.
Validation: `make check` green. Excludes CR-L01-08 (EngineFallbackPolicy wire-or-delete is a
decision) and CR-L01-10 (touches gossip). CR-L01-03, CR-L01-09, CR-L01-11, CR-L01-05.

- [ ] **R3.5** Give `BaseEngine.run_tick` a real signature
**Spec corrected 2026-09-02 (DEC-251): the converter half is already true and is struck from
this task.** `_to_native` is defined once, at `graph_reader.py:199`, and used only in that file;
the validation command `grep -rlc '_to_native' src/` already returns 1, not 3. There is no
triplication to collapse. Only the `BaseEngine.run_tick` signature half is real, and it touches
all 28 engines — treat it as its own session.
Files: `src/npc_engine/engines/base_engine.py`,
`src/npc_engine/retrieval/context/context_builder_helpers.py`,
`src/npc_engine/graph/graph_reader.py`
Spec: `base_engine.py:24` is `async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str,
Any]` — it types 33 scheduler parameters and enforces nothing, so mypy stays clean with an
incompatible engine. Replace with an explicit signature or a Protocol with real parameters. Excludes CR-L02-05 (raw
dicts at 145 functions) — that is R7.1. The converter half is struck; see the note above.
RED anchor: add an engine whose `run_tick` takes an incompatible parameter and assert `make type`
reds. Today mypy passes — `*args, **kwargs` accepts anything. This is the counterfactual
CR-L14-04 is built on.
Validation: `make check` green. CR-L14-04. (CR-L14-05 is void — see the note above.)

- [x] **R3.6** ✅ DONE 2026-09-02 — 8 failures triaged to **5 causes**; recorded in ISSUE-233.
A+D already fall inside R3.2/R3.4; B is likely one fix for two tests; only C (faction gossip
pair selection) and E (reputation label boundary) are new, both S–M. **No structural problem
found** — contracts not implemented and wiring not completed, not a design that needs rework.
Note: the env vars are load-bearing — without them the suite reports "9 passed, 34 skipped"
and looks green while testing nothing.
Files: `project-harness/ISSUES.md` (append findings only)
Spec: with bolt reachable, `pytest tests/integration` returns **35 passed / 8 failed / 0
skipped** (re-measured 2026-09-01 by R2.2, settling ISSUE-236 — the count was recorded as 9 and
is really 8; `test_faction_integration.py::test_set_standing_independent_directions` passes).
The passing ones pass on first execution ever. The 8 have never been evaluated. They are the
committed allowlist in `scripts/integration_baseline.txt`, so they cannot grow silently while
this triage waits: `make check-integration-baseline` reds on a ninth. **Standing rule agreed 2026-08-28:
triage and report only — change no test and fix no code.** Open each of the eight, classify it as
defect / stale expectation / fixture gap with one line of evidence, and append the classification
to ISSUE-233. One is already confirmed a genuine defect
(`FactionService.remove_member()` silently no-ops on a non-member instead of raising
`FactionMembershipError`); the other seven are unknown and must not be assumed either way.
Do NOT edit a test to make it pass — the easiest way to green a red test is to edit it, and
`loop_gates.py`'s own docstring calls that fraud.
RED anchor: none — this task deliberately changes no behaviour. Its verification is that
`git diff --stat` touches ONLY `project-harness/ISSUES.md`.
Validation: eight classifications appended, each with a file:line or a pasted assertion.
When one is fixed, drop it from `scripts/integration_baseline.txt` via
`make check-integration-baseline-update` — the gate nags until you do.
Needs the test override running. ISSUE-233, CR-L14-02.

<!-- LOOP:QUEUE end -->

## Outside the queue

These need a human, or must not run unattended.

### R5 — Integrator-facing

The Unreal DemoGame is a real external consumer now (DEC-229), so these stopped being
hypothetical. Plans: `FIX_PLANS.md#r5`.

- [ ] R5.1 API stability policy + breaking-change contract test — **do first in this phase**; cheap now, expensive once Unreal binds · CR-L12-07
- [ ] R5.2 Python 3.14 everywhere; install `torch`/`sentence-transformers` · DEC-230 · CR-L16-06, CR-L16-04
- [ ] R5.3 Make `make package` build — its spec names `config/` and `game_schema.yaml`, neither of which exists · CR-L12-02
- [ ] R5.4 Migration down paths + applied-state record — 0 of 7 have either · CR-L04-01, CR-L04-06, CR-L04-05
- [ ] R5.5 Ops: image staleness, non-root, app healthcheck, default creds, lockfile, NFR measurement · CR-L16-03 +5

### R6 — Overnight loop rework

**Excluded from the queue on principle:** these edit `expand_loop.sh` and `loop_gates.py`, which
are the driver executing the queue. A loop rewriting its own driver mid-run produces a night that
cannot be diagnosed. Run these with the loop stopped.

- [ ] R6.1 Fix ISSUE-126 — `--dry-run` never terminates, and the deeper cause: tasks are ticked by the *session*, not the driver, so a session that completes without ticking re-runs forever · CR-L11-09
- [ ] R6.2 Classify HALT causes so a self-test failure is not a product HALT — every HALT to date was the harness tripping over its own self-tests · CR-L11-03

### R7 — Deferred large work

- [ ] R7.1 Pydantic models at `BaseEngine.run_tick()` / `generate_structured()` — 145 functions, XL. Do not start before R2 is green · CR-L02-05
- [ ] R7.2 Debt with no urgency: the four file splits behind R1.1, `config.py` fan-in 74, single-caller DIP port cull, `intent_queries.py` coverage, double mypy run, ruff rule set · CR-L14-03 +9

### Parked

- [ ] B2B / Unreal integration track — **deliberately paused** (DEC-229) until engine work lands and smaller fine-tuned local models free the VRAM budget. See `UNREAL_DEFERRED.md`.
