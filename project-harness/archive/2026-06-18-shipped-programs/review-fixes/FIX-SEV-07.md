# FIX-SEV-07 — Eval test hygiene: sys.path, asserted-not-measured guard, runner coverage

**Severity:** MEDIUM · **Lens:** L4 (L4-06, L4-02, L4-13), L8 (L8-01, L8-03)

## Problem
1. **REGRESSED:** 5 eval test files still call `sys.path.insert(...)` instead of importing via the package
   path (L4-06).
2. **Asserted-not-measured:** `test_secret_propagation_logs_seed` injects a `caplog` fixture but never
   queries it — the test passes even if the seed `LOGGER.debug()` call is deleted (L4-02 / L8-01).
3. `evals/runner.py` is 24% covered and excluded from the coverage gate; the HTTP call loop, result
   assembly, and the `guarantee_demonstrated` gate (`runner.py:395`) are untested (L4-13 / L4-03).

## Current shape (verify against code now)
- 5 eval test files with `sys.path.insert` — find: `grep -rl "sys.path.insert" tests/ evals/`.
- `tests/.../test_sev22_rng_determinism.py:75-83` — `caplog` param unused.
- `Makefile` `test-cov` target omits `--cov=runner`; `evals/runner.py` ~164 lines, 24%.

## Steps
1. Remove `sys.path.insert` from the 5 eval test files; rely on the installed package / conftest path (add
   the eval package to the path via `pyproject`/`conftest` once if needed, not per-file).
2. Strengthen `test_secret_propagation_logs_seed`: drive the real `run_tick` path (or the seed log call
   site) and assert `caplog.records` contains the seed key — so deleting the log breaks the test.
3. Add `--cov=runner` (or the runner package) to the `test-cov` gate and add tests for the runner's
   execution loop + the `guarantee_demonstrated` gate so coverage clears the 80% threshold (total stays
   ≥80% since the rest is 86.6%).

## Verification
- `grep -rl "sys.path.insert" tests/ evals/` returns empty.
- `pytest tests/ -k "secret_propagation or runner" -q` — confirm the seed-log test FAILS if the log line is removed (do this check manually once).
- `make test-cov` — runner included, gate green.

## Blast radius
5 eval test files, 1 guard test, `Makefile` test-cov target, possibly `conftest.py`/`pyproject`. Tests + build config only.
