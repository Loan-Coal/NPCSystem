# NPCSystem — Engine Roadmap

**Status:** Phases 0–26 complete. This file is the **forward** roadmap only — it is
intentionally near-empty, ready for the next analysis run to populate.

## Archive (completed history)

| Range | Where |
|-------|-------|
| Phases 0–13 (+ engine audit, session log → S13.3) | `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 (proactive dialogue, retrieval evals, moderation, API exit contract, arch-debt drain, runtime correctness, P3 sweep, eval fixtures, temporal framing, voice polish) + full session log | `project-harness/archive/ROADMAP_phase14-26_2026-06-11.md` |
| 2026-06-01 Munich hackathon roadmap | `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md` |
| 2026-06-03 codebase review (BLOCK, 43 findings) — remediation backlog, now drained across Phases 20–26 | `project-harness/archive/review-2026-06-03/` |

---

## Next — to be filled by the next analysis run

> Run a codebase/expansion analysis and write the next phase block(s) here.
> Convention per phase: **Goal · Effort · Leverages · Constraint(s) · Notes · steps with Exit lines.**

_(empty — pending analysis)_

---

## Parked backlog (carried forward, not active)

These are the only known forward items. All are explicitly deprioritized or deferred —
none gate a feature phase. Promote into a "Next" phase block when picked up.

- [ ] **S17.9 / EXP-42** — Niche-engine expansions + demo integration (succession, clique,
  investigation, skill, military, treaty). Low commercial value; kept in code, no active dev.
- [ ] **S21.6** — File-size rule cluster, `demo_game/` scope (`client.py` 1524L, `seed.py` 1265L,
  `run.py`, `run_scenes.py`, `game_controller.py`, `ui/*`, `scenarios/*`). Demo code, high split
  risk (`make demo` breakage), low value; several already waived (DEC-029/032/034/049/074/075).
- [ ] **Phase X — Engine SDKs (Unity / Unreal)** — DEFERRED COMMERCIAL MILESTONE. Drop-in plugins
  wrapping the REST/WS API; highest commercial ROI but its own 8+ session milestone, sequenced after
  the OpenAPI contract is frozen.
  - [ ] **SX.1** OpenAPI contract freeze + versioned client spec.
  - [ ] **SX.2** Unity C# package (REST + WS, auth, models).
  - [ ] **SX.3** Unreal plugin (parity).
  - [ ] **SX.4** Sample integration scene per engine + docs.

---

## Engine Scope Decisions (reference)

| Engine | Status | Decision |
|--------|--------|----------|
| gossip, emotion, need, mood, routine, agenda | works, ticks | Showcased (Phases 1, 6) |
| quest_generation, quest (lifecycle) | works | Showcased (Phases 2–3) |
| memory_consolidation | works | Showcased (S6.3 — headline feature) |
| chapter, story_pacing | works | Promoted to gameplay (Phase 7) |
| faction_politics, oath, treaty | complete | Completed + showcased (S2.3, S2.4, S6.2) |
| military | implemented | Implemented S6.5 (ISSUE-031) |
| reputation + gossip | works | Productized (Phase 8 networked reputation) |
| secrets, leverage, pledges, beliefs | works | One consequence surfaced (S6.2) |
| succession, clique | works, niche | Graveyard — kept in code |
| investigation, skill | works, niche | Graveyard — out of scope |

---

## Testing Strategy (forward)

`make test` + `make test-demo` green before every merge. New work ships with tests.
`make check` (lint · check-rules · check-layers · check-docstrings · type · test-cov ≥80%) is the
canonical health gate. Green as of Phase 25 completion (1967 passed, 22 skipped, 85.70% coverage).
