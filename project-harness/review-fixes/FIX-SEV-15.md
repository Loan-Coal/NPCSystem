# FIX-SEV-15 — Get CI green: clear lint, add type to CI, restore `make check`

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** S (lint) + L (type burn-down, = SEV-14)
**Category:** build-infra / harness-drift · **Absorbs:** HARN-01, HARN-02, HARN-13, PY-04
**Do first** — unblocks a meaningful CI signal for every other fix. **Type-gating depends on:** SEV-14.

## Problem
`make lint` fails (38 ruff errors), `make type` fails (254 mypy errors) and is never run in CI, so the documented `make check` (`lint type test`) cannot pass. CI's `static-analysis` job is red on every push and `coverage-gate` (which `needs` it) is blocked.

## Current shape
- `.github/workflows/ci.yml:26` runs `make lint`; `03_lint.log` "Found 38 errors" → CI red on `on.push.branches:["**"]`.
- CI never runs `make type` / `make check`; `04_type.log` "Found 254 errors in 86 files".
- 30 of 38 lint errors are E402 from one misplaced line: `retrieval/context_builder.py:21` has `logger = logging.getLogger(__name__)` in the middle of the import block (lines 23-71 then flagged). 5 are auto-fixable (unused imports/vars); 1 is unused `TYPE_CHECKING` in `scheduler/tick_scheduler.py:23`.
- `Makefile:83` `check: lint type test`.

## Target shape
`make lint` exits 0; CI runs `make type` (reporting now, gating after SEV-14); `make check` is the real, runnable health gate.

## Steps
1. **Kill the 30 E402:** move `logger = logging.getLogger(__name__)` in `context_builder.py` to **after** the last import (after line 71).
2. **Auto-fix:** `ruff check --fix src/` (clears the 5 auto-fixable) and remove the unused `TYPE_CHECKING` import in `tick_scheduler.py:23` + the other 2 dead imports manually.
3. `make lint` → confirm 0.
4. **Add a CI type job** in `ci.yml`: a `make type` step. Make it **non-gating** (`continue-on-error: true` or `|| true`) until SEV-14 drives the count to 0, then flip to gating and add `make type` to the `check` path the pipeline runs.
5. Until type is green, document `make check` as "known-failing on type" in `NEXT_SESSION.md` (ties to SEV-25).

## Verification
- `make lint` exit 0; CI `static-analysis` green; `coverage-gate` runs.
- CI shows a `type` job (red but visible) → after SEV-14, green and gating.
- `make check` exits 0 once SEV-14 completes.

## Blast radius
All branches' CI signal. Step 1-3 are ~30 minutes and immediately unblock CI; step 4 makes the 254-error debt visible and trackable (it is currently invisible — see SEV-25).
