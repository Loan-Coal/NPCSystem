# Lessons from Prior Roadmaps

Sources: `project/old stuff/ROADMAP.md` (V1) and `project/old stuff/ROADMAP_V2.md` (V2).

---

## What V1 Planned

V1 was a high-level 5-phase plan: Foundations → First vertical slice (factions)
→ Routine engine → World depth (memories, beliefs, goals, secrets) → Demo polish.
LLM-as-judge, per-engine fine-tuning, and "does world state actually drive
outputs?" were all listed as **backlog** items — acknowledged but not gated.

## What V1 Actually Shipped

V1 shipped all five phases. The gossip visualizer was part of Phase 5 demo
polish. The backlog items (LLM judge, fine-tuning, world-state quality) were
never touched. The demo was a 90-second video scenario (`make demo-video`) that
demonstrated propagation and dialogue mechanically, but LLM response quality
was never measured.

## What V2 Planned

V2 was an ambitious 68-item plan across 8 phases: structural fixes → engine
config baseline → retrieval foundation → graph primitives → RPG depth → retrieval
quality lift → genre-specific modules → scale and retrieval unification. V2 had
detailed verification checklists with latency targets and test gates per phase.

## What V2 Actually Shipped

V2 shipped through Phase 7 M/S (mood contagion, chapter engine, narrative beats)
with 771 tests green. All 68 items in Phases 1–6 were completed. Phase 7 L
(detective, political simulation, social simulation, strategy/4X) was deferred.
Phase 8 (scale/retrieval unification) was never started.

## Where V1 and V2 Diverged from Intent

1. **LLM quality was never gated.** Both roadmaps assumed retrieval correctness
   and prompt structure were "good enough" without ever measuring them. The
   demo worked mechanically, but the specific reported failure — "streets safe?"
   returning an answer not correlated with active war state — was never caught
   because no automated or manual gate asked "does the model's output reflect
   the world state in the prompt?"

2. **Infrastructure grew faster than demo story.** V2 added sophisticated
   retrieval (graph-RAG, 3-tier cache, weight profiles, compression) and a
   rich graph schema, but the demo scenario itself was not updated to exercise
   this depth. The mentor demo risk is that the infrastructure looks impressive
   in code review but doesn't visibly change NPC behavior.

3. **LLM judge was promoted to "later."** It appeared in V1 backlog, appeared
   in V2 Phase 8, and still has not been wired into the default scenario harness.
   `e2e/helpers/llm_judge.py` exists and works; the missing piece is making it
   a pass/fail gate in `make scenarios`, not writing it from scratch.

4. **Model selection was never revisited.** Mixtral 8x7B was the original choice
   and has never been benchmarked against smaller, faster 7–8B models. For a
   12 GB VRAM machine this may be leaving latency and quality on the table.

## What V3 Does Differently

- **Diagnostic first.** Phase 0 verifies whether world state reaches the model
  at all before attempting any fix. This is the question V1 and V2 never asked.
- **LLM judge as hard gate from Phase 1.** Not backlog, not opt-in.
- **Demo game as explicit phase.** Phase 2 exists specifically to make the
  quality improvements visible to a mentor who isn't reading the code.
- **Effort is half-day units, not aspirational.** Skeleton subphases for Phases
  1–4 are fleshed out at the start of each phase, with the prior phase's
  findings in hand — not speculatively at roadmap-write time.
