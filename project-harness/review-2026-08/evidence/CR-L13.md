# CR-L13 — Truth-in-documentation

Scope: all 22 files in `docs/`, plus `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, and
the named-state `project-harness/*.md` files (`HARNESS_GATES.md`, `ROADMAP.md`,
`EVAL_STRATEGY.md`, `HANDOFF_TRACK_A.md`, `HANDOFF_TRACK_B.md`, `MORNING_HANDOFF_*.md`).
`project-harness/CLAUDE.md` is L5's — noted where relevant, not scored here.

Repo state: branch `eval-ab-context-arms`, HEAD `d46ae42`, live API server reachable at
`http://127.0.0.1:8000`.

## Required measurements

### 1. Claims checked / false / unverifiable

**Method:** extracted every quantitative claim (number, threshold, path, command name)
and every state claim ("X is implemented/gated/stale") from the in-scope docs by targeted
grep + manual reading, then verified each by: running the command, reading the
referenced source file, or diffing against the live API. Full `make check` was also run
to completion (twice — see §2/§6) rather than assumed. 74 discrete claims were checked;
the sample concentrates on the docs that make the most decision-relevant claims
(HARNESS_GATES.md, CONTRIBUTING.md, README.md, CASE_SET_POLICY.md/CAPABILITY_CASES.md/
ENGINE_EVAL_COVERAGE.md, API.md, CHANGELOG.md, EVAL_STRATEGY.md, ROADMAP.md header) since
those are where a false number changes a decision; the remaining docs (ARCHITECTURE.md,
DATA_MODELS.md, ENGINES.md, etc.) were spot-checked for path/command validity only.

| Metric | Count |
|---|---|
| Claims checked | 74 |
| Claims FALSE | 29 |
| Claims unverifiable (historical, not re-derivable without git archaeology) | 3 |

**Claims false — table:**

| Doc:line | Claim | Measured truth | How measured |
|---|---|---|---|
| `project-harness/HARNESS_GATES.md:33` | "`scripts/rules_baseline.txt` — grandfathered CLAUDE.md rule violations (**57** today)" | File has **133** violation entries (136 lines − 3 comment-header lines); `make check-rules` itself reports "133 grandfathered" | `wc -l scripts/rules_baseline.txt`; ran `python scripts/check_rules.py` → `check-rules: OK - no new violations (133 grandfathered).` |
| `project-harness/HARNESS_GATES.md:34` | "`.mypy_baseline` — grandfathered mypy error count (**256** today)" | File contains **`0`** | `cat .mypy_baseline` → `0` |
| `project-harness/HARNESS_GATES.md:11` | "`make check` = `lint + check-rules + type-ratchet + check-harness + test-cov(80% floor)`" | Actual `check:` recipe (Makefile:200) has **14** deps: `lint check-rules check-evals-rules check-layers check-docstrings type type-evals check-harness check-human-gates check-test-quality check-conservation check-label-survival test-cov test-cov-evals`. It depends on `type` (plain `mypy src/`, Makefile:101-102), not `type-ratchet` (Makefile:122-123, a separate target `make check` never calls) | `grep -n "^check:" Makefile`; `grep -n "^type:\|^type-ratchet:" -A2 Makefile` |
| `docs/CASE_SET_POLICY.md:94` | "Measured and gated by `scripts/check_base_rate.py` (`make check-base-rate`)" | `make check-base-rate` does not exist as a target | `make check-base-rate` → `make: *** No rule to make target 'check-base-rate'.  Stop.` |
| `docs/CAPABILITY_CASES.md:69` | "`make check-engine-coverage` fails when a unit exists with no classification row" | Target doesn't exist | `make check-engine-coverage` → `make: *** No rule to make target 'check-engine-coverage'.  Stop.` |
| `docs/ENGINE_EVAL_COVERAGE.md:4` | "Gated by `scripts/check_engine_coverage.py` (`make check-engine-coverage`)" | Same target, same failure | Same command, same output |
| `project-harness/EVAL_STRATEGY.md:152` | "`make eval-full`" (Running the Full Eval Suite) | Target doesn't exist | `make eval-full` → `make: *** No rule to make target 'eval-full'.  Stop.` |
| `docs/ARCHITECTURE.md:677` | Quick-start snippet: `make seed` | Target doesn't exist (real ones are `seed-api`, `seed-probe`, `seed-village-world`, `seed-tavern-world`, `demo-seed`) | `make seed` → `make: *** No rule to make target 'seed'.  Stop.` |
| `project-harness/EVAL_STRATEGY.md:158` | `python seeds/world/seed_tavern_world.py` | Path is `seeds/worlds/seed_tavern_world.py` (plural) | `ls seeds/worlds/seed_tavern_world.py` exists; `seeds/world/` does not |
| `project-harness/EVAL_STRATEGY.md:116` | `seeds/world/run_eval_world.py` | Path does not exist anywhere in the repo (not even under `seeds/worlds/`) | `find . -iname run_eval_world.py` → no result |
| `CONTRIBUTING.md:39,44,49` | "All tests must be green... See `project/CLAUDE.md` § 'Pre-merge checklist'"; "Read `project/CLAUDE.md` before writing any code" | `project/` directory does not exist; canonical path is `project-harness/CLAUDE.md` | `ls project/` → No such file or directory |
| `CONTRIBUTING.md:56` | "anything you notice but do not fix goes in `project/ISSUES.md`" | Path is `project-harness/ISSUES.md` | Same |
| `CONTRIBUTING.md:57,71` | "write a `project/DECISIONS.md` entry" | Path is `project-harness/DECISIONS.md` | Same |
| `CONTRIBUTING.md:30` | `python -m npc_engine.scripts.seed` (graph seeding step) | Module does not exist | `python -m npc_engine.scripts.seed` → `No module named npc_engine.scripts.seed`; only `demo_game/seeds/seed.py` and `seeds/worlds/*` exist |
| `CHANGELOG.md:8` | "recorded in `project/STATUS.md`" | Path does not exist | `ls project/` fails |
| `CHANGELOG.md:35` | "`project/STATUS.md` — added project health snapshot header" | Same | Same |
| `CHANGELOG.md:36` | "`project/PATTERNS.md` — added Common Anti-Patterns section" | Path is `project-harness/PATTERNS.md` | Same |
| `CHANGELOG.md:36,40` | "migrated from `docs/LLM_GENERATION_GUIDE.md`" / "Removed: `docs/LLM_GENERATION_GUIDE.md`" | File does not exist at that path (never re-verified after the project/→project-harness/ rename) | `find . -iname LLM_GENERATION_GUIDE.md` → no result |
| `CHANGELOG.md:41` | "`project/proposals/WRITE_PATH_CONVERGENCE_P0.md` — moved to `archive/`" | Path does not exist | `ls project/proposals/` fails |
| `CHANGELOG.md:42` | "`project/proposals/refactor.md` — moved to `archive/`" | Same | Same |
| `README.md:77` | `[npc_engine/main.py](npc_engine/main.py)` | Path is `src/npc_engine/main.py` | `ls npc_engine/main.py` fails; `ls src/npc_engine/main.py` succeeds |
| `README.md:78` | `[npc_engine/config.py](npc_engine/config.py)` | Path is `src/npc_engine/config.py` | Same pattern |
| `README.md:79` | `[npc_engine/engines/dialogue/]` | Path is `src/npc_engine/engines/dialogue/` | Same |
| `README.md:80` | `[npc_engine/type_registry/]` | Path is `src/npc_engine/type_registry/` | Same |
| `README.md:81` | `[npc_engine/retrieval/]` | Path is `src/npc_engine/retrieval/` | Same |
| `README.md:84` | `[tests/scenarios/]` | Path doesn't exist; real e2e scenario dir is `e2e/scenarios/` (per project-harness/CLAUDE.md's own test-layout section and the `scenarios` Makefile recipe) | `ls tests/scenarios/` fails; `grep -n "^scenarios:" -A2 Makefile` shows `pytest e2e/scenarios/` |
| `README.md:85` | `[proposals/]` (Design proposals) | Path doesn't exist at root; real path is `project-harness/proposals/` | `ls proposals/` fails |
| `README.md:38` | "`tone_judge` matcher is a stub; wire in LLM-as-judge" | `_eval_tone_judge` in `evals/matchers.py:272` is a working YES/NO LLM-judge call using `prompts/eval/tone_judge.yaml`, not a stub | Read `evals/matchers.py:196,272-290`; `prompts/eval/tone_judge.yaml` is a real 25-line judge prompt template |
| `README.md:34` | "`dialogue_handler.py` currently passes `archetype=\"default\"` to the canned tier; wire in a lightweight graph lookup" | `dialogue_handler.py:220,384` already does the graph lookup: `archetype = await self._dialogue_repo.get_npc_archetype(request.npc_id) or "default"` — "default" is only the fallback | `grep -n archetype src/npc_engine/engines/dialogue/dialogue_handler.py` |
| `README.md:32,33` | "`proposals/prompt_inventory.md` is ready, awaiting approval"; "Pick one of the three options in `proposals/delta_log_options.md`" | Both files are filed under `project-harness/archive/stale-2026-06/` by the project's own archival process — not pending, not even at the path named | `find . -iname delta_log_options.md -o -iname prompt_inventory.md` |

**Notable TRUE claims** (included to show the check was not one-sided): `docs/API.md`
rate-limit defaults (50 req/s, burst 100) match `config.py:250-251` exactly; the
`[0.55, 0.85]` base-rate band in `docs/CASE_SET_POLICY.md:92` matches
`scripts/base_rate_contract.py:32-33` exactly; `docs/ENGINE_EVAL_COVERAGE.md`'s "18 of 44
units qualify" and "tested by `tests/unit/scripts/test_check_engine_coverage.py`" are both
true (script re-run gives 44/44, 18 dialogue_observable; test file exists, 15/15 pass);
CI's "Python pinned to 3.14" (`HARNESS_GATES.md:60`) is true across all 5 job definitions
in `.github/workflows/ci.yml`; ROADMAP.md's "`make check` GREEN" (line 6) is **Confirmed**
— a full `make check` run completed with exit code 0 (1007 passed, 1 skipped, 79.76%
eval coverage against a 75% floor, 80% floor met on the main suite).

**Unverifiable (3):** `HARNESS_GATES.md:5`'s "2026-06-03 review surfaced (38 lint, 254
type errors, 11 oversized files, silent CI)" and `ROADMAP.md:4`'s "SEV backlog... fully
drained (47/47)" and "EXP-201..230... fully shipped" describe historical/aggregate states
at a past commit that would require checking out and re-running tooling against dozens of
historical revisions to re-derive — not attempted given scope.

### 2. `scripts/check_harness_honesty.py`

Read in full (`scripts/check_harness_honesty.py`, 106 lines). Ran both modes:

```
$ python scripts/check_harness_honesty.py
check-harness: OK - 67 open ticket(s); debt is tracked, docs consistent.
(exit 0)

$ python scripts/check_harness_honesty.py --strict
check-harness: OK - 67 open ticket(s); debt is tracked, docs consistent.
(exit 0)
```

**`--strict` currently flags nothing, and cannot, structurally, today:**

- **H1** (lint red / mypy baseline>0 without a covering ISSUE) never fires: `ruff check
  src/ evals/` returns "All checks passed!" and `.mypy_baseline` is `0`.
- **H3** (ISSUES.md has open tickets but NEXT_SESSION.md claims none) is **dead code**:
  `NEXT_SESSION.md` is read via `_read()`, which returns `""` for a missing file — and
  `project-harness/NEXT_SESSION.md` does not exist (it only exists at
  `project-harness/archive/stale-2026-06/NEXT_SESSION.md`). The regex can never match an
  empty string, so this check has not fired, and cannot fire, regardless of what's in
  ISSUES.md, until someone recreates that file.
- **H2** (ROADMAP says "complete" while new `.py`/`.yaml` files sit untracked under
  `evals/`, `tests/`, `src/`) is live in principle (ROADMAP.md does contain "complete" 28
  times) but `git status --porcelain` currently shows zero untracked files matching that
  filter — only three untracked `.md` files, which the check ignores by extension.

**Conclusion:** the honesty gate is advisory by design (per its own docstring) and today
is *also* a no-op in practice — none of its three checks are in a state where they could
fail, one of them (H3) cannot fail at all until a file that was moved to `archive/` is
restored to its original path. `--strict` changes zero behavior against the current tree.

### 3. Documented `make` targets vs Makefile (100 real targets, 693 lines)

| Doc | Target mentioned | Exists? |
|---|---|---|
| `docs/ARCHITECTURE.md:676` | `install` | Yes |
| `docs/ARCHITECTURE.md:677` | `seed` | **No** |
| `docs/ARCHITECTURE.md:678` | `run` | Yes |
| `docs/API.md` | `seed-api`, `smoke`, `scenarios` | Yes (all 3) |
| `docs/CAPABILITY_CASES.md:69` | `check-engine-coverage` | **No** |
| `docs/CAPABILITY_CASES.md:173,188` | `seed-village-world`, `seed-tavern-world` | Yes |
| `docs/CAPABILITY_CASES.md:53,135` / `docs/REASONING_DIMENSIONS.md:201` | `hedge-probe` | Yes |
| `docs/CASE_SET_POLICY.md:74` | `check-dead-keywords` | Yes |
| `docs/CASE_SET_POLICY.md:94` | `check-base-rate` | **No** |
| `docs/DATA_MODELS.md:207` | `check-contracts` | Yes |
| `docs/DEMO.md`, `docs/DEMO_SCRIPT.md` | `eval-llm-demo`, `demo-seed`, `demo`, `demo-video`, `demo-run` | Yes (all) |
| `docs/ENGINE_EVAL_COVERAGE.md:4,99` | `check-engine-coverage` (**No**), `eval-arm-probe` (Yes) | mixed |
| `docs/SCORER_TRUST_POLICY.md:5` | `eval-calibrate` | Yes |
| `README.md` | `demo-seed`, `demo`, `test`, `eval` | Yes (all) |
| `CONTRIBUTING.md:39-41` | `test`, `eval`, `smoke` | Yes (all) |
| `CHANGELOG.md:19` | `seed-probe` | Yes |
| `project-harness/CLAUDE.md` | 12 targets (`demo-seed`, `demo`, `demo-run`, `test`, `test-demo`, `eval-llm-demo`, `demo-village`, `demo-tavern`, `seed-village-world`, `seed-tavern-world`, `eval-report`, `demo-snapshot`, `check-layers`) | Yes (all 13) |
| `project-harness/HARNESS_GATES.md` | `lint`, `check-rules`, `type-ratchet`, `test-cov`, `check-harness`, `check-contracts`, `check-rules-update`, `type-ratchet-update` | Yes (all exist as targets — the doc's *bug* is that `check` doesn't call `type-ratchet`, not that `type-ratchet` is missing) |
| `project-harness/EVAL_STRATEGY.md:152` | `eval-full` | **No** |
| `project-harness/EVAL_STRATEGY.md:155` | `eval-llm-demo` | Yes |
| `project-harness/HANDOFF_TRACK_A.md:290` | `check-base-rate` (self-documented as "not in `make check`, by design, until EVAL-P26.2") | **No** target, but doc is honest about it being unwired — contrast with `docs/CASE_SET_POLICY.md` and `docs/CAPABILITY_CASES.md`, which present the same command with no such caveat |
| `project-harness/HANDOFF_TRACK_A.md:309` | `review-cases` (explicitly "the ... recipe **proposed** ... is library-only") | **No** — but framed as a proposal, not a claim, so not counted as false |

**Summary:** of the make targets actually asserted as *currently runnable* (not
"proposed"/"planned"), **4 are dangling**: `seed`, `check-engine-coverage`,
`check-base-rate` (asserted twice, in `docs/CASE_SET_POLICY.md` and
`docs/CAPABILITY_CASES.md`/`docs/ENGINE_EVAL_COVERAGE.md`), `eval-full`. Everything else
sampled across the ~30 docs checked resolved to a real target.

### 4. Dangling file paths

Extracted every `src/docs/evals/tests/scripts/project-harness/seeds/prompts/demo_game/e2e`
path with a file extension (`.py .md .yaml .yml .json`) from the in-scope docs (293 unique
paths) and tested each with a filesystem check.

**42 raw misses**, of which **13 are genuine current-state lies** (listed in the claims
table above: `project/*` × 8 in CONTRIBUTING.md/CHANGELOG.md, `npc_engine/*` × 5 in
README.md, plus `tests/scenarios/`, `proposals/`, `seeds/world/*` × 2,
`docs/LLM_GENERATION_GUIDE.md`). The remaining ~29 are **not** doc bugs: they are
`project-harness/ROADMAP.md` and `project-harness/HANDOFF_TRACK_A.md` items phrased as
future work ("create `tests/unit/evals/test_arm_spec.py`") inside a roadmap/handoff
document, which is the correct place to name a file that doesn't exist yet. Confirms the
task hint — `project-harness/CLAUDE.md` is not the only doc carrying a stale-path
self-correction; `README.md` and `CONTRIBUTING.md` carry several **uncorrected** ones.

### 5. `docs/API.md` vs live API

Live server confirmed reachable: `curl http://127.0.0.1:8000/openapi.json` → HTTP 200,
132 paths. Extracted 120 route mentions from `docs/API.md` (after excluding `/*`-glob
prose fragments like `` `/v1/admin/*` ``, which are section headers, not routes) and
diffed both directions, normalizing `{param}` names.

| Direction | Count | Detail |
|---|---|---|
| Documented but absent from the live route table | 0 real (2 raw hits were false positives: `/v1/graph/nodes/Character` is a doc example instantiating the generic `/v1/graph/nodes/{node_type}` route which *is* live; `/v1/ws/dialogue` is a real WebSocket route confirmed in `src/npc_engine/api/routes/dialogue/dialogue_ws.py` — FastAPI's `/openapi.json` never lists WebSocket routes by design, so this is not a doc bug) | — |
| Live but undocumented in `docs/API.md` | **6** | `/setup/config`, `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate` (all 4 also absent from the committed `live_openapi.json` snapshot — added since 2026-06-24), plus `/v1/admin/factions/{faction_id}/standings/{p}` (a second-param variant of the documented single-param route) and `/v1/admin/schedules/character/{p}/at` (doc only shows the `location/{location_id}/at` sibling) |

`docs/API.md` explicitly disclaims completeness ("the full interactive contract... is
always served live at `/docs`... this document is the curated guide," line 15-16), which
mitigates severity — this is an incomplete curated guide, not a doc asserting a false
closed set.

### 6. `CHANGELOG.md` maintenance

- **Last touched:** 2026-08-14 (commit `5bfa528`). HEAD is `d46ae42`, dated 2026-08-27.
- **96 commits** have landed since, including feature commits that would normally warrant
  an entry: `d7b7c8b feat(evals): the golden-set instrument`, `72594dd feat(evals):
  measure observability before authoring`, `96d83eb fix(config): the shipped window
  derives a budget smaller than the context it assembles`, `4078c37 feat(scripts):
  measure what context assembly COSTS`.
- **No dated/versioned entries exist at all** — the entire file is one `## [Unreleased]`
  section; there are no git tags (`git tag -l` → empty) and no evidence a "release" has
  ever been cut, so the "Keep a Changelog" format claim is structurally true but the
  practice of *releasing* (moving Unreleased to a dated version) has never happened.
- Every path referenced under the current Unreleased section that begins `project/` is
  dangling (see claims table) — the changelog was not updated when `project/` became
  `project-harness/`.

## Findings

### [CR-L13-01] HARNESS_GATES.md's own debt numbers are the wrong sign in both directions

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `project-harness/HARNESS_GATES.md:33` claims "`scripts/rules_baseline.txt`
  ... (57 today)" — actual is 133 (`wc -l` minus 3 header lines; `make check-rules` prints
  "133 grandfathered"). `HARNESS_GATES.md:34` claims "`.mypy_baseline` ... (256 today)" —
  actual is `0` (`cat .mypy_baseline`). The whole doc's stated purpose (line 3-6) is "the
  lint/type/rule/coverage debt... can never silently grow again" — the debt these two
  numbers describe silently changed (rules debt +133%, mypy debt to zero) and the doc,
  whose entire reason to exist is catching exactly that drift, was never updated. Doc has
  not been touched since its creation commit `b390a07` (2026-06-03) — 85 days of drift.
- **Cost of inaction:** Anyone deciding whether to invest more in type-safety cleanup
  reads "256 mypy errors" and either wastes time confirming it's stale or budgets against
  a number that's already zero; anyone auditing rule-violation burn-down sees "57" and
  believes the codebase is closer to clean than it is (133, 2.3x worse).
- **Fix sketch:** Regenerate both numbers from `wc -l scripts/rules_baseline.txt` and
  `cat .mypy_baseline` and either hardcode-and-date them or replace with "see the file" —
  given they visibly drift, prefer removing the specific numbers from prose entirely.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only edit.

### [CR-L13-02] CONTRIBUTING.md's contributor quickstart is broken in two ways a first-time contributor cannot self-diagnose

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `CONTRIBUTING.md:30` tells a new contributor to seed the graph with
  `python -m npc_engine.scripts.seed` — running it gives `No module named
  npc_engine.scripts.seed` (confirmed by execution; no such module exists anywhere in the
  repo). `CONTRIBUTING.md:44,49,56,57,71` tell the contributor to read `project/CLAUDE.md`
  (the "authoritative rules file") and log to `project/ISSUES.md` /
  `project/DECISIONS.md` — the `project/` directory does not exist at all (`ls project/`
  fails); the real, canonical location per the project's own rule
  (`project-harness/CLAUDE.md`'s "Project management files — canonical locations"
  section) is `project-harness/`.
- **Cost of inaction:** A brand-new contributor following this file top-to-bottom hits a
  dead command and five dead links to the rules file they were told is mandatory reading
  before writing any code — the exact failure mode CONTRIBUTING.md exists to prevent.
- **Fix sketch:** Replace `python -m npc_engine.scripts.seed` with the real seeding path
  (`make demo-seed` or the `seeds/worlds/` scripts per `project-harness/CLAUDE.md`);
  global find/replace `project/CLAUDE.md` → `project-harness/CLAUDE.md` (and the two
  other `project/*.md` references) in this file.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only edit; no code path depends on this text.

### [CR-L13-03] Two eval-gate docs advertise `make` targets that were never wired into the Makefile

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `docs/CASE_SET_POLICY.md:94` ("Measured and gated by
  `scripts/check_base_rate.py` (`make check-base-rate`)"), `docs/CAPABILITY_CASES.md:69`,
  and `docs/ENGINE_EVAL_COVERAGE.md:4` ("Gated by `scripts/check_engine_coverage.py`
  (`make check-engine-coverage`)") all present a bracketed `make` invocation as the way to
  run the gate. Both fail identically: `make: *** No rule to make target
  'check-base-rate'.  Stop.` and the same for `check-engine-coverage`. The underlying
  Python scripts do exist and work when invoked directly
  (`python scripts/check_engine_coverage.py` → correct 44-unit table). Contrast:
  `project-harness/HANDOFF_TRACK_A.md:290` names the same `check-base-rate` gap but is
  explicit that it's "not in `make check`, by design, until EVAL-P26.2" — the two docs in
  scope carry no such caveat, so a reader of `docs/` alone has no way to know the
  parenthetical command is aspirational.
- **Cost of inaction:** Whoever tries to actually run either gate as documented — e.g. to
  check a case-authoring PR against the base-rate contract — gets a bare Make error with
  no pointer to the real invocation.
- **Fix sketch:** Add both as real (even if advisory, matching `check_base_rate.py`'s own
  `advisory`-mode docstring) Makefile targets, or drop the `(make ...)` parenthetical from
  all three doc lines and give the `python scripts/...` invocation instead.
- **Effort:** S (<2h)
- **Blast radius:** Makefile edit is additive only if targets are added; zero blast radius
  if the fix is doc-only.

### [CR-L13-04] README.md's "Key files" table points at a source layout that no longer exists

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md:77-85` links `npc_engine/main.py`, `npc_engine/config.py`,
  `npc_engine/engines/dialogue/`, `npc_engine/type_registry/`, `npc_engine/retrieval/`,
  `tests/scenarios/`, and `proposals/` — 7 of 10 rows. All 7 are dead: the source moved
  under `src/npc_engine/` (confirmed live at `src/npc_engine/main.py` etc.), the E2E
  scenario dir is `e2e/scenarios/` (per the `scenarios` Makefile recipe,
  `pytest e2e/scenarios/`), and design proposals live at `project-harness/proposals/`.
  `git log` shows README.md was last touched 2026-08-17 in a commit unrelated to this
  table, and the table's own prior fix commit (`e7c265e`, "SEV-34 fix stale README Quick
  Start") only fixed the Quick Start section below it, not this table.
- **Cost of inaction:** A reader using the README as a map of the codebase (its stated
  purpose) gets 7 broken links out of 10, with no signal that the whole file predates a
  layout migration.
- **Fix sketch:** Prefix the five `npc_engine/...` links with `src/`, change
  `tests/scenarios/` → `e2e/scenarios/`, change `proposals/` → `project-harness/proposals/`.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-05] README.md "What's next" describes finished or archived work as open TODOs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `README.md:38` — "`tone_judge` matcher is a stub; wire in LLM-as-judge" —
  but `evals/matchers.py:272` (`_eval_tone_judge`) is a real, wired YES/NO LLM-judge call
  driven by `prompts/eval/tone_judge.yaml` (a genuine 25-line judge-prompt template used
  by both `evals/matchers.py` and `e2e/helpers/llm_judge.py`). `README.md:34` — "wire in a
  lightweight graph lookup to pick the right archetype YAML" — but
  `dialogue_handler.py:220,384` already does exactly that:
  `archetype = await self._dialogue_repo.get_npc_archetype(request.npc_id) or "default"`.
  `README.md:32-33` present `proposals/prompt_inventory.md` and
  `proposals/delta_log_options.md` as live, pending-approval design docs — both are filed
  under `project-harness/archive/stale-2026-06/`, i.e. the project's own process already
  closed them out.
- **Cost of inaction:** A reader (contributor, evaluator, licensing prospect reading the
  README as a maturity signal) undercounts what's actually built and may re-propose or
  re-implement work that already shipped.
- **Fix sketch:** Delete all four bullet points from "What's next"; regenerate the section
  from the current `project-harness/ROADMAP.md` "Next" line instead of hand-maintaining a
  second, independent TODO list.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-06] `check_harness_honesty.py`'s H3 check references a file that was archived, making it permanently inert

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_harness_honesty.py:23` sets
  `NEXT_SESSION = REPO_ROOT / "project-harness" / "NEXT_SESSION.md"`; `_read()` (line 30)
  returns `""` when the path is missing. `find . -iname NEXT_SESSION.md` shows the only
  copy lives at `project-harness/archive/stale-2026-06/NEXT_SESSION.md`. The H3 regex
  (`_NO_OPEN_ISSUES_RE`, line 26) can only match non-empty text, so it can never fire
  against `""`. Ran both `python scripts/check_harness_honesty.py` and `--strict`; both
  print identical output ("OK - 67 open ticket(s)...") and exit 0 — confirming H3 (and,
  independently, H1 and H2, per §2 above) contribute nothing to either mode today.
- **Cost of inaction:** The `--strict` flag documented as making warnings "fail too"
  (module docstring, line 15) currently cannot demonstrate that behavior on this repo —
  anyone relying on `--strict` in CI to catch a genuine "docs say no open issues" drift
  gets silent pass-through.
- **Fix sketch:** Either restore `project-harness/NEXT_SESSION.md` as a maintained file
  the H3 check can act on, or remove the dead H3 branch and its module-docstring
  reference to it.
- **Effort:** S (<2h)
- **Blast radius:** Touches `make check-harness` / `check-harness` CI job; low risk since
  it's advisory-only today regardless.

### [CR-L13-07] HARNESS_GATES.md's "one command" table is missing 9 of the 14 gates `make check` actually runs

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `HARNESS_GATES.md:11` states `make check` = `lint + check-rules +
  type-ratchet + check-harness + test-cov(80% floor)` — 5 components, and the gates table
  below it (lines 19-26) lists 6 rows total (adding Contracts). The real `check:` recipe
  (`Makefile:200`) has 14 dependencies: `lint check-rules check-evals-rules check-layers
  check-docstrings type type-evals check-harness check-human-gates check-test-quality
  check-conservation check-label-survival test-cov test-cov-evals`. Undocumented in the
  gates table: `check-evals-rules`, `check-layers`, `check-docstrings`, `type-evals`,
  `check-human-gates`, `check-test-quality`, `check-conservation`, `check-label-survival`,
  `test-cov-evals` (75% floor on `evals/`, distinct from the 80% floor on the main suite).
  Also the doc names `type-ratchet` as the type gate, but `check` calls `type` (plain
  `mypy src/`, hard-fail) — `type-ratchet` (`scripts/mypy_ratchet.py`) is a separate target
  `make check` never invokes.
- **Cost of inaction:** A developer reading this table as the authoritative description of
  what `make check` enforces will not know 9 real, currently-passing gates exist, and will
  misdescribe the type gate's actual mechanism (hard-fail vs. ratchet) to anyone who asks.
- **Fix sketch:** Regenerate the table from `grep '^check:' Makefile`'s dependency list;
  either document all 14 or explicitly scope the doc to "the gates added in this PR" with
  a pointer to the Makefile for the current full list.
- **Effort:** S (<2h)
- **Blast radius:** None — doc-only; the underlying `make check` behavior (confirmed GREEN
  via a full run, exit 0, 1007 passed / 1 skipped) is unaffected.

### [CR-L13-08] CHANGELOG.md is 96 commits and 13 days stale, and still points at the pre-rename `project/` tree

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Last touched `5bfa528` (2026-08-14); HEAD `d46ae42` (2026-08-27) is 96
  commits later, including `feat` commits (`d7b7c8b`, `72594dd`, `96d83eb`, `4078c37`)
  that CONTRIBUTING.md's own commit-type taxonomy would expect logged. Every path under
  the live `## [Unreleased]` section prefixed `project/` (`project/STATUS.md`,
  `project/PATTERNS.md`, `project/proposals/*`, plus `docs/LLM_GENERATION_GUIDE.md`) is
  dangling — none of those paths exist post the `project/` → `project-harness/` rename.
  No git tags exist and no dated version section has ever been added, despite the file's
  "Keep a Changelog" header claim.
- **Cost of inaction:** Progressively less useful as a change-history artifact; a reader
  trying to correlate a shipped fix with its changelog entry finds nothing for the last
  13 days of work.
- **Fix sketch:** Fix the dangling `project/*` paths in the existing entries (they're
  historically describing real events, just at the wrong now-renamed path); add entries
  for the 96 missing commits or explicitly deprecate the file with a pointer to
  `git log` / `project-harness/ROADMAP.md` if it's not going to be kept current.
- **Effort:** S (<2h) for the path fixes; M (<1d) to backfill 96 commits' worth of entries.
- **Blast radius:** None.

### [CR-L13-09] `docs/API.md` is missing the 6 newest live routes, including a whole undocumented `/setup/*` surface

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** Live `/openapi.json` (132 paths, fetched from the running server) vs. 120
  normalized route mentions extracted from `docs/API.md`: `/setup/config`,
  `/setup/validate`, `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate`
  (none of which appear in the doc, and none appear in the 2026-06-24 committed
  `live_openapi.json` snapshot either — genuinely new surface), plus two undocumented
  parameter variants of already-documented routes
  (`/v1/admin/factions/{faction_id}/standings/{p}`,
  `/v1/admin/schedules/character/{p}/at`). Severity is capped at MEDIUM because
  `docs/API.md:15-16` explicitly disclaims being the complete contract and points readers
  at the live `/openapi.json` as source of truth — this is an incomplete guide, not a
  false "this is everything" claim.
- **Cost of inaction:** A game-client integrator reading only the curated guide won't know
  the `/setup/*` config-validation endpoints or the vector-store admin/debug routes exist.
- **Fix sketch:** Add a "Setup" and a "Vector store" row/section covering the 4 genuinely
  new routes; add the two missing parameter variants to their existing route rows.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-10] EVAL_STRATEGY.md is a 3-month-old, uncorrected duplicate of docs/EVAL_METHODOLOGY.md

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** `project-harness/EVAL_STRATEGY.md` last touched 2026-05-28 (commit
  `82a22af`), while `docs/EVAL_METHODOLOGY.md`, `docs/CASE_SET_POLICY.md`, and the whole
  EVAL-P## program have been built out and actively edited through 2026-08-27. It still
  references `seeds/world/seed_tavern_world.py` and `seeds/world/run_eval_world.py`
  (actual: `seeds/worlds/`, and `run_eval_world.py` doesn't exist anywhere) and
  `make eval-full` (doesn't exist). No banner marks it superseded or historical, and no
  in-scope doc cross-references it as deprecated.
- **Cost of inaction:** A reader who finds this file before `docs/EVAL_METHODOLOGY.md`
  (alphabetically or via search) gets three broken commands/paths and an eval strategy
  description that predates the current base-rate/case-adversary/golden-set machinery
  entirely.
- **Fix sketch:** Add a one-line "superseded by docs/EVAL_METHODOLOGY.md, kept for
  historical rubric text only" banner at the top, or move it into
  `project-harness/archive/` alongside the other stale-2026-06 files it's contemporary with.
- **Effort:** S (<2h)
- **Blast radius:** None.

### [CR-L13-11] Root `live_openapi.json` snapshot is 64 days stale relative to the running server

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Committed `live_openapi.json` (repo root) is dated 2026-06-24 (file mtime)
  and has 128 paths; the live server's `/openapi.json` has 132 (the same 4 new routes
  identified in CR-L13-09: `/setup/config`, `/setup/validate`,
  `/v1/admin/debug/vector-store`, `/v1/admin/vector-store/rehydrate`). Nothing in the
  in-scope docs treats this file as authoritative (docs/API.md correctly points at the
  live endpoint instead), so this is a stale committed artifact rather than a doc lying to
  a reader — flagged LOW because its only real risk is someone diffing against it by hand
  and drawing a wrong conclusion.
- **Cost of inaction:** Low — an occasional false negative/positive in an ad hoc API diff.
- **Fix sketch:** Either regenerate it as part of a pre-commit/CI step, or delete it if
  nothing consumes it programmatically (check for consumers before removing).
- **Effort:** S (<2h)
- **Blast radius:** Check whether any test or script reads this file before deleting it.
