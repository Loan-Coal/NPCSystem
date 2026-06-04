# FIX-SEV-35 — Unify `delta_ticks` bound to one `MAX_DELTA_TICKS` constant

**Severity:** LOW · **Confidence:** Confirmed · **Effort:** S
**Category:** security · **Absorbs:** SEC-03, GAME-09

## Problem
Three inconsistent bounds for `delta_ticks`:
- `api/routes/clock.py:32` uses `le=200`
- Project rule says `[1, 1000]`
- Secondary guard in tick_scheduler uses `MAX_CONCURRENT_TICKS * 10` (magic number)
- `demo_game/client.py` docstring says "1–200"

## Current shape
- `api/routes/clock.py:32`: `delta_ticks: int = Field(..., ge=1, le=200)`
- `scheduler/tick_scheduler.py`: guard using `MAX_CONCURRENT_TICKS * 10` (verify exact line)
- `demo_game/client.py`: docstring states "1–200"

## Steps
1. In `src/npc_engine/config.py`: add `MAX_DELTA_TICKS: int = 1000`.
2. In `api/routes/clock.py`: replace `le=200` with `le=settings.MAX_DELTA_TICKS`; import `get_settings()` if not already present.
3. In `scheduler/tick_scheduler.py`: find and replace the `MAX_CONCURRENT_TICKS * 10` guard with `settings.MAX_DELTA_TICKS`; import settings if needed.
4. In `demo_game/client.py`: update docstring to say "1–1000".
5. Run `rg "le=200" src/` and `rg "CONCURRENT_TICKS \* 10" src/` to confirm no remaining instances.

## Verification
- `rg "le=200" src/` → 0 matches
- `rg "MAX_CONCURRENT_TICKS \* 10" src/` → 0 matches
- `make type` passes (no new errors)
- `make test` passes

## Blast radius
Clock route validator and tick scheduler guard only.
