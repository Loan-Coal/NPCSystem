# Issues Log

Persistent issue tracker. IDs are monotonic and never reused.
When an issue is fixed, change heading to `## [FIXED] ISSUE-NNN: <title>` and add a `**Fixed:** YYYY-MM-DD` line.

---

## ISSUE-001: Military engine run_tick is a stub
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/military/military_engine.py`
**Description:** `MilitaryEngine.run_tick` returns `{"skipped": True}` with no logic. Battle resolution, resource yield, and depletion tracking are not implemented.
**Why deferred:** User confirmed military tick logic should be deferred; engine is wired for future expansion.
**To fix:** Implement battle resolution (opposing armies at same location → strength comparison, CONTROLS/OCCUPIES edge updates), resource yield (PRODUCES → faction.treasury per tick), and depletion tracking (ResourceNode.depletion decrement).

---

## ISSUE-002: OathEngine.check_pledge_violations returns empty list
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/oath/oath_engine.py`
**Description:** Violation scan stub returns `[]` unconditionally. Pledgers whose recent actions conflict with their pledge are never flagged.
**Why deferred:** Violation detection requires cross-referencing PARTICIPATED_IN and WITNESSED edges against pledge semantics — non-trivial scope for initial implementation.
**To fix:** For each active pledge, query pledger's PARTICIPATED_IN and WITNESSED edges since `sworn_at_tick`; check action_type against pledge_type; call `break_pledge` on violation and generate high-severity EVENT.

---

## ISSUE-003: Treaty tribute condition checking does not verify payment
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/treaty_service.py:check_treaty_conditions_mechanical`
**Description:** Tribute conditions detect when payment is due (tick % interval == 0) but do not verify whether payment was actually made. All tribute conditions are flagged as due without checking faction treasury.
**Why deferred:** Payment verification requires faction treasury write operations not yet implemented in this layer.
**To fix:** Query faction treasury, verify amount >= condition.amount, deduct on payment, and only flag as violation if treasury insufficient.

---

## ISSUE-004: SATISFIES_NEED src_type is multi-type (Item or Location)
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/type_registry/base_edges/satisfies_need.yaml`
**Description:** SATISFIES_NEED should accept both Item and Location as source nodes, but the type registry YAML format only supports a single string for `src_type`. Current implementation uses `location` as src_type; Item→Need satisfaction is not schema-registered.
**Why deferred:** Registry extension to support multi-type src_type requires changes to `registry.py` edge model validation — out of scope for Phase 7 L.
**To fix:** Either (a) add an `item_satisfies_need.yaml` edge type for Item→Need, or (b) extend registry to accept `src_type: [location, item]` list syntax.
