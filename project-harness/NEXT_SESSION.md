# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S6.6 — Final demo flow (5-minute script, all Phase 6 engine beats)
**Next task:** S7.1 — Player objective + win/lose condition
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 7, S7.1
**Test baseline:** 1223 passing (engine unit), 457 passing (demo suite)

---

## S7.1 — What to do

Player objective + win/lose condition. Suggested framing: "Earn the trust of two of
the three factions before the Iron Legion takes the market square."

Concretely:
- Define a win condition (e.g., player has STANDS_WITH standing ≥ 50 with 2/3 factions).
- Define a lose condition (e.g., iron_legion CONTROLS loc_market_square after tick N).
- Wire a `check_game_end()` call at the end of each clock advance tick.
- Show win/lose state in the WORLD panel or a new overlay.
- Exit: a session can be won or lost; state is shown; game stops accepting player actions.

---

## S6.6 — What was done (this session)

Final demo flow fully assembled.

- `demo_game/run_scenes.py` (NEW) — all Scene subclasses extracted here (12 scene types:
  NarratorCue, SeedCheck, EventFire, ClockTick, DialogueBeat, StreamingDialogueBeat,
  BribeScene, ReputationDisplay, EmotionDisplay, QuestDisplay, MemoryConsolidate, WorldFeed).
- `demo_game/run.py` — rewritten: 5-act SCENES list covering all Phase 6 beats
  (streaming dialogue, gossip, quest, bribe, emotion, memory, military engine, WORLD feed).
- `demo_game/seed.py` — added step 17: iron_legion faction + army_iron_legion (str=100) +
  army_city_guard_main (str=60) + OCCUPIES edges at loc_guard_barracks.
- `demo_game/client.py` — fixed put_world_state to write to `id="world_demo"` (was "world");
  resolves world state updates being silently lost since S0.4 (DEC-050).
- `docs/DEMO_SCRIPT.md` — complete 5-act, 5-minute script with narration script,
  API call sequence, sign-off checklist.
- `project-harness/DECISIONS.md` — DEC-049 (run.py split), DEC-050 (world_demo fix).

---

## Pre-recording checklist (before making takes)

- `make demo-seed` — re-seed to pick up armies + iron_legion faction
- `make demo-run ARGS=--dry-run` — confirm scene sequence prints cleanly
- `make demo-run` (live) — warm the cache
- `make demo-run ARGS=--cached` — confirm playback is error-free

---

## Open issues

None open.

**Next ID to use: ISSUE-050.**

---

*Regenerated end of S6.6 session 2026-06-03.*
