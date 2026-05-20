# Phase 0 — Audit & Diagnostic

## Goal

Determine the actual cause of the context-not-respected failure before any code
is changed. Capture a reproducible baseline of scenario outputs (manual + LLM
judge). Audit `docs/RELEVANCE_WEIGHTS.md` against `retrieval/context_scoring.py`
for drift. Produce a signed handoff that tells Phase 1 exactly what to fix.

## Why This Phase Exists

V1 and V2 both shipped without ever measuring whether LLM outputs reflected
world state. Phase 0 exists because fixing the wrong layer wastes the most
constrained resource (model context budget). The four possible failure modes
require different fixes:

| Cause | Fix lives in |
|-------|-------------|
| (a) World state fact not retrieved at all | `context_builder.py` retrieval queries |
| (b) Fact retrieved but ranked low / compressed out | `context_scoring.py` weights or Tier 0 logic |
| (c) Fact in prompt, model treats it as flavor | Prompt structure (few-shot, framing) |
| (d) Prompt doesn't signal world state overrides model defaults | System prompt adversarial framing |

Phase 1 scope branches on which cause (or combination) Phase 0 identifies.

## Scope (In)

- Run existing test suite and confirm it passes (hard gate before anything else).
- Enable prompt logging and capture the full assembled prompt for the war scenario.
- Trace world state through the retrieval pipeline: is it retrieved? budgeted
  out? present in the final prompt?
- Audit `docs/RELEVANCE_WEIGHTS.md` vs `context_scoring.py` and `context_config_models.py`.
- Record baseline scenario outputs (war, reputation) to `e2e/baselines/`.
- Run LLM judge (soft gate) against baseline outputs and record verdict.
- Benchmark Mixtral 8x7B latency to inform Phase 1 model swap decision.
- Write findings in `handoff.md`. Scope Phase 1 based on findings.

## Scope (Out)

- **No prompt changes.** Do not touch `prompt_builder.py`'s `_SYSTEM_PROMPT`.
- **No retrieval changes.** Do not edit `context_scoring.py` or `context_builder.py`
  except to add logging (two lines maximum).
- **No model swap.** Default is Phase 1 unless Mixtral is unusably slow.
- **No new tests.** Phase 0 runs existing tests, does not write new ones.
- **No new scenarios.** Use existing `scenario_war_breaks_out.py` and
  `scenario_dialogue_reputation.py`.
- **No doc edits** outside `project/roadmap3/`. Document findings here; edits
  happen in Phase 1.
- **No Phase 7 L engine work** of any kind.

## Entry Criteria

- `project/roadmap3/` exists with this README (i.e., the roadmap has been authored).
- Answers to at minimum Q1 and Q2 from `open_questions.md` are known (can be
  resolved in P0.1 with a quick config check).
- Docker Compose stack can be started locally (`make dev` or equivalent).

## Exit Criteria

1. **[HARD]** `make test` passes with zero failures (771 tests green or more).
2. **[HARD]** No new tests were written in Phase 0 — gate 2 is N/A; confirm in handoff.
3. **[HARD]** War scenario baseline saved to `e2e/baselines/` and verified readable.
4. **[HARD]** `handoff.md` contains a written diagnosis (a/b/c/d) with supporting
   evidence (log excerpts or reasoning). Phase owner signs off.
5. **[SOFT]** LLM judge verdict recorded against baseline outputs. Failure or
   "cannot run" is acceptable — record and explain.
6. **[SOFT]** Coverage gate is N/A (no new code). Note in handoff.

## Affected Modules

- **Read only (diagnostic):**
  - `src/npc_engine/engines/dialogue/prompt_builder.py` — inspect system prompt
  - `src/npc_engine/engines/dialogue/llm_client.py` — check LOG_LLM_PROMPTS behavior
  - `src/npc_engine/retrieval/context_builder.py` — trace world state retrieval
  - `src/npc_engine/retrieval/context_scoring.py` — audit weight implementation
  - `src/npc_engine/schema/context_config_models.py` — audit RelevanceWeights model
  - `docs/RELEVANCE_WEIGHTS.md` — compare against code
  - `e2e/scenarios/scenario_war_breaks_out.py` — run for baseline
  - `e2e/scenarios/scenario_dialogue_reputation.py` — run for secondary baseline
  - `e2e/helpers/llm_judge.py` — run manually for soft gate
- **Write (new files only, no edits to existing):**
  - `e2e/baselines/war_outbreak_baseline.json` — scenario output capture
  - `e2e/baselines/reputation_baseline.json` — secondary baseline
  - `e2e/baselines/llm_judge_phase0.json` — LLM judge verdict
  - `project/roadmap3/phase0_audit/decisions.md` — any decisions made
  - `project/roadmap3/phase0_audit/handoff.md` — phase sign-off
- **Possible minimal write (only if Q2 is "neither logged"):**
  - `src/npc_engine/engines/dialogue/prompt_builder.py` — add 1 DEBUG log line
  - `src/npc_engine/retrieval/context_builder.py` — add 1–2 DEBUG log lines

## Docs to Evolve

None in Phase 0. Findings logged in `handoff.md`; edits to `docs/RELEVANCE_WEIGHTS.md`
and `docs/PROMPT_DESIGN.md` happen in Phase 1.

## Demo Impact

Phase 0 does not change visible behavior. Its output is a diagnosis and a
baseline. Without it, Phase 1 risks fixing the wrong thing.

## Risks

1. **LOG_LLM_PROMPTS does not capture full prompt** — mitigation: read
   `llm_client.py` first; add 1 DEBUG log line in `prompt_builder.py` if needed.
   Cost: 1–2 lines, no tests needed for a DEBUG log.
2. **Docker Compose / Ollama not available** — mitigation: Phase 0 can proceed
   with static code analysis only for the retrieval audit (subphases P0.2–P0.4).
   Baseline capture (P0.1, P0.5) requires a running stack. Flag in handoff if
   baselines could not be captured.
3. **War scenario has non-deterministic LLM output** — mitigation: run the
   scenario 3 times; capture all three outputs; note variance in handoff.
4. **Mixtral 8x7B load time >5 min** — mitigation: note in handoff; Phase 1
   model swap is the fix; do not try to fix it in Phase 0.

## Estimated Effort

3.5 half-days total:

| Subphase | Half-days |
|----------|-----------|
| P0.1 — Env check & baseline capture | 0.5 |
| P0.2 — Prompt logging & inspection | 0.5 |
| P0.3 — Retrieval diagnostic | 1.0 |
| P0.4 — Relevance weight audit | 0.5 |
| P0.5 — Model swap benchmarking | 0.5 |
| P0.6 — LLM judge baseline + handoff | 0.5 |

If I have to cut: cut P0.5 (model swap benchmarking) — the swap decision can
be made from published benchmarks and the latency observation during P0.1/P0.3
runs. Do not cut P0.3 or P0.4; those are the core diagnostic.
