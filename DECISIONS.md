# Decisions Log

Non-obvious architectural choices. Each entry explains what was decided and why,
so future maintainers can judge edge cases without re-deriving the rationale.

---

## DEC-001: LEVERAGE is a reified node, not an edge
**Date:** 2026-05-19
**Context:** Phase 7.2 Political Simulation adds a leverage mechanic where one character holds leverage over another, grounded in a shared secret.
**Decision:** LEVERAGE is implemented as a node (`Leverage`) rather than a `Character→Character` edge.
**Schema:** `Character -[HAS_LEVERAGE]→ Leverage -[AGAINST]→ Character`, with `Leverage -[GROUNDED_IN]→ Secret`.
**Why:** Neo4j edges cannot have outgoing edges — only nodes can. F3 fix requires `GROUNDED_IN: LEVERAGE → Secret` for graph traversal. A reified node is the correct solution. It also makes leverage queryable as a first-class entity (e.g., find all leverage nodes with status=held).
**Alternative rejected:** Keep LEVERAGE as an edge with `secret_id` string FK and skip F3. Rejected because it defeats the graph-traversal benefit and was explicitly called out as a flaw in the roadmap.

---

## DEC-002: Military engine run_tick is a stub
**Date:** 2026-05-19
**Context:** Phase 7.4 Strategy/4X adds ARMY, RESOURCE_NODE, and military infrastructure. The tick logic (battle resolution, resource yield, depletion) is complex and was not specified in detail.
**Decision:** `MilitaryEngine.run_tick` is a stub returning `{"skipped": True}`. The engine is wired into TickScheduler to enable future expansion without schema changes.
**Why:** User explicitly confirmed military logic should be deferred. Wiring the stub now means the scheduler interface does not need to change when logic is added.

---

## DEC-003: Succession engine queries HOLDS_TITLE edge (F2 fix)
**Date:** 2026-05-19
**Context:** The roadmap originally defined `TITLE.current_holder_id` as a string field. F2 identifies this as a staleness risk.
**Decision:** `title.yaml` does NOT include `current_holder_id`. The current holder is always determined by querying the `HOLDS_TITLE` edge in Neo4j.
**Why:** A denormalized `current_holder_id` field goes stale whenever a title is transferred. Graph edges are the authoritative, always-consistent source. The succession engine and any code needing the current holder must use `political_queries.get_current_title_holder`.

---

## DEC-004: SATISFIES_NEED uses location src_type only (ISSUE-004)
**Date:** 2026-05-19
**Context:** SATISFIES_NEED should accept both Item and Location as source nodes per the roadmap.
**Decision:** Initial implementation registers `satisfies_need.yaml` with `src_type: location` only. Item→Need satisfaction is deferred to ISSUE-004.
**Why:** The type registry YAML format supports a single `src_type` string. Adding multi-type support requires registry changes out of scope for this phase. Location-based satisfaction covers the primary use case (a tavern satisfies the social need).

---

## DEC-005: controls.yaml gains optional fields (schema extension)
**Date:** 2026-05-19
**Context:** Phase 7.4 roadmap specifies adding `control_strength` (0–100) and `contested_by_faction_id` to the existing `CONTROLS` edge.
**Decision:** Both fields added as `required: false` to `controls.yaml`. Existing CONTROLS edges without these fields remain valid.
**Why:** Making them optional preserves backward compatibility — existing graph data does not need migration. Military engine can write these fields when it sets control state; political and faction engines can read them without breaking if absent.

---

## DEC-006: Demo gossip chain is pre-seeded, not live-propagated
**Date:** 2026-05-22
**Context:** Roadmap V3 Phase 1. The gossip propagation engine selects pairs by co-location (`LOCATED_AT`). Captain Sorn is alone at `loc_guard_barracks`, so the engine cannot propagate northern_war_begins to Mira (tavern) or Henryk (market_square) in the 3 ticks the demo script fires.
**Decision:** Pre-seed distorted KNOWS_ABOUT edges for `mira_innkeeper` and `old_henryk` in `demo_game/seed.py`. The 3 ClockTick scenes in `demo_game/run.py` advance the tick counter (for visual pacing) but are not the source of the demo-path knowledge. LOCATED_AT edges are also now seeded for all 5 NPCs; live gossip will work between co-located pairs in the interactive game.
**Why:** Demo reliability requires the same gossip chain on every run. Pre-seeding is the explicit contingency in ROADMAP.md and avoids randomness from propagation timing or ordering. The distorted summaries are authored to demonstrate the feature clearly.

---

## DEC-007: `--cached` mode skips scene delays
**Date:** 2026-05-22
**Context:** `make demo-run ARGS=--cached` exit criterion is < 10 seconds. With 23 s of `delay_before_ms` sleeps across all scenes, the cached run was timing out at ~33 s.
**Decision:** `DemoRunner.run()` skips delays when `self.cache.readonly` is True (i.e. `--cached` mode), matching the existing `--dry-run` behavior. Live mode (`make demo-run`) retains all delays for pacing during recording.
**Why:** `--cached` mode is used to verify the cache is warm before recording, not to actually drive the recorded video. The recording uses live mode where delays create natural pacing for the narrator.
