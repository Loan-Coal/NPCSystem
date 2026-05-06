# Next Session Instructions

## Foundation is clean — Phase 1 is ready to start

Phase 0.4 (per-engine LLM config) and Phase 0.5 (ISSUES 001–003 cleanup) are both done.
All open issues are resolved. No deferred P1/P2 items exist.

```bash
pytest tests/ -q
# Expected: green (run to confirm before starting Phase 1)
```

## Phase 1.1 — Faction nodes and membership (next)

**Goal:** Add Faction as a first-class graph node, with characters belonging
to factions and factions standing toward each other.

**Key file:** `project/ROADMAP.md` Feature 1.1 section — read it first.

**Steps per ROADMAP:**
1. Schema files: `type_registry/base_nodes/faction.yaml`,
   `type_registry/base_edges/member_of.yaml`, `stands_with.yaml`, `controls.yaml`
2. Service: `src/npc_engine/graph/faction_service.py` (≤300 lines)
   - create_faction, add_member, remove_member, set_standing, query operations
3. Unit tests for service operations
4. Integration tests against test Neo4j
5. API endpoints under `/v1/graph/admin/factions/*`
6. E2E script `e2e/scripts/faction_setup.py`
7. `docs/DATA_MODELS.md` updated with Faction schema
8. Migration script `scripts/migrations/add_factions.py` (idempotent)

**Not in this feature:**
- Faction-aware gossip (Feature 1.2)
- Faction-aware dialogue context (later)
- WorldState `faction_standings` JSON field migration
