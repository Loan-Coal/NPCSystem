# SEV-14 — The measurement-integrity tool is itself unmeasured

**HIGH** · Finding **L4-01** (tests) · Confidence: Confirmed · Evidence: `evidence/L4.md`

## Problem

`evals/arm_probe.py` and `evals/arm_probe_report.py` — the P9 measurement-integrity tooling — ship at
**0% coverage**. `evals/arm_probe_client.py` is at 46%.

This is the tool whose job is to establish that measurements are trustworthy. It is new since the
2026-08-28 baseline (it landed with Phase 5 in `ef870f7f`), it has no prior art in any review, and
nothing exercises its orchestration, its HTTP client, or its reporting.

Given that the whole judged-scorer layer is currently REFUSED and under repair, the tooling that decides
whether a measurement is sound is exactly the wrong thing to leave untested.

## Current shape

Untested behaviour, per L4's asserted-not-measured register:
- `evals/arm_probe.py` — `_run`, `_live_gates`, `main`: **no tests**
- `evals/arm_probe_client.py` — `ProbeClient.observe`, `.rehydrate`, `.corpus_fingerprint`: 46%
- `evals/arm_probe_report.py` — **no tests**

Adjacent files from the same Phase 5 landing worth checking while here: `arm_probe_gates.py`,
`arm_probe_models.py`, `arm_supply.py`.

Coverage floors that did not catch this: `make test-cov-evals` floor is 75 and the package sits at
**79.76%** — the aggregate passes while these specific modules sit at zero. That aggregate-hides-zero
pattern is worth noting in the fix.

## Steps

1. Add unit tests for `ProbeClient` first — it is the seam everything else goes through. Cover
   `observe`, `rehydrate`, `corpus_fingerprint`: success, HTTP error, malformed payload, and timeout.
   Mock the transport; **no live services** (`evals/` unit tests do no I/O).
2. Add tests for `arm_probe.py`'s orchestration: `_run` and `_live_gates` — that gates are evaluated,
   that a failing gate is reported as failing, and that the exit path reflects it. A probe that reports
   success on a failed gate is the defect class that matters most here.
3. Add tests for `arm_probe_report.py`: rendering a report from known records, including the empty and
   the all-failed cases.
4. Follow the repo's TDD rule — write each test, confirm it fails for the right reason, then keep it. For
   already-working code, confirm the test is capable of failing by breaking the source temporarily.
5. Consider a per-module coverage floor for the probe files, so the aggregate cannot hide a zero again.
   If the harness has no per-module mechanism, log it rather than building one here (single-task focus).

## Verification

```
pytest tests/unit/evals/ -v
make test-cov-evals          # floor 75; package was 79.76% at baseline
make check
```

Report the per-module coverage for `arm_probe.py`, `arm_probe_report.py` and `arm_probe_client.py`
before and after — the aggregate number is not the point of this fix and should not be quoted as if it
were.

Per invariant 6: do **not** run or cite any judged scorer while validating this. The probe's *mechanics*
are testable deterministically; its judged outputs are not currently trustworthy.

## Blast radius

Test-only — no source change to `evals/`. If a test cannot be written without restructuring a function
(e.g. `main` doing orchestration and I/O together), prefer a narrowly-scoped extraction over an
integration test that needs live services, and note the extraction in the summary.

Watch the `evals/` import conventions: ISSUE-289 (`mypy.ini`'s `mypy_path = src` Any-types intra-`evals/`
imports) and ISSUE-132 (mixed flat and package-absolute imports) are both open and both affect how these
tests should import. Follow the surrounding files rather than inventing a third convention.

**Sequencing:** fully independent — parallelisable.
