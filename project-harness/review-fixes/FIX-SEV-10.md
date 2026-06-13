# FIX-SEV-10 — `check_layers.py` misses intra-rank + silently skips unranked packages

**Severity:** LOW · **Lens:** L2 (L2-09)

## Problem
The layer checker only fails when `importer_rank < imported_rank`, so within-rank peer imports are
unchecked, and any package with no rank entry (e.g. `observability`) gets `_UNKNOWN_RANK = -1` and is
**silently skipped** — future Python added under `src/npc_engine/observability/` would be invisible to the
guard.

## Current shape (verify against code now)
- `scripts/check_layers.py:113` — `if importer_rank < imported_rank:` (the only failure condition).
- `LAYER_RANK` dict has no `observability` entry; unknown packages → `_UNKNOWN_RANK = -1`.

## Steps
1. Add `"observability": 1` (or the correct peer rank — it is ops/config data at the lowest tier) to `LAYER_RANK`.
2. Make an unknown/unranked package an explicit **failure** (or at minimum an emitted warning that the test
   asserts on) rather than a silent skip, so a new unranked layer cannot bypass the check.

## Verification
- Add `tests/.../test_check_layers.py` cases: an unranked-package import is flagged; the existing valid
  layering still passes.
- Run `make check-layers` and `pytest tests/ -k check_layers -q`; `make check` green.

## Blast radius
`scripts/check_layers.py` + its test. Tooling only — confirm no currently-valid import newly trips the
stricter check before committing.
