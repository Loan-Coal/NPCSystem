# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S2.3 — Oath violation detection (ISSUE-032)
**Next task:** S2.4 — Treaty tribute + economy/price verify
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 2, S2.4
**Test baseline:** 1157 passing, 0 failed (unit)

---

## S2.4 — What to do

Two sub-tasks:

1. **Treaty tribute** (ISSUE-033): implement `check_tribute_payment()` in
   `src/npc_engine/graph/treaty_service.py`. Query currency-transfer edges for
   the tribute period; verify faction treasury ≥ condition.amount before flagging
   as violation. Currently `check_treaty_conditions_mechanical` flags tribute as
   due without checking payment.

2. **Economy price verify** (ISSUE-046): start engine + `make demo-seed`, then
   `curl "http://localhost:8000/v1/economy/price?item_type=spice&character_id=aldric_merchant"`.
   If 404, find correct route in `src/npc_engine/api/`; if schema differs, update
   `demo_game/client.py:get_item_price()`.

**Exit criteria:** both pass integration tests against live Neo4j.

---

## S2.3 — What was done

- Added `pledge_violation_service.py` (new graph-layer module) with:
  - `check_pledge_violations()` replacing the stub in `pledge_service.py`
  - `_VIOLATION_ACTIONS`/`_VIOLATION_ROLES` dicts mapping pledge type → violation signals
  - Cypher queries `CYPHER_GET_WITNESSED_VIOLATIONS`, `CYPHER_GET_PARTICIPATED_VIOLATIONS`
  - `_emit_violation_event()` writing high-severity Event nodes on violation
- Added `get_active_pledges_for_pledger`, `get_witnessed_violations`,
  `get_participated_violations`, `get_all_active_pledgers` to `pledge_queries.py`
- Added `get_all_active_pledgers_svc` to `pledge_service.py`
- Fixed `oath_engine.run_tick`: now queries all active pledgers and calls
  `check_pledge_violations` for each; result dict now includes `violated_pledges` count
- Updated stale stub test in `test_pledge_service.py`
- 10 new unit tests in `tests/unit/test_pledge_violations.py`
- Marked ISSUE-032 fixed in ISSUES.md

---

## Open issues

| Issue | Sev | Targeted by |
|---|---|---|
| ISSUE-046 | P2 | S2.4 |
| ISSUE-031, 033 | P3 | Phase 2/6 |

**Next ID to use: ISSUE-048.**

---

*Regenerated end of S2.3 session 2026-06-03.*
