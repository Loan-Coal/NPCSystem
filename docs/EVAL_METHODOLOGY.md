# Eval Methodology

This document explains every statistical and structural choice made in the NPC Engine
eval harness. Each section names *why the obvious simpler alternative is wrong* and links
to the module that computes the number and the test that pins it so a reader can verify
any figure without running the suite.

> **Constraint (EVAL-P13):** Nothing new is measured here. Every technique described
> corresponds to a module that already ships and a test that already passes.

---

## 1. Wilson score confidence interval (not the normal approximation)

**What it measures:** Uncertainty around a binary pass rate.

**Where it is computed:** `evals/statistics.py` — `wilson_interval(successes, trials)`  
**Pinned by:** `tests/unit/evals/test_statistics.py::test_wilson_3_of_3` and
`test_wilson_table_driven`

**Why not the normal approximation?**

The standard normal-approximation interval is:

```
p̂ ± z * sqrt(p̂(1 - p̂) / n)
```

At small n this breaks in two ways:

1. The lower bound goes negative and the upper bound exceeds 1. For p̂ = 0 and n = 3 the
   normal approximation gives [0.0, 0.0] — a degenerate zero-width interval that claims
   certainty where there is none.
2. The approximation assumes the binomial is well-approximated by a Gaussian, which
   requires both `n·p̂ ≥ 5` and `n·(1-p̂) ≥ 5`. Neither holds for a suite with n < 20.

The Wilson score interval uses a different pivot:

```
center = (p̂ + z²/(2n)) / (1 + z²/n)
margin = z * sqrt(p̂(1-p̂)/n + z²/(4n²)) / (1 + z²/n)
```

This always stays in [0, 1], has better coverage at both tails, and matches hand-worked
arithmetic to three decimal places for the test fixtures (see the worked table in
`test_statistics.py`).

**Concrete check:** For 3/3 passes the Wilson interval is [0.438, 1.000] — *not* [1.0,
1.0]. That 44 % lower bound is the honest price of having only three data points.
Every headline rate in the dashboard and report carries this interval.

---

## 2. Exact McNemar test (not the chi-squared approximation)

**What it measures:** Whether a code change shifted the pass/fail outcomes of the same
cases — a paired comparison across two eval runs.

**Where it is computed:** `evals/paired_stats.py` — `mcnemar_exact(b, c)` and
`paired_compare(before, after)`  
**Pinned by:** `tests/unit/evals/test_paired_stats.py::test_mcnemar_exact_matches_worked_example`

**Why not chi-squared?**

McNemar's chi-squared approximation is:

```
χ² = (|b - c| - 1)² / (b + c)
```

The rule of thumb is that this is only reliable when the number of *discordant* pairs
(b + c) exceeds 25. At 53 total cases, discordant pairs are typically far fewer — a run
where most cases stay stable might have b + c < 10. Using the chi-squared approximation
in that region inflates Type I error (false "significant" verdicts).

The exact approach evaluates the full binomial:

```python
p = 2 * sum(C(n, k) for k in range(min(b, c) + 1)) / 2^n   where n = b + c
```

This is always exact, has no minimum-n requirement, and collapses to the chi-squared
result at large n anyway. The test pins the p-value to three decimal places against a
hand-worked binomial table.

**Canonical case count note:** The suite uses `evaluated_cases` (cases that actually ran)
as n for McNemar, not `total_cases` (see §4 below). The two values diverge whenever
precondition guards skip a case.

---

## 3. Cohen's κ with bootstrap CI (not bare κ)

**What it measures:** Inter-rater reliability between the automated scorer and a human
adjudicator. Gates what claims a calibration score licenses (see §5).

**Where it is computed:** `evals/calibration.py` — `cohens_kappa(rows)` and
`kappa_interval(rows, resamples, seed)`  
**Pinned by:** `tests/unit/evals/test_calibration.py`

**Why not just report κ?**

A bare κ is a point estimate with no uncertainty. With calibration samples of 30–60
adjudicated rows, the asymptotic standard error formula for κ makes strong distributional
assumptions that are not met at these sizes. Two scorers at κ = 0.61 and κ = 0.63 are
not meaningfully different if their bootstrap intervals overlap substantially.

The bootstrap approach (2000 resamples, `BOOTSTRAP_SEED = 42`, percentile method at 2.5 %
and 97.5 %) avoids distributional assumptions entirely. The seed makes the interval
reproducible: the same labels file always produces the same bounds. This matters because
the trust policy (§5) consults the interval, not just the point estimate.

**Two axes, one calibration run:**

The calibration module reports two confusion matrices per scorer:

- **Headline:** `scorer_verdict` vs `human_verdict` — can you trust the automated scorer?
- **Secondary:** `pre_label` vs `human_verdict` — how much does the reference pre-labeller
  agree with the maintainer?

Both carry κ and a bootstrap CI (`kappa_interval` and `pre_label_kappa_interval`). The
FP cell (scorer says pass, human says fail) is the dangerous cell and is highlighted
explicitly in every printed report.

---

## 4. `evaluated_cases` as the denominator (not `total_cases`)

**What it measures:** Which cases actually ran and whose outcomes count toward the rate.

**Where it is computed:** `evals/summary.py` — `EvalSummary.evaluated_cases`  
(line: `evaluated_cases = total_cases - skipped_cases`)  
**Pinned by:** `tests/unit/evals/test_case_stats.py`

**Why not `total_cases`?**

A case is skipped when its precondition fails — for example, a guard case that requires
a knowledge-graph node that was not seeded in this run. Counting skipped cases in the
denominator would silently dilute the pass rate: a run where 10 of 53 cases were skipped
would report 43/53 = 81 % even if every evaluated case passed (43/43 = 100 %).

`evaluated_cases` is the denominator for every headline rate (guard rate, capability
rate, over-refusal rate). `total_cases` is reported alongside it so the reader can see
how many cases were skipped, but it never enters a rate calculation.

The `summary.py` output line reads:

```
All cases: {evaluated_cases} evaluated / {total_cases} total ({skipped_cases} skipped)
```

This forces the skipped count to be visible rather than hidden in a denominator.

---

## 5. Capability rate paired with guard rate (not guard rate alone)

**What it measures:** Together: whether the NPC resists hallucination *and* can still
answer legitimate questions. Separately: neither is meaningful.

**Where it is computed:** `evals/summary.py` (`EvalSummary.guard_rate`,
`EvalSummary.capability_rate`) and `evals/scorer_trust_policy.py` (`check_publication`)  
**Pinned by:** `tests/unit/evals/test_trust_policy.py`,
`tests/unit/evals/test_capability_coverage.py`

**Why not guard rate alone?**

A guard rate of 100 % is trivially achieved by an NPC that refuses every question. The
capability battery (`case_pos_*` cases) makes that evasion visible: an NPC that refuses
grounded questions also fails the capability rate.

The two batteries are defined by case ID prefix:

- **Guard battery:** `case_adv_*` (adversarial injections) + `case_neg_*` (negative
  knowledge guards). An NPC passes when it does *not* affirm a false claim or produce
  out-of-character text.
- **Capability battery:** `case_pos_*` (positive knowledge checks). An NPC passes when
  it *does* demonstrate grounded factual recall.

The `summary.py` `format_summary_lines` function refuses to render the guard rate without
the capability rate in the same block (see `_UNPAIRED_GUARD_ONLY` / `_UNPAIRED_CAPABILITY_ONLY`
constants). This is a structural constraint, not a convention.

**Trust policy gate:** `scorer_trust_policy.py` enforces a three-tier publication policy
based on κ:

| κ range | Trust level | What is permitted |
|---------|-------------|-------------------|
| < 0.40 | `HIDDEN` | Scorer is suppressed entirely |
| 0.40 – 0.60 | `RESTRICTED` | Shown in detail view, not in headline |
| ≥ 0.60 | `PUBLISHABLE` | Headline and README |

`check_publication(scorer, kappa, interval)` returns a `PolicyRefusal` when the scorer
cannot be published, and the report substitutes the EVAL-P11.1 refusal message in place
of the rate. A calibrated scorer that later loses adjudicated rows can be demoted — the
policy is re-evaluated on every report generation, not cached.

---

## Anti-metric section — what this suite cannot see

The following limitations are structural. They are stated here so that a reader
interpreting any published rate knows the boundary of the guarantee.

### Pronouns

The entity scorer (`evals/entity_scorer.py`) uses whole-word alias-table matching.
Pronoun references ("he", "she", "they") are invisible to it: a hallucinated entity
referred to only by pronoun will not raise the unsupported-entity rate.

### Unnamed fabrications

Phrases like "a merchant from the eastern docks" or "an old alchemist" do not match any
alias-table entry and pass entity scoring undetected. The entity scorer explicitly
documents this: `entity_scorer.py` module docstring line "Unnamed fabrications
('a merchant from the eastern docks') are undetectable."

### Single-turn only

Every eval case measures one NPC response in isolation. The suite has no multi-turn
scenario that tests whether an NPC maintains consistency across a conversation — for
example, remembering a denial it gave three turns earlier. Dialogue coherence across
turns is not measured.

### One judge

The LLM judge is a single model (`judge_config.py`, default `mixtral:8x7b`). All
`tone_judge` and `affirms_judge` verdicts come from this one model. Its systematic
biases (over-strictness, over-permissiveness for certain phrasing patterns) affect every
judged case in the same direction. A second judge with different architecture was
considered (DEC-143) but not implemented. The calibration results (§3) measure how much
the single judge agrees with a human, but they cannot detect the judge's blind spots —
only a second independent judge could do that.

---

## Verification index

Every number in any published report or README must trace to one of these:

| Claim | Module | Test |
|-------|--------|------|
| Guard rate + CI | `evals/summary.py:EvalSummary` | `test_case_stats.py` |
| Capability rate + CI | `evals/summary.py:EvalSummary` | `test_case_stats.py` |
| Wilson CI bounds | `evals/statistics.py:wilson_interval` | `test_statistics.py::test_wilson_table_driven` |
| McNemar p-value | `evals/paired_stats.py:mcnemar_exact` | `test_paired_stats.py::test_mcnemar_exact_matches_worked_example` |
| Scorer κ + CI | `evals/calibration.py:kappa_interval` | `test_calibration.py` |
| Trust tier | `evals/scorer_trust_policy.py:check_publication` | `test_trust_policy.py` |
| Over-refusal rate | `evals/refusal_rate.py:score_refusal_rate` | `test_refusal_rate.py` |
| evaluated_cases count | `evals/summary.py:EvalSummary.evaluated_cases` | `test_case_stats.py` |
| Sequence k-repeat stats | `evals/sequence_runner.py:run_scenario_k_times` | `test_sequence_runner.py` |
