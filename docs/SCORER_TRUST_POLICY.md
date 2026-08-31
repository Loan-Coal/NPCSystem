# Scorer Trust Policy

**Version:** 1.0  
**Status:** Active  
**Applies to:** All eval scorers measured via `make eval-calibrate` (EVAL-P5)

---

## Purpose

A calibration kappa number means nothing if a report can quote it without restriction.
This document states — **before looking at any specific number** — what kappa licenses
what claim. The policy is also encoded as a function (`evals/scorer_trust_policy.py:check_publication`)
so no report path can bypass it programmatically.

---

## Thresholds

| κ range | Trust level | Allowed actions |
|---------|-------------|-----------------|
| κ ≥ 0.60 | **PUBLISHABLE** | Rate may be quoted in any report or public artefact |
| 0.40 ≤ κ < 0.60 | **RESTRICTED** | Rate may appear in internal reports with a caveat; must not be published or promoted as a headline metric |
| κ < 0.40 | **HIDDEN** | Rate must not appear in any report, internal or external; scorer must be remediated or retired |

Thresholds are strict on the low side: a scorer at exactly 0.40 is RESTRICTED, not HIDDEN.
A scorer at exactly 0.60 is PUBLISHABLE.

---

## Rationale

The thresholds map to established psychometric convention (Landis & Koch 1977) and the
specific risk profile of this eval harness:

- **0.60** is the lower bound of "substantial agreement" — below it, the scorer and
  human raters disagree often enough that a published rate could mislead.
- **0.40** is the lower bound of "moderate agreement" — below it, the scorer is
  essentially unreliable and showing any number would be actively misleading.

---

## How the policy is enforced

`evals/scorer_trust_policy.py` exposes a single function:

```python
from scorer_trust_policy import check_publication

refusal = check_publication(
    scorer="tone_judge",
    kappa=0.55,
    interval=(0.38, 0.70),
)
if refusal is not None:
    # refusal.scorer, refusal.kappa, refusal.interval, refusal.trust_level are all set
    raise RuntimeError(f"Cannot publish: {refusal}")
```

`check_publication` returns `None` when the scorer is publishable, and a `PolicyRefusal`
dataclass otherwise. The refusal names the scorer, its kappa, and its confidence interval
so that error messages and logs are self-contained.

Report generators **must** call `check_publication` before including a scorer's rate in
any output. Bypassing it (e.g. reading `kappa` directly and formatting it yourself) is a
policy violation — `scripts/scan_fix_diff.py` will flag it on review.

---

## What this policy does NOT do

- It does not say a RESTRICTED scorer is worthless — calibration drove a remediation
  loop, and RESTRICTED scorers are candidates for prompt revision (EVAL-P11.2).
- It does not impose a minimum sample size. Sample-size adequacy is a separate concern
  tracked in `docs/EVAL_METHODOLOGY.md`.
- It does not set the kappa CI width requirement. That is in `evals/calibration.py`
  (`BOOTSTRAP_RESAMPLES = 2000`).

---

## Revision history

| Date | Change |
|------|--------|
| 2026-08-09 | Initial policy, EVAL-P11.1 |
