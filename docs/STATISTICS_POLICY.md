# Statistics Policy

This document states which statistical intervals are quoted in each context and
which inferences are not supported by the current eval harness.

---

## 1. Interval types produced by the calibration harness

Each calibration run over S scorers produces **2 × S simultaneous bootstrap intervals**
(one headline-axis κ CI and one secondary-axis κ CI per scorer).

| Interval | α level | When to quote |
|---|---|---|
| Nominal 95% CI | α = 0.05 per interval | Single-scorer reports; exploratory comparison |
| Holm-Bonferroni companion | α* = 0.05 / family_size | Any claim covering multiple scorers simultaneously |

**Family-wise error rate (FWER) at α = 0.05:**

| Scorers | Intervals | FWER |
|---|---|---|
| 1 | 2 | 0.098 |
| 2 | 4 | 0.185 |
| 4 | 8 | 0.337 |

At 4 scorers there is a **33.7% probability** that at least one nominal 95% CI misses the
true κ value. The Holm companion CI controls this to ≤ 5%.

### What to quote where

- **Single-scorer summaries** (e.g. "tone_judge κ = 0.72 [0.61, 0.83]"): quote the
  nominal 95% CI. The family is size 2 at this scope; FWER ≤ 0.098.

- **Cross-scorer claims** (e.g. "all four scorers achieve κ > 0.6"): quote the
  Holm-adjusted companion CI. The companion is printed on the `Holm-adj` line in
  the calibration report immediately below each scorer's nominal CI.

- **Dashboard and executive summaries** covering all scorers: always state the
  family size and FWER alongside any interval quoted.

---

## 2. Inferences not supported by the harness

### 2a. Per-case cherry-picking from `compare`'s delta table

`evals/compare.py` produces a 115-row delta table (one row per expectation slot).
**Per-case cherry-picking from this table is not a supported inference.**

Reasons:

- The 115 rows are not independent observations. Each case contributes 1–3 rows
  (one per expectation slot), and the case-level McNemar test — not the slot-level
  table — is the correct unit of analysis (EVAL-P16.4).

- Selecting "interesting" rows post-hoc from a 115-row table without correcting for
  the implicit 115-comparison family inflates the effective α by a factor of up to 115.

- A change that moves 3 slots belonging to 2 correlated cases yields p = 0.031 at
  the slot level but p = 0.5 at the case level (the EVAL-P16.4 worked example). The
  slot-level p is not an honest measure of evidence.

**Supported inferences from `compare`:**

- The overall McNemar test on case-level discordant pairs (printed as `p_mcnemar`).
- The direction and magnitude of the change in case-level pass rate.
- Slot-level rows as *examples* to understand *which* expectations changed, not as
  independent evidence that the change is real.

### 2b. Pooled κ across scorers

Computing a single aggregate κ from all scorers' rows pools correlated observations
across heterogeneous decision axes. This was the original bug corrected by EVAL-P16.
The calibration harness deliberately prints **one matrix per scorer**. A pooled number
is not printed and must not be computed manually from the per-scorer matrices.

### 2c. Row-level bootstrap for κ

The bootstrap in `evals/calibration.py` resamples **case clusters**, not individual rows,
because each case contributes k ≈ 3 correlated rows. A row-level bootstrap underestimates
the CI width by a factor of √k at rho ≈ 1 (EVAL-P16.2). Row-level bootstrap CI widths
must not be used or cited; they will always be narrower than the honest cluster-bootstrap bounds.

---

## 3. Summary table

| Inference | Supported? | Correct approach |
|---|---|---|
| Per-scorer κ with nominal 95% CI | Yes — single-scorer scope | Printed in calibration report |
| Cross-scorer claim (all scorers) | Yes — with Holm companion | Use `Holm-adj` line from report |
| Cherry-pick from 115-row delta table | **No** | Use case-level McNemar p-value |
| Pooled κ across all scorers | **No** | Report per-scorer only |
| Row-level bootstrap CI for κ | **No** | Use cluster-bootstrap (default) |
