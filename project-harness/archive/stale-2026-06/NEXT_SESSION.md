# Session Handoff

**Branch:** `munich-demo` (local only — 0 pushed; 6 commits ahead of origin)
**Last completed:** **Phase 13 — Clean-Slate Hygiene, COMPLETE.** S13.1 (committed Phases 11/12 + review),
S13.2 dropped (DEC-055, ISSUE-051 won't-fix), S13.3 (doc-drift sweep — fixed military `__init__` stub
docstring). Roadmap archived (Phases 0–13) and slimmed to Phase 14+.
**Test baseline:** 1326 unit + 525 demo passing. `make lint` GREEN (SEV-15 lint cleared — 38 errors fixed, uncommitted). `make type` RED — 256 errors, tracked as ISSUE-052 (SEV-14); ratchet-pinned via `.mypy_baseline`. Harness quality gates added — see `project-harness/HARNESS_GATES.md`.

---

## Next task — a sequencing decision, then build

Phases 14–16 are planned in `ROADMAP.md` (forward roadmap). **But** the 2026-06-03 audit returned
**BLOCK** (2 CRITICAL + 16 HIGH). Before starting Phase 14, decide:

> **Phase the `review-fixes/` remediation backlog vs. the feature phases.**

Recommended first moves if remediation goes first (critical path from `review-fixes/INDEX.md`):
`SEV-15` (green the lint/type gate) → `SEV-01` (prove the anti-hallucination moat — the headline claim) ‖
`SEV-02` (make `demo_game` a real standalone client). Fastest no-dep wins: SEV-09, SEV-13, SEV-16, SEV-17, SEV-07.

If features go first: **Phase 14** (proactive NPC dialogue) → 15 → 16; Phase 17 (SDKs) deferred.

## Where things live
- Forward roadmap: `project-harness/ROADMAP.md` (Phase 14 →).
- Full history (Phases 0–13): `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md`.
- Remediation backlog: `project-harness/REVIEW_FINDINGS.md` + `project-harness/review-fixes/` (INDEX.md = critical path).

## Open issues
- **ISSUE-052** (P2) — 256 mypy type errors; `make type` gate red (SEV-14, ratchet-pinned at `.mypy_baseline`).
- **ISSUE-053** (P2) — 57 grandfathered CLAUDE.md rule violations (`make check-rules` baseline / `scripts/rules_baseline.txt`).
- ISSUE-051 closed won't-fix (DEC-055). **Next ID to use: ISSUE-054.**

*Regenerated 2026-06-03 after Phase 13 close + roadmap restructure.*
