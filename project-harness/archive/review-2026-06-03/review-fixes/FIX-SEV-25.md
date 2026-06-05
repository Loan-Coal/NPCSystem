# FIX-SEV-25 — Harness honesty: update stale status docs

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** S
**Category:** harness · **Absorbs:** HARN-03, HARN-09, HARN-08

## Problem
`NEXT_SESSION.md` claims "Open issues: None" while ISSUE-052 (mypy) and ISSUE-053 (lint baseline) are logged. ROADMAP/NEXT_SESSION mark Phase 11 / S11.3 "complete" but all Phase 11 artifacts (`evals/summary.py`, `tests/unit/test_eval_summary.py`, 12 `case_*` yaml) are uncommitted (`??` in git status). ISSUE-041 sits under `## Open` referencing a nonexistent `seeds/worlds/seed_demo_world.py`.

## Current shape
- `NEXT_SESSION.md:38` "Open issues: None" (false — ISSUE-052 and ISSUE-053 exist)
- `ROADMAP.md` and `NEXT_SESSION.md` mark Phase 11 done without the artifacts committed
- `project-harness/ISSUES.md` ISSUE-041: still open, references nonexistent `seeds/worlds/seed_demo_world.py`

## Steps
1. In `NEXT_SESSION.md` "Open issues" section: replace "None" with a bullet referencing ISSUE-052 (mypy errors) and ISSUE-053 (lint baseline); add a note that Phase 11 artifacts are uncommitted (`git status: ??`).
2. In `project-harness/ISSUES.md`: mark ISSUE-041 `[FIXED]` with a note: `seeds/worlds/seed_demo_world.py` was superseded by `demo_game/seed.py`; Fixed 2026-06-04.
3. Do NOT commit Phase 11 artifacts here — just flag the gap. Do NOT create new issues; ISSUE-052 and ISSUE-053 already exist.

## Verification
- `grep "Open issues: None" NEXT_SESSION.md` → 0 matches
- `grep "ISSUE-041" project-harness/ISSUES.md` → shows `[FIXED]`
- `make check` still passes (no code changes)

## Blast radius
Docs/harness only.
