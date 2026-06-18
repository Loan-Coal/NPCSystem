# Phase 3 Subphases (Skeleton)

<!-- Skeleton only. Fleshed out in P3.0 at the start of Phase 3,
     using the Phase 1 handoff (which identifies the target engine).
     Phase 3 can begin after Phase 1 and can run partially in parallel
     with Phase 2. -->

## P3.0 — Flesh out subphases.md (0.5 half-day)

Read `phase1_prompting_and_retrieval/handoff.md` section "What Phase 3 needs
to know." Confirm target engine. Decide data generation approach (hosted API
choice). Expand skeleton below. Commit before starting P3.1.

---

## P3.1 — Training infrastructure

`training/` directory scaffold. QLoRA training script using `transformers` +
`peft` + `bitsandbytes`. Dry-run test (1 step, tiny batch). Confirm training
runs on available hardware.

---

## P3.2 — Data collection and generation

Design instruction-tuning prompt format for target engine. Generate synthetic
examples via hosted LLM API (diversity seeds). Save raw examples to
`training/data/raw/`.

---

## P3.3 — Hand curation

Filter raw examples to high-quality set. Target: 500–1000 curated examples.
Save to `training/data/curated/`. Write a curation checklist in `decisions.md`.

---

## P3.4 — QLoRA training run

Train on curated dataset. Log loss curve. Save adapter weights to
`training/adapters/{engine_name}_v1/`.

---

## P3.5 — Eval and integration

Run E2E scenarios against adapter-loaded model. LLM judge comparison vs. Phase 1
baseline. If pass: add `adapter_path` to target engine `llm_config.yaml`.

---

## P3.6 — Handoff

Fill in `phase3_finetune_one_adapter/handoff.md`. Graduate training pipeline
decisions to `project/DECISIONS.md`. Replace `project/NEXT_SESSION.md`.
