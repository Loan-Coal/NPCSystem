# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S0.5 — Reputation-differentiated dialogue tone (ISSUE-035)
**Next task:** S1.1 — Autonomous tick driver
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 1, S1.1
**Test baseline:** 1077 passing, 19 skipped (engine) | 254 passing (demo)

---

## S1.1 — What to do

Add a background task to `main.py` lifespan that calls `tick_scheduler.advance()`
every N seconds (`TICK_INTERVAL_SECONDS` default 10; `TICK_AUTOPILOT_ENABLED` default
true in demo). Mirror the `embedding_reconciler.run_forever()` pattern. Do NOT write
a new scheduler — reuse the existing scheduler's per-engine cadence and lease/idempotency.

**Exit criteria:** Server up with no client calls → `Event` nodes and `KNOWS_ABOUT`
edges change over 60 seconds (observable via `GET /v1/graph/nodes/Event`).

---

## Open issues

| Issue | Sev | Targeted by |
|---|---|---|
| ISSUE-046 | P2 | pre-recording check |
| ISSUE-031, 032, 033 | P3 | Phase 2/6 |

**Next ID to use: ISSUE-048.**

---

*Regenerated end of S0.5 session 2026-06-02.*
