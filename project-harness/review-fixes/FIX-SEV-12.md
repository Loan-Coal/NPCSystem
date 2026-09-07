# SEV-12 — `engine_status` is read by nothing and cannot express "starved"

**HIGH** · Finding **L13-04** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

Engines are exception-isolated so one bad engine cannot halt the tick. That is sound — but it converts a
loud crash into a **silent absence** with no compensating signal.

Measured live: **27 engines ran, every `last_error` null, and only 6 did any work.** 17 reported zero
effect. Two of those are provably dead (their queries match nothing — L13-01, L13-02), and the status
record **cannot tell that apart from healthy idleness**: `error_count: 0`, `tick_count: 7` and a non-null
`last_duration_ms` look identical for "ran and correctly did nothing" and "ran and did nothing because
its working set is permanently empty."

`GET /health` returned `{"status":"ok"}` throughout and would do so with every engine erroring.

## Current shape

The record itself is complete and useful — `scheduler/engine_status_store.py`'s `EngineStatusRecord`
carries `last_tick_id`, `last_error`, `last_error_tick`, `error_count`, `last_duration_ms`, `tick_count`,
populated at `tick_scheduler.py:225-241` via `EngineTickTimer`.

It is surfaced at:
- `api/routes/admin/system.py:98-109` — `GET /v1/admin/system/engines`
- `api/routes/world/clock.py:131`

And consumed by **nothing**: `grep -rn "engine_status\|last_error\|error_count" src/npc_engine/api/`
returns only the wiring and those two read routes. No metric, no health-check integration, no gate.

## Steps

Two changes. **(2) is the load-bearing one** — without it, (1) would not have caught L13-01 or L13-02.

1. **Export the error signal as metrics.** Add `engine_last_error_tick` and `engine_error_count` gauges to
   `GET /v1/admin/system/metrics`, next to the DEC-273 `llm_backend_*` metrics, so `last_error` lands
   where the latency work already put its signal.
2. **Make "starved" expressible.** Add `working_set_size` (or a `worked` boolean) to `EngineStatusRecord`,
   set by the scheduler from the engine's return payload, so *"ran and did nothing because there was
   nothing to do"* is distinguishable from *"ran and did nothing because its query matches nothing."*
   Engines already return payloads like `{'moved': 0, 'skipped': 0}` — the scheduler can derive this
   without touching each engine.
3. Export that as a gauge too, so a permanently-zero working set is visible over time rather than only in
   a single admin poll.
4. Do **not** add a gate that fails the build on an idle engine in this fix — several engines are
   legitimately idle in the demo seed. Make it visible first; gate once Decide-D2/D3 settle which
   engines are supposed to be doing work.

## Verification

Write the failing tests first:

`tests/unit/scheduler/test_engine_status_working_set.py`
- an engine returning a zero-size working set records `working_set_size: 0` and is distinguishable from
  one that did work
- the field survives the store round-trip

`tests/unit/api/test_engine_status_metrics_exported.py`
- an engine with a non-null `last_error` produces a non-zero `engine_error_count` on the metrics endpoint
- a starved engine is visible as a zero working set

```
pytest tests/unit/scheduler/ tests/unit/api/test_engine_status_metrics_exported.py -v
make check
```

Live confirmation — this fix is only worth anything if it surfaces the real defect: bring the stack up,
advance the clock ~6 times, and confirm the metrics now show `routine` and `need_decay` with a
permanently zero working set. That is the observable that was missing.

## Blast radius

`scheduler/engine_status_store.py` (a model field — Pydantic, so additive and backward compatible),
`tick_scheduler.py` (populating it), and the admin metrics route. Additive only; no existing field
changes meaning, no route signature changes.

**Sequencing:** independent — parallelisable. High value **before** Decide-D2/D3, because it turns "17
engines look idle" into a measurable list rather than a one-off observation from this review.
