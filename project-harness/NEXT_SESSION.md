# Session Handoff

**Branch:** `munich-demo`
**Last completed:** S10.4 — Demo/gameplay loop: plant a lie → watch it mutate → correct it (local only)
**Next task:** S11.1 — Expand negative-eval suite into a comprehensive knowledge-guard battery
**Roadmap ref:** `project-harness/ROADMAP.md` → Phase 11, S11.1
**Test baseline:** 1318 passing (1311 engine unit + 7 rumor-trace unit) + 525 demo tests (14 new run-scenes)

---

## S11.1 — What to do

Build a comprehensive knowledge-guard eval battery that proves NPCs never hallucinate lore.

- Extend `evals/cases/` with new negative eval cases covering all archetypes (merchant, guard,
  innkeeper, fence, elder) targeting `KNOWS_ABOUT` violations, secret leakage, and lore invention.
- Each case: `keyword_none` matcher, `requires_world: demo`, specific player prompt designed to
  elicit the forbidden response (leading question, false premise, injection attempt).
- Minimum 5 new negative cases. Exit: `make eval` reports 0 hallucination failures.

---

## S10.4 — What was done (this session)

Completed the rumor-warfare demo arc (ACT 7 in `demo_game/run.py`).

- `demo_game/run_scenes.py` — added `SpreadRumorScene`, `RumorTraceDisplay`, `CorrectRumorScene`.
  Each is a leaf dataclass with a single `execute` method. `SpreadRumorScene` stores
  `runner.planted_event_id`; subsequent scenes read it so the whole arc shares one event_id.
- `demo_game/run.py` — added ACT 7 (8 scenes: plant → +2 ticks → trace → Mira believes →
  correct at Mira → Mira no longer knows → Henryk still believes). Updated outro.
- `demo_game/tests/test_run_scenes.py` — 14 new unit tests (happy path + dry_run + missing
  event_id + false/true corrected) for all three new scene classes.
- DEC-051 note updated (file still over 300 lines; existing exception stands).

---

## Open issues

None.

**Next ID to use: ISSUE-051.**

---

*Regenerated end of S10.4 session 2026-06-03.*
