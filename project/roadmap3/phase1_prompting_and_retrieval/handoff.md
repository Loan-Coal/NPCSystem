# Phase 1 Handoff

<!-- Fill in this document at the end of Phase 1. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass:
   [ ] YES  [ ] NO — details: ...

3. E2E baseline:
   [ ] NO REGRESSION  [ ] REGRESSION
   details: ...

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [asked "are the streets safe?" without prompting — NPC response was: "..."]

5. LLM judge (HARD gate from Phase 1):
   [ ] PASS  [ ] FAIL
   Verdict: [saved to e2e/baselines/llm_judge_phase1.json]

6. Coverage on new code:
   __% — [ ] PASS (≥78%)  [ ] SOFT FAIL — explanation: ...

---

## What Shipped

- [ ] Retrieval fix (cause a/b) — [describe what changed]
- [ ] System prompt rewrite (cause c/d) — prompt version: stage_b_v2.0
- [ ] Model swap — new model: [Qwen2.5-7B-Instruct / Llama 3.1 8B Instruct / skipped]
- [ ] LLM judge wired into make scenarios
- [ ] explicit weight resolution — [implemented / removed from docs]
- [ ] docs/PROMPT_DESIGN.md updated
- [ ] docs/RELEVANCE_WEIGHTS.md updated

---

## What Was Deferred

---

## What Phase 2 Needs to Know

[API routes that the demo game will rely on — confirm they work:]
- POST /v1/dialogue — [status]
- GET /v1/graph/nodes/{type} — [status]
- GET /v1/graph/edges/{type} — [status]
- POST /v1/clock/advance — [status]

[Any API surface gaps discovered during Phase 1 scenario runs:]

---

## What Phase 3 Needs to Know

**Recommended target engine for QLoRA adapter:**
[gossip / dialogue / other] — reason: [Phase 1 found prompting hit a ceiling
here because ...]

**Any training data signals from Phase 1:**
[e.g., the types of responses where the model consistently fails]

---

## Decisions Graduated to project/DECISIONS.md

---

## NEXT_SESSION.md Update

```
Phase 2 — Demo Game Skeleton + Graph Visualization

Entry criteria:
- Phase 1 handoff signed off: [YES/NO]
- make scenarios passes with LLM judge gate: [YES/NO]
- War scenario manual sign-off: [YES/NO]

Key context:
- Model in use: [model name]
- Prompt version: stage_b_v2.0
- LLM judge target: make scenarios-judge
- [other key context]
```
