# Phase 2 Handoff

<!-- Fill in this document at the end of Phase 2. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass (demo_game/ unit tests):
   [ ] YES  [ ] NO — details: ...

3. E2E baseline:
   [ ] NO REGRESSION  [ ] REGRESSION
   details: ...

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [describe the demo game walkthrough — what was visible in the
   graph panel, what the NPC said, whether gossip was visibly propagating]

5. LLM judge (HARD gate):
   [ ] PASS  [ ] FAIL
   Verdict: [judge run on at least one demo-game-initiated dialogue turn]

6. Coverage on demo_game/ (excluding UI rendering):
   __% — [ ] PASS (≥78%)  [ ] SOFT FAIL — explanation: ...

---

## What Shipped

- [x] demo_game/ package scaffold — P2.1 done 2026-05-21
      EngineClient (8 methods), DemoConfig, stubs for seed/ui/graph_panel,
      GraphNode/GraphEdge/GraphSnapshot/GraphDelta dataclasses, 20 tests green,
      make demo / demo-seed / test-demo targets, .env.demo gitignored
- [ ] seed.py — demo world created via API calls  ← P2.2
- [ ] Dialogue UI — player input, NPC response display  ← P2.3
- [ ] Graph visualization panel — live-updating, faction-colored  ← P2.4
- [ ] Gossip trigger flow — event seeded → graph updates visible  ← P2.5
- [ ] LLM judge scenario — `e2e/scenarios/scenario_demo_game_judge.py` PASS  ← P2.5
- [ ] make demo target (functional, not stub)  ← P2.3
- [ ] docs/DEMO.md updated  ← P2.6

---

## What Was Deferred

- **ISSUE-019**: 20 pre-existing test failures — `consume()` missing on mock Neo4j result
  stubs in `tests/unit/`. Not introduced by P2.1. Logged in `ISSUES.md`. Defer to Phase 4+.
- `make test` accurate baseline: **20 failed, 951 passed, 17 skipped (988 total)** —
  the "964/965" figure in NEXT_SESSION.md (written post-Phase 1) was incorrect.

---

## Top 5 Rough Edges Identified (for Phase 4)

1. ...
2. ...
3. ...
4. ...
5. ...

---

## What Phase 3 Needs to Know

[Any observations from demo game UI about which engine behaviors are most
visibly weak — useful for confirming or adjusting Phase 3 target engine.]

---

## Decisions Graduated to project/DECISIONS.md

---

## NEXT_SESSION.md Update

```
Phase 3 — QLoRA Adapter (and/or Phase 4 can begin in parallel)

Entry criteria:
- Phase 2 handoff signed off: [YES/NO]
- Phase 1 handoff signed off: [YES/NO]
- Phase 3 target engine confirmed: [engine name]

Key context:
- demo_game/ location: demo_game/
- make demo: starts engine + demo game
- Visualization panel polls at [N]s intervals
- Top rough edges (for Phase 4): [list from above]
```
