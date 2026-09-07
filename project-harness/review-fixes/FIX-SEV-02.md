# SEV-02 — `TICK_LLM_CALLS_PER_MINUTE_MAX` is broken on all three axes

🔴 **CRITICAL** · Finding **L13-05** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

This is the **only** mechanism in the system meant to stop background tick work from eating the single
resident model. All three of its axes are broken, so in the *recommended* clock mode it does not exist.

A studio reading the setting name reasonably concludes background LLM work is capped at 6 calls/minute.
The real ceiling in `game_driven` mode is **unbounded**; even in `realtime` mode it is 6 *ticks* × up to
84 calls ≈ **500 calls/minute** against one 7B model.

## Current shape

**Wrong unit.** `src/npc_engine/scheduler/tick_budget_guard.py:76-83` — `record_llm_tick()` appends
**one** timestamp per tick regardless of how many model calls that tick made. A tick making 84 calls
costs the budget exactly 1. The setting name is a lie about its unit.
- `config.py:272` — `TICK_LLM_CALLS_PER_MINUTE_MAX: int = 6`
- wired at `main.py:222` into `TickBudgetGuard`, enforced at `tick_autopilot.py:85-102`

**Wrong coverage.** `skip_llm_engines` is read at exactly two sites:
`tick_scheduler.py:467` (`chapter`) and `:535` (`memory_consolidation`). The three quest triggers run at
`:472` inside the ungated `_ordered_tick_engines()` list and are **63 of the 84** worst-case calls.
Load-shedding therefore removes 25% of the calls and leaves 75%. (Independently confirms L11-03.)

**Wrong entry point.** `tick_scheduler.py:552` — `advance(..., skip_llm_engines: bool = False)`.
`api/routes/world/clock.py`'s `advance_clock` **never passes it**; `grep -rn "skip_llm_engines"
src/npc_engine/api/` → no matches. Only `tick_autopilot.py:98` supplies it. `ENGINES.md:29-31` calls
`game_driven` the **"recommended"** mode, and the eval stack runs exactly that
(`CLOCK_MODE=game_driven`, `TICK_AUTOPILOT_ENABLED=false`) — so the guard was never constructed during
any measurement in DEC-273.

## Steps

Three separable steps. **Do step 1 first — it is ~5 lines and delivers most of the value.**

1. **Extend `skip_llm_engines` to the three quest triggers** (`tick_scheduler.py` around `:472`), the
   same way `chapter` (`:467`) and `memory_consolidation` (`:535`) are already gated. This converts a
   25% shed into a **100% shed** and is the cheapest real win in the whole review.
2. **Move the gate from the autopilot into `TickScheduler.advance()`** so both clock modes get it, and
   have `advance_clock` (`api/routes/world/clock.py`) pass it through. Today `game_driven` — the
   recommended mode — has no budget at all.
3. **Increment the guard per call, not per tick.** The seam already exists: DEC-273's
   `llm_backend_calls_total` counter sits at exactly the right place. Rename the setting to match its
   unit, or keep the name and make it true — but do not ship a third mismatch.

Steps 2 and 3 change a public config contract; if you prefer, land step 1 alone and log 2–3.

## Verification

Write failing tests first, one per step:

- `tests/unit/scheduler/test_tick_budget_guard_counts_calls.py` — a tick issuing N model calls advances
  the budget by N, not by 1.
- `tests/unit/scheduler/test_skip_llm_engines_covers_quest_triggers.py` — with `skip_llm_engines=True`,
  assert the three quest trigger engines make **zero** LLM calls. This test must fail on the current
  tree; that failure is the bug.
- `tests/unit/api/test_advance_clock_passes_skip_llm.py` — `advance_clock` propagates the flag.

```
pytest tests/unit/scheduler/ tests/unit/api/test_advance_clock_passes_skip_llm.py -v
make check
```

Then measure live, since the point is load: bring the stack up, advance the clock with the budget
exhausted, and confirm via `GET /v1/admin/system/metrics` that `llm_backend_calls_total` stops rising
for tick-originated engines while dialogue still works.

## Blast radius

`scheduler/` (tick_scheduler, tick_budget_guard, tick_autopilot), one API route, one config field.
No graph schema change. Step 3 changes the meaning of an existing setting — record it in `DECISIONS.md`.

**Sequencing:** SEV-03 and SEV-04 build on this. Land step 1 here before starting SEV-03, or you will
fix the same amplification twice.
