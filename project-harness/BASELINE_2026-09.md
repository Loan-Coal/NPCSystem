# Baseline 2026-09 (post-Sprint-6 / T12.2)

Measured 2026-09-21 at T12.2. This file supersedes
`project-harness/review-2026-08/BASELINE_2026-08-28.md` (ISSUE-321).
The 2026-08-28 file is retained as history and is deliberately immutable.

A number that moves without an explanation relative to this file is a finding.

---

## Test counts

| Suite | Passed | Skipped | Command |
|---|---:|---:|---|
| Unit + scripts | 4,650 | 97 | `make test` |
| Demo | 1,157 | 0 | `make test-demo` |

---

## Coverage

Both floors are unchanged from the Sprint-6 roadmap spec (prune did not move coverage
materially — the deleted set was better covered than the mean, as predicted).

### `src/npc_engine/` (main floor: 80%)

| Metric | Value |
|---|---:|
| Statements | 17,366 |
| Missing | 2,231 |
| Coverage | **87.15%** |
| Floor | 80% |
| Headroom | +7.15 pp |

Command: `make test-cov` (run inside `make check`; contexts from `test-cov-run`).

### `evals/` (evals floor: 75%)

Re-measured at T12.2 after adding `test_arm_probe_client.py`, `test_arm_probe_report.py`,
`test_arm_probe_run.py`. The three previously-zero modules:

| Module | Before | After |
|---|---:|---:|
| `evals/arm_probe.py` | 0% | 98.7% |
| `evals/arm_probe_client.py` | 46.2% | 100% |
| `evals/arm_probe_report.py` | 0% | 100% |

| Metric | Value |
|---|---:|
| Aggregate (evals/) | **85.08%** |
| Floor | 75% |
| Headroom | +10.08 pp |

Command: `make test-cov-evals` (runs after `test-cov-run` in `make check`).

**No per-module floor exists** — see ISSUE-365. The aggregate can hide a module at
zero again. This is the gap these new tests were written to address directly; an
enforcement mechanism is a separate task.

---

## mypy

| Scope | Errors |
|---|---:|
| `src/` (572 source files) | **0** |

Command: `make type` (`mypy src/`).

---

## LOC (non-test Python)

From `make check-loc-ratchet` at T12.2:

| Area | LOC |
|---|---:|
| `src/npc_engine/` | 65,092 |
| `scripts/` | 11,433 |
| `evals/` | 23,060 |
| `demo_game/` | 21,577 |
| **total** | **121,162** |

Ratchet baseline: 121,162 (609 LOC headroom from the ratchet gate). The ratchet
permits only decreases; any task increasing this total must bump the baseline with
a stated reason.

---

## CI gate status

`integration-tests` is a **required** status check for merge on `main` (DEC-288,
owner decision 2026-09-17). `make check` runs without Neo4j; the integration job
supplies the Cypher-coverage that `make check` cannot.
