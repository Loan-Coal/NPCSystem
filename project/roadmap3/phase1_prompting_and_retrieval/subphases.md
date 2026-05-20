# Phase 1 Subphases (Skeleton)

<!-- This skeleton is fleshed out in P1.0 at the start of Phase 1, using the
     Phase 0 handoff. Do not add detail here speculatively. -->

## P1.0 — Flesh out subphases.md (0.5 half-day)

Read `phase0_audit/handoff.md`. Based on the diagnosis (cause a/b/c/d), expand
each skeleton subphase below into full-detail format (goal, steps, files,
expected output, exit check). Commit the expanded file before starting P1.1.

---

## P1.1 — Retrieval fix (if cause a or b)

Apply the fix identified by Phase 0 for WorldState retrieval or budget
enforcement. Add tests.

---

## P1.2 — System prompt rewrite (if cause c or d)

Rewrite `prompt_builder.py::_SYSTEM_PROMPT` with adversarial/authoritative
framing. Add few-shot examples for world-state-grounded responses. Version bump
to `stage_b_v2.0`. Add tests.

---

## P1.3 — Model swap

Pull Phase 1 target model (Qwen2.5-7B-Instruct or Llama 3.1 8B Instruct) via
Ollama. Update `dialogue/llm_config.yaml`. Run full test suite. Confirm no
regression on war and reputation scenarios.

---

## P1.4 — LLM judge wiring

Wire `e2e/helpers/llm_judge.py` into `make scenarios` as a hard gate. Update
war and reputation scenario files to include judge assertions. Add a separate
`make scenarios-judge` target for the inner dev loop.

---

## P1.5 — Explicit weight resolution

Based on Q3 decision: either implement `explicit` field in `RelevanceWeights`
and `context_scoring.py`, or remove it from `docs/RELEVANCE_WEIGHTS.md`.
Document built-in weight profiles in the doc.

---

## P1.6 — Docs update

Evolve `docs/PROMPT_DESIGN.md` with new prompt version and framing rationale.
Update `docs/RELEVANCE_WEIGHTS.md` with drift fixes and profile documentation.

---

## P1.7 — Handoff

Fill in `phase1_prompting_and_retrieval/handoff.md`. Replace
`project/NEXT_SESSION.md`.
