# SEV-08 — `delta_ticks: 1000` runs 27 engines 1000× in one request on a frozen snapshot

**HIGH** · Finding **L13-09** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

Two defects in one call path.

**Unbounded work behind a cap that looks like a cap.** `le=1000` satisfies the input-cap rule in form,
not in effect: a single authenticated request can occupy the scheduler for hours and issue tens of
thousands of model calls, with no timeout and no back-pressure. At the measured 433–570 ms deterministic
floor, 1000 ticks is ≈ **8 minutes of held lock with no LLM work at all**; with quest triggers firing it
is unbounded (see SEV-03).

**A correctness bug.** `advance()` reads `world_state` **once, before** the loop and passes the same
object into every iteration — so batched advances see a `time_of_day` that never changes.

## Current shape

- `config.py:52` — `MAX_DELTA_TICKS: int = 1000`
- `api/routes/world/clock.py:37` — `delta_ticks: int = Field(default=1, ge=1, le=MAX_DELTA_TICKS)`
- `scheduler/tick_scheduler.py:568-582` — `world_state = await get_world_state(...)` is read **before**
  the `for tick_id in range(...)` loop and reused for every iteration
- Consequences inside the loop: `routine.run_tick(time_of_day=world_state.time_of_day)` (`:461`) sees a
  frozen time-of-day for all N ticks; `_maybe_consolidate_memory` (`:538-543`) builds its `TimePoint`
  from the same pre-loop snapshot
- The whole range runs inside `async with self._lock` (`:567`) on a single `AsyncSession`, with
  `skip_llm_engines` false throughout (SEV-02)

Note: `routine` is currently inert anyway (L13-01 — the seed writes no `:Schedule`). Once that is fixed
(Decide D2), this frozen snapshot would move NPCs into the same slot 1000 times. Fix the snapshot first.

## Steps

1. **Re-read `world_state` inside the tick loop** — or at minimum recompute `time_of_day` and the
   consolidation `TimePoint` per tick. This is the correctness half and it is independent of the cap.
2. **Lower `MAX_DELTA_TICKS`** to something a frame can absorb (single digits). Keep it a config field
   with a validator, not a literal.
3. If large catch-up advances are a genuine requirement, do **not** solve it by raising the cap — make
   it an explicit background job with its own budget, rather than a synchronous HTTP call. Log that as a
   DECISIONS question rather than building it here.
4. Consider a wall-clock ceiling on a single `advance()` call as defence in depth.

Step 2 changes a shipped config default. It is a public-contract change in spirit — note it in
`DECISIONS.md` with the measured justification (8 minutes of held lock at 1000).

## Verification

Write the failing tests first:

`tests/unit/scheduler/test_advance_rereads_world_state.py` — advance N>1 ticks across a time-of-day
boundary and assert the engines observe **changing** `time_of_day`, not the pre-loop value. This fails on
the current tree; that failure is the bug.

`tests/unit/api/test_clock_advance_delta_bound.py` — `delta_ticks` above the new cap is rejected with a
422 at the boundary, and the boundary value itself is accepted.

```
pytest tests/unit/scheduler/ tests/unit/api/test_clock_advance_delta_bound.py -v
make check
```

Live: advance across a day boundary and confirm from the structured logs that `routine` and memory
consolidation see successive time-of-day values.

## Blast radius

`tick_scheduler.advance()` (hot path — every tick goes through it), one API request model, one config
default. Re-reading world state per tick adds a graph read per tick: measure the cost against the
433–570 ms baseline and confirm it is noise, not a new regression. No graph schema change.

Callers passing large `delta_ticks` will start getting 422s — check `demo_game/` and `evals/` for any
caller relying on a large batch advance before lowering the cap.

**Sequencing:** independent — parallelisable. Land the snapshot fix (step 1) before Decide-D2.
