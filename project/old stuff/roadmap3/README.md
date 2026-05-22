# V3 Roadmap — NPC Engine

## Goal

Prove the engine is demo-ready in ~2 weeks: NPCs respond to live world state,
a playable demo game calls the engine over HTTP, and one fine-tuned adapter
demonstrates the path to per-engine quality. Built for a hackathon/mentoring
demo where mentors will evaluate both technical depth and visible behavior.

## Phase Index

| Phase | Name | Status | Effort (half-days) |
|-------|------|--------|-------------------|
| [0](phase0_audit/) | Audit & Diagnostic | **Ready to start** | 3.5 |
| [1](phase1_prompting_and_retrieval/) | Prompting & Retrieval Fixes + LLM Judge | Blocked on Phase 0 handoff | TBD at phase start |
| [2](phase2_demo_game/) | Demo Game Skeleton + Graph Visualization | Blocked on Phase 1 | TBD |
| [3](phase3_finetune_one_adapter/) | One QLoRA Adapter | Can start after Phase 1 | TBD |
| [4](phase4_polish_and_demo/) | Polish & Demo | Blocked on Phase 2 | TBD |

Phases 3 and 2 are partially parallel once Phase 1 closes: data collection for
Phase 3 fine-tuning can begin while Phase 2 demo-game coding is in progress.

## Exit Criteria (All Phases)

Six gates applied at the end of every phase, in priority order:

1. **[HARD]** All pre-existing tests pass.
2. **[HARD]** All new code has unit/integration tests; all new tests pass.
3. **[HARD]** E2E scenarios do not regress vs. the baseline recorded in Phase 0.
4. **[HARD]** Manual review of representative scenario outputs shows improvement
   or no regression. Phase owner signs off in the phase `handoff.md`.
5. **[HARD, Phase 1+; SOFT in Phase 0]** LLM-judge automated review of scenario
   outputs shows improvement or no regression.
6. **[SOFT]** Coverage on new code ≥ 78%. Explain in `handoff.md` if missed.

See [conventions.md](conventions.md) for the hard-vs-soft gate distinction and
the handoff template that captures gate status.

## Hard Constraints

These are fixed decisions. Do not propose alternatives anywhere in this roadmap.

- **Local LLM only.** Ollama on 12 GB VRAM / 64 GB system RAM. No hosted
  fallback, no cloud API calls.
- **Current base:** Mixtral 8x7B. Phase 1 candidate swap to Qwen2.5-7B-Instruct
  or Llama 3.1 8B Instruct. Decision made at end of Phase 0.
- **Demo game** lives in `demo_game/` (same repo). Calls engine via HTTP (FastAPI
  gateway). No in-process imports from `src/npc_engine/`.
- **Fine-tuning:** QLoRA adapters on a shared base model. No separate full
  fine-tunes per engine.

## Context and Pivot

The project completed V2 Roadmap through Phase 7 M/S (mood contagion, chapter
engine, narrative beats) and has 771 unit tests green. Phase 7 L (detective,
political simulation, social simulation, strategy/4X) is explicitly deferred
and is **out of scope for V3**.

V3 is a deliberate pivot from feature depth to demo quality. The reported
problem is that LLM outputs reflect world state only as surface fluff (e.g.,
"are the streets safe?" returns yes/no uncorrelated with an active war). Before
any prompt engineering or fine-tuning, V3 starts by diagnosing the actual cause
of this failure. See [lessons_from_prior_roadmaps.md](lessons_from_prior_roadmaps.md).

## Key Audit Findings (from V3 planning)

These findings shaped phase scope and are documented here for reference:

- `engines/dialogue/prompt_builder.py` contains a hardcoded `_SYSTEM_PROMPT`
  string (not a YAML file). It does reference `context.world.epoch` but uses
  "read this" language rather than "this is authoritative ground truth" framing.
  Cause (d) is a strong candidate until ruled out by Phase 0.
- `settings.LOG_LLM_PROMPTS` already exists as a flag in `DialogueLLMClient`.
  Phase 0 should verify it dumps the full assembled prompt; if not, add logging
  in `prompt_builder.py::build_dialogue_prompt`.
- `docs/RELEVANCE_WEIGHTS.md` lists an `explicit` weight that does not exist
  in `RelevanceWeights` model or any code. See [open_questions.md](open_questions.md).
- `e2e/helpers/llm_judge.py` exists and is used in `scenario_llm_judge.py`
  (`@pytest.mark.llm_eval`, opt-in) but is not wired into the default scenario
  harness as a pass/fail gate. Phase 1 wires it in.
- `engines/llm/llama_adapter.py` is a 14-line orphan. See open_questions.
