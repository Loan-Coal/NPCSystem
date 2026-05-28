# Phase 3 — One QLoRA Adapter

## Goal

Build the fine-tuning pipeline (data collection → synthetic data generation →
hand-curation → QLoRA training → eval → adapter integration) and ship one
trained adapter for the engine where Phase 1 prompting hit a ceiling. Frame the
result to mentors as "LoRA infrastructure built, one adapter as proof, scales
to per-engine specialization."

## Why This Phase Exists

Phase 1 fixes the prompt framing; it does not improve the model's intrinsic
ability to generate contextually grounded, stylistically rich NPC responses.
QLoRA training on domain-specific data is the mechanism that shifts the model's
defaults toward the project's style. One adapter proves the pipeline works and
provides a visible quality lift for the demo. Subsequent engines follow the same
pattern without rebuilding the infrastructure.

## Scope (In)

- **Select the target engine.** Default candidate: gossip mutation engine —
  the "distortion chain" behavior (omission, exaggeration, role_swap,
  timeline_shift) is currently template-based; an LLM adapter trained on
  realistic distortion examples would produce more convincing mutations. If
  Phase 1 shows dialogue is the bigger gap, swap the target.
- **Data pipeline:**
  - Use a larger, hosted LLM (via API, one-time cost for data generation, not
    inference) to generate diversity-seeded synthetic examples.
  - Hand-curate: filter to N high-quality examples (target: 500–1000).
  - Data format: instruction-tuning JSONL compatible with the target base model.
- **Training:** QLoRA via `transformers` + `peft` + `bitsandbytes`. Train on
  the Phase 1 base model. Save adapter weights.
- **Eval:** Run the existing E2E scenarios + LLM judge against adapter outputs.
  Compare against Phase 1 baseline. Adapter ships only if it passes.
- **Integration:** Add adapter loading path to the target engine's `llm_config.yaml`.
  The base model loads; the LoRA adapter is merged or applied at inference.
- Document the training pipeline in `project/DECISIONS.md` (cross-phase).

## Scope (Out)

- **One adapter only.** Do not start a second adapter for a different engine
  in Phase 3. Infrastructure proves the pattern; depth comes later.
- **No hosted model at inference time.** Data generation uses a hosted API
  (one-time); inference is local Ollama only.
- **No changes to the dialogue engine prompt** unless the target is dialogue and
  Phase 1 found a ceiling there specifically.
- **No demo game changes.** Phase 4 integrates Phase 3 results into the demo.
- **No curriculum learning, RLHF, or DPO.** QLoRA SFT only for V3.

## Entry Criteria

- Phase 1 `handoff.md` is signed off.
- Phase 1 has identified which engine most needs fine-tuning (documented in
  Phase 1 `handoff.md` under "What Phase 3 needs to know").
- Phase 1 base model confirmed and running.
- At least one hosted LLM API key available for synthetic data generation
  (not used at inference time).

## Exit Criteria

1. **[HARD]** All pre-Phase-3 tests pass.
2. **[HARD]** Data pipeline scripts have unit tests. Training script has a dry-run
   test. New tests pass.
3. **[HARD]** E2E scenarios for the target engine do not regress vs. Phase 1
   baseline (adapter must be at least as good as the base model on existing
   scenarios).
4. **[HARD]** Phase owner runs the target engine with the adapter loaded, produces
   3 sample outputs, and documents them in `handoff.md`. Outputs are visibly
   better than baseline on the target behavior (e.g., gossip mutations are more
   naturalistic and varied).
5. **[HARD]** LLM judge run on the 3 sample outputs returns PASS.
6. **[SOFT]** Coverage ≥ 78% on data pipeline and training scripts.

## Affected Modules

- **New directory:** `training/` — data pipeline scripts, training script,
  curated dataset (`training/data/`), adapter weights (`training/adapters/`)
- Target engine `llm_config.yaml` — add `adapter_path` field
- Target engine's adapter loading code — add LoRA loading path
- `tests/unit/` — data pipeline unit tests
- `project/DECISIONS.md` — training pipeline decisions (cross-phase, human copies)

## Docs to Evolve

- `docs/ARCHITECTURE.md` — add a section on the fine-tuning pipeline and adapter
  loading pattern (where it fits in the LLM adapter layer).
- `project/DECISIONS.md` (via human copy from `phase3_finetune_one_adapter/decisions.md`).

## Demo Impact

After Phase 3: the target engine (e.g., gossip) produces visibly more diverse
and contextually grounded outputs. A mentor watching the graph panel in Phase 2's
demo will see gossip mutations that feel like plausible rumors rather than
template substitutions. The narrative "LoRA adapter improves gossip realism;
same pipeline will improve dialogue, quests, etc." is demonstrable.

## Risks

1. **QLoRA training requires >12 GB VRAM** — mitigation: use `bitsandbytes`
   4-bit quantization; train in CPU offload mode if VRAM is insufficient.
   This increases training time but is tractable.
2. **Synthetic data quality is low** — mitigation: hand-curate aggressively;
   50 high-quality examples beat 500 noisy ones for QLoRA.
3. **Adapter degrades quality on scenarios not in training set** — mitigation:
   gate 3 requires no regression on the full E2E suite, not just the target
   engine's scenarios.
4. **Training takes >1 day** — mitigation: start training in the background
   while Phase 2 or Phase 4 polish work proceeds in parallel.

## Estimated Effort

TBD — fleshed out in P3.0 at phase start.

Rough range: 5–8 half-days (data collection 2, training 1–2, eval/integration 2).

If I have to cut: cut the data diversity (fewer examples, less varied prompts).
Do not cut the eval gate — an untested adapter is not a shipped adapter.
