# FIX-SEV-12 — Clique engine magic numbers → config keys

**Severity:** LOW · **Lens:** L7 (L7-07)

## Problem
`CliqueFormationEngine` hardcodes three numeric thresholds with no `config.py` keys, violating the
CLAUDE.md strict rule "no raw numeric thresholds." The tick interval is correctly injected via settings;
these three bypass it.

## Current shape (verify against code now)
- `src/npc_engine/engines/.../clique_formation_engine.py:34` — `_AFFECTION_THRESHOLD = 70`, plus `_INITIAL_COHESION = 10` and `_STALE_CLIQUE_AGE_TICKS = 50`.

## Steps
1. Add `CLIQUE_AFFECTION_THRESHOLD: int = 70`, `CLIQUE_INITIAL_COHESION: int = 10`,
   `CLIQUE_STALE_AGE_TICKS: int = 50` to `config.py` (`Settings`).
2. Read them from the injected `settings` in the engine constructor; drop the module-level constants (or
   keep them only as fallbacks sourced from settings — prefer reading settings).

## Verification
- `pytest tests/ -k clique -q` — add/adjust a test that overrides the settings values and asserts the engine uses them.
- `make check`.

## Blast radius
`engines/.../clique_formation_engine.py` + `config/config.py` + clique tests. No interface/schema change;
defaults preserve current behavior.
