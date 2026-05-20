# Phase 0 Handoff

<!-- Fill in this document at the end of Phase 0. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass:
   [ ] N/A (no new code written in Phase 0) — confirm: ...

3. E2E baseline:
   [ ] N/A — Phase 0 *produces* the baseline; regression gate applies from Phase 1.
   Baseline files saved: ...

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [describe what scenario outputs were reviewed and what they showed]

5. LLM judge (SOFT gate in Phase 0):
   [ ] PASS  [ ] FAIL  [ ] COULD NOT RUN — reason: ...
   Verdict saved to: e2e/baselines/llm_judge_phase0.json

6. Coverage:
   [ ] N/A (no new code) — confirm: ...

---

## Primary Diagnosis

**Cause:** (a / b / c / d) — [fill in]

**Evidence:**
[Paste or summarize the key finding from P0.3. For example:
- "The CONTEXT block in the prompt contained epoch='war', ruling out cause (a)."
- "WorldState is Tier 0 and was not compressed out, ruling out cause (b)."
- "The system prompt says 'read context.world.epoch' but does not declare world
  state as authoritative — strong evidence for cause (d)."
]

**Secondary cause (if applicable):** ...

---

## What Shipped

- [ ] Baseline files saved to `e2e/baselines/`
- [ ] Diagnosis written in `decisions.md`
- [ ] Relevance weight audit written in `decisions.md`
- [ ] Model swap recommendation written in `decisions.md`
- [ ] LLM judge baseline recorded

---

## What Was Deferred

<!-- List items that surfaced during Phase 0 but were not acted on.
     Create ISSUES.md entries for each. -->

---

## What Phase 1 Needs to Know

<!-- This section is the most important part of the handoff.
     Phase 1 subphase planning starts by reading this section.
     Be specific: name the file, the function, the weight, the Cypher query. -->

**If cause is (a) or (b) — retrieval fixes needed:**
- ...

**If cause is (c) or (d) — prompt-only fixes:**
- ...

**Model swap target:** [Qwen2.5-7B-Instruct / Llama 3.1 8B Instruct] — latency
observed: [N]s median, [N]s p95. Swap urgency: [high / low].

**Relevance weight `explicit`:** [implement in Phase 1 / remove from docs] —
reasoning: ...

---

## Decisions Graduated to project/DECISIONS.md

<!-- List entries from phase0_audit/decisions.md that are cross-phase and
     should be copied by the human into project/DECISIONS.md. -->

---

## NEXT_SESSION.md Update

<!-- Paste the full replacement text for project/NEXT_SESSION.md here.
     Keep it to <10 lines: what phase is next, entry criteria status,
     and 3–5 bullets needed to start cold. -->

```
Phase 1 — Prompting & Retrieval Fixes + LLM Judge

Entry criteria:
- Phase 0 handoff signed off: [YES/NO]
- Diagnosis confirmed: cause ([a/b/c/d])
- Baseline files in e2e/baselines/: [YES/NO]

Key context:
- [bullet 1]
- [bullet 2]
- [bullet 3]
```
