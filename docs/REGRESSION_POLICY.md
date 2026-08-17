# Regression Policy

**Version:** 1.0
**Status:** Active
**Applies to:** Trend comparisons via `evals/regression_gate.py` (EVAL-P23.2), consumed
by `scripts/Run-EvalHarness.ps1` (EVAL-P23.3)

---

## Purpose

`compare` (EVAL-P8.2) answers "did A vs B change" for one pair of runs. Nothing in the
harness answers "is the engine improving over six weeks" — that needs an accumulating
history (`evals/trend_store.py`, EVAL-P23.1) and a rule for what counts as a drop worth
stopping for. This document states that rule before any specific run trips it, and the
rule is also encoded as a function (`evals/regression_gate.py:check_regression`) so no
harness run can apply a looser standard by accident.

---

## The rule

A candidate run is flagged as a regression when **any** of the following hold, compared
against the most recently recorded trend row (`trend_store.latest_row()`):

1. **A published rate's entire CI falls below the baseline's point estimate** — checked
   as `candidate.ci_high < baseline.rate` (guard rate, capability rate — checked
   independently).
2. **A paired case-level McNemar comparison verdicts `worse`** (`paired_stats.py`).
3. **The inconclusive rate exceeds `DEFAULT_MAX_INCONCLUSIVE_RATE` (0.20)** — the same
   threshold `summary.py` uses to mark a run's own guarantee undemonstrated.

Any one finding is enough to flag `regressed=True`. Findings are cumulative and all
reported together, not short-circuited at the first hit — a run with three problems
should say so, not only the first one alphabetically.

---

## Why the CI upper bound, not the point estimate

**Use the interval, not the point estimate.** A point-estimate comparison at k=3
repetitions fires on sampling noise: two runs of a genuinely unchanged engine can easily
differ by a few points on 94 guard turns without anything real having happened. Comparing
`candidate.rate < baseline.rate` directly would make every third run "regress" for no
reason.

Requiring the candidate's CI **upper bound** to fall below the baseline's **point
estimate** is a one-sided, asymmetric test on purpose: it tolerates a candidate rate that
is nominally lower than the baseline as long as the uncertainty in that measurement still
plausibly reaches back up to the baseline's value. It only fires when the candidate's own
confidence interval has moved entirely below where the baseline sat. This is the same
reasoning `paired_stats.is_boundary_ci` and the McNemar test already apply elsewhere in
this harness — a number without its interval is not evidence of change.

**Overlapping intervals never fire**, by construction. This is worth stating plainly
because it is the property most likely to be "fixed" by someone who has not read this
document: a candidate whose rate is nominally lower than the baseline's, but whose
interval overlaps it, is not a regression under this policy — it is noise.

**A tempting-looking wrong implementation, caught by testing against a real artifact:**
comparing `candidate.ci_low < baseline.rate` instead of `candidate.ci_high` reads almost
the same but is a different, broken test — a confidence interval's lower bound is *always*
below its own point estimate, so that comparison fires on nearly every pair of runs,
including a run compared **against itself**. This was caught empirically, not by reasoning
about it in advance: a unit test that recorded `k3_73e6c36`'s own numbers as both baseline
and candidate reported a false regression under the `ci_low` version. If a future change
to `regression_gate.py` ever reintroduces `ci_low` here, that same self-comparison test
(`test_main_gates_against_a_recorded_baseline`,
`tests/unit/scripts/test_record_trend_and_gate.py`) will catch it again.

---

## How the policy is enforced

```python
from regression_gate import check_regression, format_regression_report
from trend_store import latest_row

baseline = latest_row()
report = check_regression(candidate_row, baseline, paired=paired_result)
print(format_regression_report(report))
if report.regressed:
    sys.exit(1)
```

`check_regression` returns a `RegressionReport` with `regressed: bool` and a tuple of
`RegressionFinding` — each finding names the metric, both intervals (or values), and `n`,
so a CI/log consumer never has to re-derive what fired from a bare boolean.

`scripts/Run-EvalHarness.ps1` (EVAL-P23.3) calls this after recording the candidate's
trend row and exits non-zero when `regressed` is `True` — that exit code is the whole
point of building a regression gate rather than a report a human has to remember to read.

---

## What this policy does NOT do

- It does not compare against every prior run, only the most recently recorded one.
  Comparing against an arbitrary earlier baseline is a `compare` (EVAL-P8.2) call, not
  this gate's job.
- It does not gate on a scorer's calibration κ directly — that is
  `docs/SCORER_TRUST_POLICY.md`'s job (`scorer_trust_policy.check_publication`), a
  separate, publication-time check.
- It does not fire when a rate is simply unmeasured on either side (`rate=None`). An
  unmeasured rate is a validity problem the harness's own preflight should catch, not a
  regression this gate should paper over with a fabricated verdict.
- It does not change what counts as "the baseline" — `latest_row()` always means "most
  recently appended", never "best" or "highest-numbered". Trend rows are never reordered.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-08-17 | Initial policy, EVAL-P23.2 (EVAL-P20→P24 unblock plan, Phase A7) |
