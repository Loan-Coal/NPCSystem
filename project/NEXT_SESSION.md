# Next Session Instructions

## Phase 4 complete. Phase 5 — Demo polish next.

Run tests before touching any code:

```bash
pytest tests/ -q
```

## Phase 4 completion status (committed 2026-05-13)

- 4.1: Faction politics engine (deterministic rules + decay).
- 4.2: Quest generation engine (slot-filling, LLM flavor, graph validation).
- 4.3: Story pacing engine (WorldState max_event_severity + quest_generation_rate).
- 4.4: Economy engine (PricingEngine, TradeEngine, GET /economy/price, POST /economy/trade).
- 694 unit tests green.

---

## Step 0 — Update stale docs first (before any code)

1. `project/IMPLEMENTATION_TRACKER.md` — mark Feature 5.1 as IN_PROGRESS with today's date.
2. `project/STATUS.md` — update Phase 5 row: 5.1 IN_PROGRESS.

---

## Feature 5.1 — The 90-second video scenario

Read `project/ROADMAP.md` lines 723+ first (the authoritative spec).

**Goal:** A single self-contained e2e scenario that boots from clean state, seeds the world,
and runs the full demo loop — suitable for a 90-second video voiceover.

**What to build:**
- A self-contained e2e scenario in `e2e/scenarios/scenario_demo_video.py` that:
  1. Creates a tavern location.
  2. Creates two NPCs (Mira the innkeeper, Gareth the wanderer) with factions.
  3. Seeds a rumor event (plague sighting) propagated via gossip.
  4. Player asks each NPC what they know — dialogue endpoints return distorted rumor.
  5. Outputs a clean text transcript suitable for video voiceover.
- The scenario should pass with `--scenarios-only` flag when the stack is running.

**Definition of done:**
- Single scenario file, no external dependencies beyond the running HTTP API.
- Transcript printed to stdout in a human-readable narrative format.
- All seeded data cleaned up in the `finally` block.
- Passes end-to-end with a live stack.

---

## Open issues to be aware of (do NOT fix unless blocking)

- ISSUE-013: `how_long_ago` bucket gap 7–27 days (P3)
- ISSUE-005: `adjust_reputation_for_event` not wired (P3)
- ISSUE-006: `Character.faction` string field not migrated (P3)
- ISSUE-004: `edge_updater.py` mypy warning (P3)
- ISSUE-011: `.env` uses Docker DNS (P3)
