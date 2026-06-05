# FIX-SEV-41 — Force UTF-8 stdout in demo/scenario entrypoints

**Severity:** LOW · **Effort:** S · **Category:** portability
**Absorbs:** (live-observed) `make scenarios` UnicodeEncodeError on cp1252 console

## Problem
On the documented Windows target, `make scenarios` raised `UnicodeEncodeError` (cp1252
console) and `demo-run` output showed mojibake. Non-ASCII content (NPC dialogue, em-dashes)
crashes/garbles when stdout isn't UTF-8.

## Current shape (verified)
- `demo_game/run.py:470` — `def main()` (entry for `make demo-run`); `:492` `__main__`.
- `make scenarios` → `pytest e2e/scenarios/` (Makefile:146-147). Scenario output is emitted
  during these pytest runs; the entrypoint is pytest collecting `e2e/scenarios/`.
- No existing `reconfigure`/`PYTHONUTF8` handling in `demo_game/` (grep clean).

## Steps
1. Add a tiny idempotent helper `ensure_utf8_stdout()` that calls
   `sys.stdout.reconfigure(encoding="utf-8")` and the same for `sys.stderr`, guarded so it's
   a no-op when the stream already reports `utf-8` or lacks `reconfigure` (older streams).
   Put it in a small module, e.g. `demo_game/encoding_utils.py` (module docstring required).
2. Call it at the top of `demo_game/run.py:main()` (before any output).
3. For scenarios: create/extend `e2e/scenarios/conftest.py` to call the same logic at import
   (a 3-line local copy is acceptable if importing `demo_game` from `e2e` is awkward — keep
   it dependency-free). Goal: scenario stdout is UTF-8 before any test prints.

## Verification
- `tests/unit/test_sev41_utf8_stdout.py` (or `demo_game/tests/`):
  - `ensure_utf8_stdout()` is idempotent and a no-op on a fake stream lacking `reconfigure`
    (monkeypatch a dummy stream; assert no crash and reconfigure called when present).
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev41_utf8_stdout.py -q`
  (or the `demo_game/tests` path if you place it there).

## Blast radius
Demo runner + scenario test entrypoints. Pure output-encoding; no logic change.
