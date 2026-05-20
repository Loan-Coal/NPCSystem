# Phase 4 — Polish & Demo

## Goal

Tighten the obvious rough edges from earlier phases, integrate Phase 3's adapter
into the demo game, rehearse the scripted demo scenario, and record a backup
video. The phase ends when the demo is reliably reproducible in 5 minutes and
has been rehearsed at least twice.

## Why This Phase Exists

Phases 1–3 produce correct, quality-improved behavior. Phase 4 produces a
presentation. A demo that requires 10 minutes of setup, crashes once in five
runs, or has an illegible graph panel will undermine confidence in technically
solid work. This phase protects that investment.

## Scope (In)

- **Integration:** Ensure Phase 3 adapter is loaded in the demo game's default
  configuration. Verify the demo game uses the correct `llm_config.yaml`.
- **Demo script:** Write a step-by-step demo script (2–3 minutes) that a mentor
  can follow. Script includes: start command, what to click, what to say to
  NPCs, what to look for in the graph panel.
- **Rehearsal:** Run through the scripted demo at least twice. Fix any crashes,
  slow responses, or illegible UI. Document each rehearsal result in `handoff.md`.
- **Backup recording:** Record a screen capture of a successful demo run.
  Save to `demo_game/recordings/`. This is the backup if the live demo fails.
- **Setup time:** `make demo` should produce a running demo in ≤5 minutes from
  a cold start (Docker pull + Ollama model load excluded).
- **Cleanup:** Identify and fix the most visible rough edges from Phases 1–3
  (e.g., illegible graph labels, slow gossip panel, NPC names in wrong places).
  Fix ≤5 polish items; do not scope-creep into new features.
- Evolve `docs/DEMO.md` to the final demo script and setup instructions.

## Scope (Out)

- **No new features.** Phase 4 polishes existing features, does not add new
  ones.
- **No new adapters.** Phase 3 shipped one; Phase 4 integrates it.
- **No graph schema changes.** Any node/edge changes would require re-seeding
  the demo world and risk stability.
- **No test additions** beyond any tests that naturally arise from fixing
  crashes or integration bugs. Phase 4 is not a testing phase.

## Entry Criteria

- Phase 2 `handoff.md` is signed off (demo game is playable).
- Phase 3 `handoff.md` is signed off (adapter exists and is evaluated).
- `make scenarios` passes with LLM judge gate on all baseline scenarios.
- Phase owner has tried the demo game cold and can list the top 5 rough edges.

## Exit Criteria

1. **[HARD]** All existing tests pass.
2. **[HARD]** No new untested code introduced. If a crash fix requires a code
   change, add a regression test.
3. **[HARD]** `make scenarios` passes (including LLM judge gate).
4. **[HARD]** Demo script completed twice without crashes. Both rehearsal logs
   in `handoff.md`.
5. **[HARD]** Backup recording exists in `demo_game/recordings/`.
6. **[SOFT]** Setup time ≤5 minutes (excluding Docker/model pull).

## Affected Modules

- `demo_game/` — integration of Phase 3 adapter, UI polish, demo script
- `demo_game/recordings/` — new directory for backup video
- `docs/DEMO.md` — final demo script and setup

## Docs to Evolve

- `docs/DEMO.md` — replace with final demo script. Include: prerequisite setup,
  `make demo` command, scripted walkthrough (what to do and what to observe),
  troubleshooting tips, and where the backup recording is.

## Demo Impact

This phase produces the demo itself. After Phase 4: the demo is a 2–3 minute
live walkthrough that shows gossip propagation in a graph panel, NPC dialogue
grounded in world state, and a fine-tuned adapter delivering improved response
quality. Mentors can try it themselves. The backup recording is available if
anything goes wrong.

## Risks

1. **Phase 3 adapter integration takes longer than expected** — mitigation: if
   adapter loading is complex, feature-flag it so the demo can fall back to the
   base model for reliability.
2. **Demo crashes on mentor hardware (different from dev machine)** — mitigation:
   test the backup recording workflow early; ensure it runs without Ollama
   (pre-rendered output).
3. **Graph panel is too slow or too busy** — mitigation: show a curated subgraph
   (5–10 nodes) during the scripted demo, not the full graph. Add a "focus NPC"
   button that filters to the selected NPC's neighborhood.

## Estimated Effort

TBD — fleshed out in P4.0 at phase start.

Rough range: 3–5 half-days (integration 1, rehearsal 1, polish 1–2, recording 0.5).

If I have to cut: cut the "nice to have" polish items (graph animation, fancy
labels). Do not cut the rehearsal or the backup recording — those are the
insurance policy.
