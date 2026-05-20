# Phase 1 — Prompting & Retrieval Fixes + LLM Judge Integration

## Goal

Apply the fixes identified by Phase 0's diagnosis to make NPC responses
demonstrably reflect live world state. Wire the existing LLM judge into the
scenario harness as an automated pass/fail gate so that quality regressions are
caught automatically from this phase forward. Optionally swap the base model to
the Phase 1 target (Qwen2.5-7B-Instruct or Llama 3.1 8B Instruct).

## Why This Phase Exists

Phase 0 identified the root cause. Phase 1 fixes it. Without this phase, the
demo game (Phase 2) would show NPCs that appear to have rich graph context but
respond generically — exactly the reported failure. The LLM judge gate is wired
here (not in Phase 2) because every subsequent phase needs automated quality
regression detection.

## Scope (In)

The exact scope is determined by Phase 0's diagnosis. Use the Phase 0 handoff
to fill in the branching sections below at phase start:

**If cause (a) — WorldState not retrieved:**
- Fix the Cypher query or retrieval path in `context_builder.py` that fetches
  WorldState or active war conditions.
- Add integration tests covering the fixed retrieval path.

**If cause (b) — retrieved but budgeted/compressed out:**
- Fix WorldState Tier assignment in `context_builder.py` (ensure Tier 0).
- Or adjust compression thresholds so WorldState is never dropped.
- Add unit tests for the budget enforcement logic.

**If cause (c) or (d) — prompt doesn't enforce world state authority:**
- Rewrite `prompt_builder.py::_SYSTEM_PROMPT` to use adversarial/authoritative
  framing for world state facts.
- Add few-shot examples demonstrating correct world-state-grounded responses.
- Add structured world-state block above event list with AUTHORITY marker.

**All paths include:**
- Wire `e2e/helpers/llm_judge.py` into `make scenarios` as a hard gate.
  The judge should produce a pass/fail verdict for each scenario run and fail
  `make scenarios` if verdict is FAIL.
- Update `e2e/scenarios/scenario_war_breaks_out.py` and
  `e2e/scenarios/scenario_dialogue_reputation.py` to include LLM judge assertions.
- Model swap: pull Qwen2.5-7B-Instruct or Llama 3.1 8B Instruct via Ollama,
  update `dialogue/llm_config.yaml`, run full test suite, confirm no regression.
- Evolve `docs/PROMPT_DESIGN.md` to reflect new system prompt version and
  any retrieval changes.
- Resolve `explicit` weight drift (implement or remove from docs per Q3 decision).

## Scope (Out)

- **No demo game.** That is Phase 2.
- **No QLoRA training.** That is Phase 3.
- **No new graph nodes or edges.** Phase 7 L work is deferred.
- **No changes to gossip, quest, or memory consolidation prompts.** Phase 1
  focuses on the dialogue engine only. Other engines may benefit from the same
  fixes but wait for Phase 3 or later.
- **No UI or visualization.** Phase 2.

## Entry Criteria

- Phase 0 `handoff.md` is signed off.
- Diagnosis (cause a/b/c/d) is written and agreed.
- Baseline files exist in `e2e/baselines/`.
- LLM judge baseline verdict exists in `e2e/baselines/llm_judge_phase0.json`.
- `project/NEXT_SESSION.md` has been replaced with Phase 0's handoff note.

## Exit Criteria

1. **[HARD]** All pre-Phase-1 tests pass.
2. **[HARD]** New tests for retrieval fix / prompt change pass. Coverage ≥ 78%
   on changed files.
3. **[HARD]** `scenario_war_breaks_out.py` and `scenario_dialogue_reputation.py`
   pass with no latency regression vs. Phase 0 baselines.
4. **[HARD]** Manual review: run the war scenario, ask "are the streets safe?"
   — the NPC response should reflect war state without being asked directly.
   Phase owner documents observed response in `handoff.md`.
5. **[HARD]** LLM judge integrated into `make scenarios`. Running `make scenarios`
   on the war scenario produces a PASS verdict. No FAIL on either baseline scenario.
6. **[SOFT]** Coverage ≥ 78% on all new files. Explain in `handoff.md` if missed.

## Affected Modules

Based on Phase 0 diagnosis — specific paths confirmed at phase start:

- `src/npc_engine/engines/dialogue/prompt_builder.py` — system prompt rewrite
- `src/npc_engine/retrieval/context_builder.py` — if cause (a) or (b)
- `src/npc_engine/retrieval/context_scoring.py` — if cause (b) or explicit weight
- `src/npc_engine/schema/context_config_models.py` — if explicit weight added
- `src/npc_engine/engines/llm/llm_config.yaml` — model swap
- `e2e/scenarios/scenario_war_breaks_out.py` — LLM judge assertion
- `e2e/scenarios/scenario_dialogue_reputation.py` — LLM judge assertion
- `e2e/scenarios/conftest.py` — LLM judge wiring for all scenarios
- `e2e/helpers/llm_judge.py` — possibly extend for new verdict format
- `tests/unit/` — new tests for retrieval/prompt changes
- `docs/PROMPT_DESIGN.md` — evolve with new prompt version and framing rationale
- `docs/RELEVANCE_WEIGHTS.md` — fix `explicit` drift

## Docs to Evolve

- `docs/PROMPT_DESIGN.md` — update system prompt version (stage_b_v1.0 →
  stage_b_v2.0), document adversarial framing rationale, update few-shot examples.
- `docs/RELEVANCE_WEIGHTS.md` — fix `explicit` weight drift; document all four
  built-in profiles.

## Demo Impact

After Phase 1: asking any NPC "are the roads safe?" during an active war
returns an answer that reflects the war (tense refusal, warning, or explicit
mention of conflict). The LLM judge confirms this programmatically. Mentors
evaluating the system can run `make scenarios` and see a PASS verdict.

## Risks

1. **Model swap degrades quality on other scenarios** — mitigation: run full
   E2E suite after swap; roll back if any baseline scenario regresses.
2. **Adversarial framing breaks tone for non-war states** — mitigation: include
   a "peace" scenario test alongside the war test to catch over-correction.
3. **LLM judge is slow** (second LLM call per scenario) — mitigation: run judge
   in a separate `make scenarios-judge` target by default; include in `make ci`
   but not in the inner dev loop `make scenarios`.
4. **Cause is (a) and the Cypher fix is complex** — mitigation: if the WorldState
   singleton is not linked to the active war Event, the fix is a new Cypher
   relationship, not a prompt change. Budget an extra 0.5 half-day.

## Estimated Effort

TBD — fleshed out in P1.0 at phase start using Phase 0 handoff.

Rough range: 4–7 half-days depending on cause complexity.

If I have to cut: cut the model swap (run on Mixtral, note in handoff, defer
swap to Phase 2 or later). Do not cut the LLM judge wiring — it is required
for Phase 2 regression detection.
