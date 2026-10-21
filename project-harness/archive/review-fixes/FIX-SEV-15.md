# SEV-15 — No test pins the tick execution order

**MEDIUM** · Finding **L13-10** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

`ENGINES.md` states that the scheduler runs engines in a fixed order so upstream state is visible
downstream **within the same tick**. L13 mapped the actual read-after-write dependencies (see
`evidence/L13.md` §A.2) and found real ones — but **nothing pins the order.**

Reordering `_ordered_tick_engines()`, or inserting a new engine in the wrong position, silently changes
behaviour. No test goes red. The failure mode is not a crash; it is an engine reading state that has not
been written yet this tick and quietly doing nothing — which, per SEV-12, is currently indistinguishable
from healthy idleness.

This is cheap to fix and it protects every dependency in the map at once.

## Current shape

- `src/npc_engine/scheduler/tick_scheduler.py` — `_ordered_tick_engines()` defines the order as a
  literal list (`("military", self._military_engine)` at `:356`, quest triggers at `:472`, `chapter`
  gated at `:467`, `memory_consolidation` at `:535`).
- The documented contract lives in `ENGINES.md`; the code is the only other statement of it.
- No test asserts the sequence, and no test asserts any specific read-after-write pairing.
- Adding an engine already requires editing 4 files (L7-03) — so the order is edited by hand, routinely,
  with no guard.

## Steps

1. Add a test that pins the **full engine execution order** as an explicit expected sequence. Keep the
   expected list in the test, not imported from the source — a test that reads the order from the code it
   is checking asserts nothing (that is the asserted-not-measured trap).
2. Add targeted tests for the specific read-after-write dependencies documented in `evidence/L13.md`
   §A.2 — for each pair, assert the writer's index is lower than the reader's. These survive a
   legitimate reordering that preserves semantics, whereas the full-sequence test intentionally does not.
3. Make the full-order test's failure message useful: on mismatch, print expected vs actual so the next
   person can tell an intentional reorder from an accident, and point them at `ENGINES.md`.
4. Cross-check `ENGINES.md` against the pinned order and correct the doc if they disagree. If they
   disagree, that discrepancy is itself a finding — report it rather than silently conforming the doc to
   the code.

## Verification

Confirm the test can fail: swap two adjacent engines in `_ordered_tick_engines()`, run the test, confirm
**red**, then restore.

```
pytest tests/unit/scheduler/test_tick_order.py -v
make check
```

No live run needed — this is a pure structural guard.

## Blast radius

Test-only, plus a possible `ENGINES.md` correction. No source change.

The one design risk is brittleness: a full-order assertion will fail on every legitimate engine addition.
That is intentional — the point is that adding an engine should require consciously placing it — but say
so in the test docstring so the next contributor updates it deliberately rather than deleting it in
frustration. The §A.2 pairwise tests are the ones that should *never* need touching.

**Sequencing:** fully independent — parallelisable. Worth doing early: it protects the tick order while
SEV-02, SEV-03 and Decide-D2/D3 all change what runs in a tick.
