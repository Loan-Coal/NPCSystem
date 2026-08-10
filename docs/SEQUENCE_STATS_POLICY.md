# Sequence Statistics Policy

**Phase:** EVAL-P14.2  
**Status:** Design complete — implementation is a separate programme.  
**Applies to:** All statistics computed from `SequenceRun` transcripts (v2 schema,
`evals/sequence_records.py`).  
**Locked at:** the commit that introduced this file.

---

## Purpose

This policy states which statistics are valid under which reset fidelity, as recorded
in each `Repetition.reset_receipt`. The goal is **automatic downgrade**: an incomplete
reset narrows the permitted output automatically, without requiring a human to remember
which checks apply on each run.

Every metric the sequence dashboard renders must appear in the table in §3 with an
explicit fidelity requirement. A metric not listed there may not be rendered. A metric
whose fidelity requirement is not met must be suppressed — not shown with a caveat,
not approximated, not reported with a warning footnote. Suppressed means absent.

---

## 1. How reset fidelity is determined

Fidelity is read from `Repetition.reset_receipt` at runtime. The two fields that matter:

| Field | Meaning |
|---|---|
| `reset_receipt.cleared` | State components the reset fully removed. |
| `reset_receipt.surviving` | State items that survived the reset and may correlate this repetition with prior ones. |

**FULL fidelity:** `reset_receipt.surviving == ()` for every repetition in the run.
All state was cleared; repetitions are statistically independent.

**PARTIAL fidelity:** `reset_receipt.surviving != ()` for at least one repetition.
Some state survived; repetitions may be correlated. The magnitude of correlation is
unknown — it depends on which state items survived and whether they affect the outcome
being measured.

The fidelity of a `SequenceRun` is the minimum fidelity across all its `Repetition`
records. One partial-reset repetition in a k=10 run demotes the entire run to PARTIAL.

---

## 2. Fidelity tiers

| Tier | Condition | Assumption |
|---|---|---|
| **FULL** | All `reset_receipt.surviving == ()` | Repetitions are i.i.d. under the world state distribution; binomial statistics apply. |
| **PARTIAL** | Any `reset_receipt.surviving != ()` | Repetitions are correlated to an unknown degree; only order-preserving and order-testing statistics are valid. |

There is no third tier. A run is either FULL or PARTIAL — no intermediate "mostly full"
category. The policy is conservative: if any repetition's independence is uncertain, all
binomial and paired-comparison statistics are withdrawn for the whole run.

---

## 3. Permitted statistics by fidelity tier

The sequence dashboard renders the metrics listed below. A ✓ means the metric is
rendered at this fidelity; an ✗ means it is suppressed.

| Metric | FULL | PARTIAL | Rationale |
|---|---|---|---|
| **Raw sequence report** — per-turn outcomes, responses, and retrieved context in execution order | ✓ | ✓ | No statistical assumptions; purely observational. |
| **Per-turn duration stats** — mean and percentiles of `turn.duration_ms` | ✓ | ✓ | Timing is independent of outcome correlation. |
| **Per-repetition outcome** — did the repetition pass the scenario's success predicate | ✓ | ✓ | Raw boolean; the statistic itself makes no independence claim. |
| **Order-effect check** — Cochran's Q across repetition indices; first-vs-last McNemar | ✓ (diagnostic) | ✓ (primary) | Explicitly tests the order structure; valid regardless of fidelity tier. See §4. |
| **Per-scenario pass rate** (raw fraction, no CI) | ✓ | ✓ | A ratio is always reportable; the CI is what requires independence. |
| **Wilson CI on per-scenario pass rate** | ✓ | ✗ | Wilson CI assumes i.i.d. Bernoulli trials. Correlated observations inflate the effective sample size and produce intervals that are too narrow. |
| **Run-to-run McNemar** — paired comparison of the same scenario across two SequenceRuns | ✓ | ✗ | McNemar requires that the two runs being compared are both drawn from independent repetitions. A PARTIAL run is not. |
| **Trend-across-runs regression alert** | ✓ | ✗ | Trend analysis fits a model across k values from multiple runs; each run must be a valid point estimate. PARTIAL runs do not produce valid point estimates. |
| **k adjacent to every rate** (the count of repetitions that produced the rate) | ✓ | ✓ | Purely descriptive; k is always shown to make the raw evidence visible. |

**Enforcement contract for implementors:** The runner computes fidelity from receipts
before calling any statistics function. If fidelity is PARTIAL, the runner passes only
the PARTIAL-permitted metrics to the report formatter. The formatter has no visibility
into the receipts — it renders whatever the runner passes. This is the automatic downgrade
mechanism: restricting the metric set at the runner level, not by adding conditional
formatting in the report.

---

## 4. The order-effect check

The order-effect check is the empirical test of the independence assumption. It asks:
does repetition position predict outcome?

### 4.1 Why this check is needed at both fidelity tiers

At **FULL** fidelity: a significant order effect is a warning that the reset did not
fully clear the relevant state, even if `surviving == ()`. The receipt captures what the
reset *claimed* to clear; the order-effect check tests whether the claim holds in the
observed outcomes. A FULL run with a significant order effect should be flagged for
manual inspection, not promoted to the same status as a clean FULL run.

At **PARTIAL** fidelity: a significant order effect *characterizes* the surviving state's
influence. The magnitude of the effect (how much rep[k-1] differs from rep[0]) is the
primary analytical output available when Wilson and McNemar are suppressed.

### 4.2 The two components

**Omnibus: Cochran's Q**

Cochran's Q tests whether the pass rate differs systematically across repetition indices.
This is appropriate for binary outcomes in a block design where the same scenario is
measured at each repetition position.

```
Q = (k - 1) · [k · Σᵢ Lᵢ² − (Σᵢ Lᵢ)²]
    ──────────────────────────────────────────
    k · Σⱼ Cⱼ − Σⱼ Cⱼ²
```

where:
- `k` = number of repetitions
- `Lᵢ` = number of passes at repetition index `i`, summed across all evaluated turns
- `Cⱼ` = number of passes for turn `j`, summed across all repetitions

Under H₀ (no order effect), Q ~ χ²(k − 1). A p-value below 0.05 is reported as a
significant order effect.

Cochran's Q requires k ≥ 3. For k = 2, skip the omnibus and go directly to the
pairwise comparison.

**Pairwise: first-vs-last McNemar**

Cochran's Q detects that some position differs; the pairwise comparison identifies
whether the *trend* is monotone from first to last. For each evaluated turn, form the
2×2 contingency table of (rep[0] outcome, rep[k-1] outcome) and apply McNemar's exact
test (the same `mcnemar_exact(b, c)` from `evals/paired_stats.py`).

This is a different use of McNemar from the run-to-run comparison (§3). Here, the
"before" and "after" are the first and last repetitions *within* a single run, not two
separate runs. This pairing is valid regardless of fidelity tier because it only claims
that rep[0] and rep[k-1] are from the same scenario — not that they are independent.

### 4.3 Reporting the order-effect check

The order-effect check always produces three numbers, regardless of fidelity:

1. Cochran's Q statistic and its p-value.
2. First-vs-last McNemar p-value.
3. Raw pass rates by repetition index (rep[0] rate, rep[1] rate, ..., rep[k-1] rate)
   so the direction and monotonicity of any effect are visible.

At **FULL** fidelity, a significant result (either test) is a **quality warning** shown
inline in the run report with the text:

```
ORDER EFFECT DETECTED (Q p=<value>, first-vs-last p=<value>).
Reset reported surviving=() but outcomes vary by position.
Flag for manual inspection before using this run's Wilson CIs.
```

At **PARTIAL** fidelity, the order-effect results are **the headline output** for the
run — presented before the raw sequence report, because they are the primary statistical
finding available.

---

## 5. Automatic downgrade rule

The downgrade is a two-step gate applied by the runner before report generation:

1. **Compute fidelity.** For each `Repetition`, check `reset_receipt.surviving`. If any
   `surviving != ()`, fidelity is PARTIAL. Otherwise FULL.

2. **Filter the metric set.** Look up the fidelity tier in the table in §3. Pass only
   the permitted metrics to the report formatter.

There is no third step. There is no "show Wilson CI with an asterisk". A suppressed
metric does not appear. This is intentional: an asterisked CI looks like an argument
in the report; a missing CI is a visible absence that prompts the reader to ask why.

---

## 6. Relationship to the single-turn eval harness (v1)

The v1 harness (`evals/summary.py`, `evals/rate_stats.py`, `evals/paired_stats.py`)
computes Wilson CIs and McNemar on single-turn cases. The v1 harness has no reset
concept — each case is a fresh, stateless invocation by construction.

This policy applies **only** to `SequenceRun` transcripts (v2 schema). It does not
retroactively change anything about v1 runs or the EVAL_METHODOLOGY.md guarantees.

If a future integration pathway passes `SequenceRun` aggregates into the v1 `summary.py`
pipeline, each `SequenceRun` must produce a single `CaseStat`-equivalent record only if
its fidelity is FULL. PARTIAL-fidelity `SequenceRun` records must not be aggregated into
v1 headline rates.

---

## 7. What this policy does NOT cover

- **Which components must appear in `cleared` for fidelity to be FULL.** The reset
  contract (which components the scenario runner is expected to clear) lives in the
  scenario definition, not here. This policy only reads `surviving`.

- **Minimum k for statistical validity.** At FULL fidelity, Wilson CI validity is
  independent of k (it is always valid, but the interval is wider at small k). The
  convention is to show k adjacent to every rate (see §3) so the reader can judge.

- **What to do if Cochran's Q cannot be computed** (k < 3 or every repetition produces
  the same outcome). Report that the test was not computable and why; do not substitute
  a different test silently.

- **How to migrate PARTIAL-fidelity runs to FULL.** Migration would require re-running
  with a corrected reset implementation, which is an EVAL-P12 harness concern, not a
  policy concern.

- **Cost of re-running.** EVAL-P14.3 addresses the cost model (blocked on EVAL-P12.4
  measured run times).

---

## Verification index

| Claim | Source |
|---|---|
| Fidelity determined from `reset_receipt.surviving` | `evals/sequence_records.py:ResetReceipt` |
| Wilson CI implementation | `evals/rate_stats.py:wilson_interval` |
| McNemar implementation (reused for first-vs-last) | `evals/paired_stats.py:mcnemar_exact` |
| Cochran's Q (to be implemented in future runner) | Not yet shipped — EVAL-P14 implementation phase |
| Order-effect check output format | §4.3 above |
