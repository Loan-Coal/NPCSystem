# SEV-03 — Quest triggers multiply into 40+ sequential model calls per tick

🔴 **CRITICAL** · Finding **L11-03** (llm) · Confidence: Confirmed · Evidence: `evidence/L11.md`

## Problem

Three quest-trigger entry points each drive `quest_generation`, which retries up to 3 times. Nothing caps
the total across them. Worst case for one tick: **event triggers 10 invocations × ≤4 calls = 40**, plus
**need triggers 10 × ≤4 = 40** — and neither is covered by `skip_llm_engines` (see SEV-02). L13 derived
~84 model calls for a saturated tick from the shipped caps independently; L11 counted ~86 from the retry
loops. Costed against measured decode rates that is **84–220 seconds of model time in a single tick**.

There is one resident model. A player's dialogue turn arriving during that tick waits behind it.

## Current shape

- `src/npc_engine/engines/quest_generation/quest_generation_engine.py` — 3-attempt structured-output loop.
  `:277` `_ask_llm_for_fills` is the LLM call site.
- Three trigger engines feed it: `world_state_quest_trigger.py`, `event_quest_trigger.py`,
  `need_quest_trigger.py` — all run at `tick_scheduler.py:472`, inside the **ungated**
  `_ordered_tick_engines()` list.
- Per-caller retry caps exist; there is **no shared per-tick budget** across the three.
- Interactive quest generation via the API is ≤4 calls, unbudgeted, with no route-level timeout.

Note `need_quest_trigger` is currently dead anyway — its `:Need` nodes are orphans (L13-02, Decide D3).
Fixing that seed defect **increases** this load, so land this fix before D3.

## Steps

1. Confirm SEV-02 step 1 has landed (`skip_llm_engines` now reaches the three triggers). If not, do that
   first — it is the shared mechanism.
2. Add a **shared per-tick LLM call budget** the three triggers draw from, rather than three independent
   caps. Inject it as a constructor parameter (constructor injection only, per CLAUDE.md); when the
   budget is exhausted, triggers fall through to their existing deterministic path rather than raising.
3. Cap total trigger invocations per tick with a named constant, not a literal.
4. Do **not** change the retry counts as the primary fix — the amplification is the *product* of
   invocations and retries, and invocations are the larger term.

**Adjacent option, needs a decision (D-item, not part of this fix):** L11 recommends deleting the LLM
call from quest slot-filling entirely and always running the existing `_deterministic_fill` fallback —
zero new code, removes up to 30 of the ~86 calls, and the fallback is already proven. That is a
quality/creativity trade-off and it is **unmeasurable today** because all five judged scorers are
REFUSED. Do not take it unilaterally in this fix.

## Verification

Write the failing test first:

`tests/unit/engines/test_quest_trigger_shared_budget.py` — construct a tick in which all three triggers
fire with maximum candidates, count LLM calls through a mock adapter, and assert the total is ≤ the
shared cap. On the current tree this test should count 40+ and fail.

```
pytest tests/unit/engines/test_quest_trigger_shared_budget.py -v
make check
```

Live check: advance the clock with all triggers primed, read `llm_backend_calls_total` from
`GET /v1/admin/system/metrics` before and after, and confirm the per-tick delta is bounded.
Rebuild first — the app image is not bind-mounted.

## Blast radius

Three trigger engines plus `quest_generation_engine`. Constructor signatures change → the composition
root (`api/dependencies_engines/`) must be updated. No graph schema change. No public HTTP contract
change. Existing quest tests must keep passing — the deterministic fallback path is already exercised.

**Sequencing:** after SEV-02 (step 1), before SEV-04. Also land before Decide-D3 (`HAS_NEED` seed fix),
which would otherwise raise this load.
