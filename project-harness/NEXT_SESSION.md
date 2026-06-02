# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S4.4 — [Bribe] wired (faction standing + gold deduction via background worker)
**Next task:** S5.1 — Idempotent seed = no-clobber (seeding must not reset player-mutated state)
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 5, S5.1
**Test baseline:** 1200 passing, 0 failed (full suite) | 312 passing (demo suite)

---

## S5.1 — What to do

Make the demo seed idempotent: seeding a world that already exists must not overwrite
player-mutated state (standing, gold, inventory, completed quests).

Exit: bribe Lira → restart → standing still elevated.

Suggested approach:
- Before upserting a Character node check if it already exists (`GET /v1/graph/nodes/Character/{id}`).
- Skip (or merge-only) the standing/gold fields on Character nodes if the world already has a player node.
- Add an integration test: seed twice, verify player-mutated gold persists.

---

## S4.4 — What was done (this session)

- Added `BRIBE_GOLD_COST = 20` and `BRIBE_STANDING_GAIN = 15` to `constants.py`.
- Added `bribe_worker` to `action_workers.py`: reads player gold + current standing,
  validates sufficient funds, increments standing (capped at 100), deducts gold.
- Enabled `[Bribe]` button in `actions_panel.py` (index 4); added `set_bribe_callback`.
- Added `set_bribe_callback` delegate to `right_panel.py`.
- Added `spawn_bribe` + `poll_bribe_queue` + `_bribe_q` to `game_controller.py`.
- Wired `set_bribe_callback` + `poll_bribe_queue()` in `game_window.py`.
- 5 new tests (`test_action_workers.py`): happy path, standing cap, insufficient gold,
  zero starting standing, API failure.
- Test baseline: 312 passing (demo suite), 1200 passing (full suite).

---

## Open issues

| Issue | Sev | Targeted by |
|---|---|---|
| ISSUE-031 | P3 | Phase 6 |

**Next ID to use: ISSUE-050.**

---

*Regenerated end of S4.4 session 2026-06-02.*
