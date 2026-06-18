# FIX-SEV-40 — Replace print() + hardcoded API-key default in seeder

**Severity:** LOW · **Effort:** S · **Category:** observability / security
**Absorbs:** PY-13, GRAPH-12

## Problem
The API seeder uses `print()` (violates the structured-logging rule) and ships a
real-looking shared secret as the default `--api-key`.

## Current shape (verified — api_seeder split by SEV-23)
- `src/npc_engine/data/api_seeder.py:75,85,94,103,113,123,134,143,153,175,186,197,216,227,243,280`
  — many `print(...)` calls (phase banners + summary).
- `src/npc_engine/data/seed_http.py:34,37,41,46,52` — `print(...)` for per-item OK/SKIP/FAIL
  + summary.
- `src/npc_engine/data/api_seeder.py:272` —
  `default=os.environ.get("NPC_API_KEY", "local_dev_secret_change_this_2026")`.

## Steps
1. Replace every `print(...)` in both files with the structured logger
   (`from npc_engine.utils.logging import get_logger`; `LOGGER = get_logger(__name__)`),
   at appropriate levels (info for progress, error for failures). Keep messages
   key-value-ish where it reads naturally.
2. Remove the hardcoded secret default: make `--api-key` resolve from `NPC_API_KEY` and
   **fail fast** with a clear error if absent (no baked-in fallback secret). Use a named
   error/message; do not `raise Exception(...)`.
3. This is a CLI/seeder (data layer) — logging to stdout is fine via the logger; just don't
   use bare `print`. Keep functions ≤40 lines.

## Verification
- `tests/unit/test_sev40_seeder_hygiene.py`:
  - `grep`-style: no `print(` remains in `api_seeder.py`/`seed_http.py` (assert via reading
    the source files or via a small AST/string check in the test).
  - Resolving the api key with `NPC_API_KEY` unset raises the fail-fast error; with it set,
    returns the value. (Test the key-resolution helper directly — extract one if needed.)
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev40_seeder_hygiene.py -q`

## Blast radius
Seeder CLI only (`make seed-api`). The fail-fast removes a convenient default — note that
`NPC_API_KEY` must now be set to run the seeder.
