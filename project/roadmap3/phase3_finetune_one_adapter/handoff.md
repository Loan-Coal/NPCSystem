# Phase 3 Handoff

<!-- Fill in this document at the end of Phase 3. Do not fill it speculatively. -->

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass (training/ unit tests):
   [ ] YES  [ ] NO — details: ...

3. E2E baseline:
   [ ] NO REGRESSION  [ ] REGRESSION
   details: [adapter must not regress on pre-existing E2E scenarios]

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [3 sample outputs from adapter-loaded model. Paste here or link
   to saved file. Describe the visible improvement over baseline.]

5. LLM judge (HARD gate):
   [ ] PASS  [ ] FAIL
   Verdict: [judge run on 3 sample outputs vs. Phase 1 baseline]

6. Coverage on training/ scripts:
   __% — [ ] PASS (≥78%)  [ ] SOFT FAIL — explanation: ...

---

## What Shipped

- [ ] training/ scaffold (data pipeline, training script)
- [ ] Raw synthetic data — N examples in training/data/raw/
- [ ] Curated dataset — N examples in training/data/curated/
- [ ] Trained adapter — saved to training/adapters/{engine}_v1/
- [ ] Adapter integrated in {engine} llm_config.yaml
- [ ] docs/ARCHITECTURE.md updated with fine-tuning pipeline section

---

## Adapter Summary

**Target engine:** ...
**Base model:** ...
**Training examples:** ...
**Key training observations:** ...
**Eval result vs. baseline:** [PASS / observed improvement described here]

---

## What Was Deferred

---

## What Phase 4 Needs to Know

**Adapter loading:** [describe how the adapter is loaded — merge vs. dynamic;
any known stability issues]

**Fallback:** [if the adapter is unstable, which feature flag or config
disables it and falls back to base model]

---

## Decisions Graduated to project/DECISIONS.md

[Training pipeline decisions — base model, LoRA rank, quantization settings,
data format — should be captured here for graduation.]

---

## NEXT_SESSION.md Update

```
Phase 4 — Polish & Demo

Entry criteria:
- Phase 2 handoff signed off: [YES/NO]
- Phase 3 handoff signed off: [YES/NO]

Key context:
- Adapter path: training/adapters/{engine}_v1/
- Adapter loading: [describe]
- Top 5 rough edges from Phase 2: [list]
- Backup recording location: demo_game/recordings/
```
