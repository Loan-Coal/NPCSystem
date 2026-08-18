# Session prompt — fix the four defects blocking EVAL-P23

**Written:** 2026-08-18. **Paste the section below into a fresh session.** It is self-contained:
every decision is already made, every defect located. Do not re-litigate the design choices —
they were taken by the maintainer via an explicit decision round on 2026-08-18.

**Deliberately NOT a roadmap phase** (human decision, same round): these are defect repairs to
already-built code, not new program scope. The roadmap phase that *sequences* EVAL-P23's
unblocking is `Phase EVAL-P22B`, which depends on this work but does not contain it.

---

## PROMPT — copy from here

You are working on NPC Engine (`c:\Users\lohan\Documents\hackathons\NPCSystem`). Read
`project-harness/CLAUDE.md` first; its rules are binding (TDD, 300-line non-test file cap,
module/function/class docstrings, `ISSUES.md` / `DECISIONS.md` discipline, no magic strings,
Pydantic v2 for anything crossing a module boundary).

### Goal

Fix four defects that block `EVAL-P23` (the regression harness) from being usable as an
**engine A/B pipeline**. All of `EVAL-P23`'s components already exist and are tested —
`evals/trend_store.py`, `evals/regression_gate.py`, `scripts/Run-EvalHarness.ps1`,
`scripts/record_trend_and_gate.py`. They are blocked by defects, not by missing work.

The end goal this serves: change engine / agent / context-management code → run one command →
get a trustworthy, gated verdict plus a trend row. A/B-testing *the judges* is explicitly **not**
the priority; judge metrics matter only insofar as they bound what an engine comparison can resolve.

### Essential background (why these defects exist)

A 3-model judge panel (`mixtral:8x7b`, `qwen2.5:14b`, `llama3.1:8b`) ran overnight on 2026-08-17
against `evals/generations/k3_73e6c36`. It completed successfully but its persistence layer had
diverged from the single-judge writer. That was repaired on 2026-08-18 (DEC-187/188/189/190,
commits `d257ce5`, `becc756`) — read those DECISIONS entries before starting; they explain the
shape of the codebase you are touching:

- **DEC-187** — `evals/judged_persistence.py` is now the single owner of the `judged.jsonl` row
  schema. Panel mode writes `judged.jsonl` (consensus, one row per record) **plus**
  `judged_panel_votes.jsonl` (one row per seat per record).
- **DEC-188** — Fleiss kappa (chance-corrected) is the headline agreement metric, not raw
  agreement. On the real corpus: kappa **0.526** (95% CI [0.227, 0.730]) where raw agreement
  reads 0.956, because the pass base rate is 0.951. Per criterion: `tone_judge` 1.000,
  `affirms_judge` 0.282, `refusal_judge` 0.225. `evals/panel_metrics.py` computes all of this,
  plus a repeat-flip decomposition separating engine variability from judge instability.
- **DEC-189** — every judge pass writes `run_status.json` (`ok` / `gate_failed` / `error`).
  Its stated purpose includes being "the per-run record for tracking metrics across A/B runs".
- **DEC-190** — `compare.py` resolves the judge identity that *actually* ran (via
  `evals/judge_identity.py` reading `run_status.json`) and refuses to compare arms scored by
  different judge passes.

Two open issues give context, do not fix them here: **ISSUE-186** (`k3_73e6c36` has
`harness_version: None` and `seed: None`, so `compare.py` refuses it against any modern run — it
is a labelled calibration corpus, never an A/B baseline) and **ISSUE-184** (`refusal_judge` /
`affirms_judge` kappa are too low to resolve small engine effects).

### The four defects, with decisions already made

#### Defect A — the harness's two steps use different baselines
`scripts/Run-EvalHarness.ps1:163` hardcodes `& make eval-compare "BEFORE=k3_73e6c36" "AFTER=$GenId"`,
while step 8 (`scripts/record_trend_and_gate.py`) gates against `trend_store.latest_row()`. So the
informational per-case delta table and the authoritative verdict describe **different comparisons**.
`k3_73e6c36` additionally can never compare (ISSUE-186), so step 7 is permanently inert.

> **DECIDED: one baseline, resolved once, used by both steps.** Add a `-Baseline` parameter to
> `Run-EvalHarness.ps1` defaulting to whatever the gate would pick (see Defect B). Steps 7 and 8
> must report on the same pair. On an empty trend store there is no baseline and the compare step
> is skipped with an explicit message — not silently.

#### Defect B — the authoritative gate has no comparability check
`evals/trend_store.py:153` `latest_row()` returns the most recent row regardless of
`harness_version`; `evals/regression_gate.py` `check_regression` never reads it. `harness_version`
hashes `evals/cases/`, `prompts/eval/` and `matchers.py` — so editing a case or a judge criterion
changes it. `compare.py` correctly refuses in that situation; the trend gate silently returns a
confident verdict, and `Run-EvalHarness.ps1` declares the trend gate *authoritative over* compare.

> **DECIDED: walk back to the latest comparable row.** Add
> `trend_store.latest_comparable_row(harness_version)` which scans back for the most recent row
> with a matching `harness_version`, and refuses only when none exists. **Mandatory, not optional:**
> the gate's output must name the chosen baseline's `gen_id` and how old it is, so comparing against
> a much older run is visible rather than silent. Keep `latest_row()` (other callers/tests use it).

#### Defect C — a docstring states the inverted rule
`evals/regression_gate.py:153` — `check_regression`'s docstring says *"only a CI **lower** bound
strictly below the baseline's point estimate counts"*. The code is correct (`_rate_regressed` at
line 67 uses `ci_high`, and its own docstring explains why at length), and DEC-185 records that the
lower-bound version fires on a run compared against itself. This file's stated purpose is to
document the wrong version so it cannot be quietly reintroduced — a docstring asserting the wrong
version is therefore an active trap.

> **DECIDED: correct the docstring to match the code and DEC-185.** No behaviour change.

#### Defect D — TrendRow records the base-rate-inflated metric, not the honest one
`evals/trend_store.py:117` has `panel_agreement_rate` (raw pairwise) but no kappa. A trend built on
raw agreement tracks a number inflated by the pass base rate — exactly the metric DEC-188 demoted.

> **DECIDED: record kappa overall, per criterion, and the repeat-flip counts.** All are already
> computed by `evals/panel_metrics.py`; this is a persistence change, not new statistics. Keep
> `panel_agreement_rate` (do not break existing rows). `TrendRow` already has `extra="allow"` plus
> per-field defaults, so it tolerates the schema change in both directions.
>
> **Plumbing note (implementer's judgement, but this is the recommended route):** extend
> `evals/run_status.py`'s `RunStatus` with the per-criterion kappa map and flip counts, so
> `record_trend_and_gate.build_trend_row` reads them from `run_status.json` rather than rebuilding
> `PanelScoredRecord`s from the transcript + votes file. DEC-189 already frames `run_status.json`
> as the per-run metrics record, and `judge_runner` already has the `PanelMetrics` object in hand
> when it writes that file. The alternative — recomputing in `record_trend_and_gate` by joining
> `outputs.jsonl` with `judged_panel_votes.jsonl`, as `scripts/migrate_panel_judged.py` does — works
> but duplicates a join that already happened.

#### Defect E — a kappa drop must be distinguishable from an engine regression
> **DECIDED: a third verdict.** `scripts/record_trend_and_gate.py` currently returns 0 (pass),
> 1 (regression), 2 (setup error). Add **3 = instrument degraded**: the judge agreement fell, so the
> run's rate comparison is not trustworthy and the engine is not necessarily at fault. Use the same
> CI-aware, one-sided rule as the rate check (`candidate.ci_high < baseline.rate`) so overlapping
> intervals never fire. `Run-EvalHarness.ps1` must report all four states distinctly.
>
> Rationale: separating "my engine got worse" from "my ruler got worse" is the whole point — with
> `refusal_judge` at kappa 0.225 this will fire in practice, and conflating it with an engine
> regression would send you debugging the wrong system.

### How to work

Follow the project's TDD discipline strictly — for each defect write the failing test first and
confirm it fails **for the right reason** before implementing. Suggested RED anchors:

- `test_gate_refuses_when_no_comparable_baseline_exists`
- `test_gate_walks_back_past_an_incomparable_row`
- `test_gate_output_names_the_chosen_baseline_and_its_age`
- `test_trend_row_records_kappa_and_per_criterion_breakdown`
- `test_kappa_drop_is_a_distinct_verdict_from_a_rate_regression`
- `test_overlapping_kappa_intervals_do_not_trigger_instrument_degraded`

`Run-EvalHarness.ps1` has an existing test file (`tests/unit/scripts/test_run_eval_harness.py`)
whose `-DryRun` and precondition paths are verified against real ambient state — extend it rather
than starting a new one, and keep that live-verification property.

### Constraints

- **Do not** run `scripts/Run-EvalHarness.ps1` for real, generate any `evals/generations/*`
  artifact, or write to `evals/calibration/labels_v1.jsonl`. Those paths are frozen for unattended
  work (`scripts/loop_gates.py FROZEN_PATH_PREFIXES`) and the real run is a separate human session.
- **Do not** modify `evals/generations/k3_73e6c36/` — it is the labelled calibration corpus.
- **Do not** re-open the four decisions above.
- No CI changes (standing human decision for this program).

### Definition of done

- All new tests pass; full `python -m pytest tests/unit -q` still green (baseline: 3504 passed,
  1 skipped as of commit `becc756`).
- `python scripts/docstring_audit.py`, `python scripts/check_layers.py`,
  `python scripts/check_rules.py`, `python -m ruff check evals/ scripts/` all clean.
- No non-test file over 300 lines (`evals/compare.py` is already over and grandfathered — do not
  make it worse; put new logic in a new module as `judge_identity.py` did).
- `ISSUES.md` entries for anything found and not fixed; `DECISIONS.md` entry recording the five
  decisions above as implemented (they were taken by the maintainer, not by you — record them as
  such).
- Report honestly which of the five are done and which are not. Do not claim a green run you did
  not observe.

## PROMPT — copy to here
