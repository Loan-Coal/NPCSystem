# Phase 4 Subphases (Skeleton)

<!-- Skeleton only. Fleshed out in P4.0 at the start of Phase 4,
     after Phase 2 and Phase 3 handoffs are both available. -->

## P4.0 — Flesh out subphases.md (0.5 half-day)

Read Phase 2 and Phase 3 handoffs. List the top 5 rough edges identified in
Phase 2 rehearsal and Phase 3 integration. Expand skeleton below. Commit
before starting P4.1.

---

## P4.1 — Phase 3 adapter integration into demo game

Load Phase 3 adapter in demo game's engine config. Verify demo game works
correctly with adapter. Feature-flag fallback to base model if adapter
loading is unstable.

---

## P4.2 — Top 5 polish items

Fix the top 5 rough edges from Phase 2/3. Each fix requires a brief entry in
`decisions.md` noting what was changed and why. Regression test for any fix
that touches engine code.

---

## P4.3 — Demo script

Write step-by-step demo script: start command, what to click, what to say,
what to observe in graph panel, timing. Target: 2–3 minutes end-to-end.

---

## P4.4 — Rehearsal 1

Run through the demo script cold. Document result in `handoff.md`. Fix any
blocking issues. Repeat rehearsal until clean run.

---

## P4.5 — Backup recording

Record screen capture of a clean demo run. Save to `demo_game/recordings/`.
Verify the recording is watchable on a different machine.

---

## P4.6 — Final handoff

Update `docs/DEMO.md` with the final demo script. Fill in
`phase4_polish_and_demo/handoff.md`. Project is demo-ready.
