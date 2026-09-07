# Shared reviewer brief — full-review night run 2026-09-07

**Branch:** remediation-2026-08 · **HEAD:** 8d30a3e1 · **Tree: CLEAN** (measurement-remediation
Phase 5 landed in ef870f7f; nothing in flight — every path is committed and fair game).

## Standing goal
**A small local model producing great effects.** Findings that shrink what the model must do,
or that let a smaller model do it, outrank findings that merely tidy code.

## What just landed (DEC-273) — build on, do not re-derive
LLM latency instrumentation now exists: `llm_backend_calls_total`, `llm_backend_latency_seconds`,
`llm_backend_load_latency_seconds` on `GET /v1/admin/system/metrics`; plus `duration_ms` /
`load_duration_ms` / `prompt_eval_duration_ms` / `eval_duration_ms` on the `llm_prompt_eval` log record.
Measured facts:
- decode is ~97% of a warm dialogue turn; prefill is prefix-cached and effectively free
- warm dialogue is 3.5–4.2s against a 3–7s budget
- the only measured budget breach was a 10.3s cold model load, fixed by `keep_alive=30m`
- **NULL result:** trimming the generation schema moved decoded tokens 70.0 → 72.0. Do NOT re-propose
  schema trimming as a latency win.

## Eval stack — half usable, and the split is load-bearing
USABLE: generation, deterministic matchers (schema/keyword/in_set/substring), latency stats,
retrieval metrics, `engine_status` liveness/timing, isolated stack via `make eval-stack-up`.
NOT USABLE: anything judged. All five scorers are REFUSED by `scripts/check_label_adequacy.py`,
the label set is NOT FROZEN, panel kappa swung 0.58→0.83. **Never quote a judged eval number as
evidence of quality.** A rate your own trust policy would refuse is worse than no rate.

## Prior art — dedupe before you claim novelty
`project-harness/ISSUES.md` has 117 open entries; `project-harness/archive/ISSUES_RESOLVED.md` has 180.
Grep both before writing a finding. A finding that contradicts a RESOLVED issue is a **REGRESSION** —
say so explicitly and raise its severity.

## Prior review to re-verify against
`project-harness/archive/review-2026-06-03/FINAL_REVIEW_FINDINGS.md` (1 CRITICAL, 13 HIGH, ~20 MED).
Open it and re-verify the SEVs in your own area. Its 5 systemic patterns were:
1. "DONE" overstated — prior fixes only partially landed
2. Asserted-not-measured — guard tests verify a constant in isolation while the real path is unprotected
3. Boundary typing half-done
4. OCP seams missing for the roadmap
5. Live-only breaks unguarded (container boot, scripted demo)

## Rubric
`project-harness/CLAUDE.md` is binding: layer model + rank order, 400 advisory / 800 hard file lines,
40-line functions, nesting ≤3, Pydantic at every module boundary, `Literal`/`Enum` for fixed value
sets, typed exceptions from `utils/errors.py`, structured logging (never `print()`), auth on every
route except `GET /health`, input caps at the API boundary, no prompt strings outside `prompts/`.

---

## ⚠️ CORRECTION — the newest review is NOT the 2026-06-03 archive

`project-harness/review-2026-08/` is a **more recent, still-active** review and is the primary
prior art. This branch (`remediation-2026-08`) exists to remediate it. Files:
- `review-2026-08/FINDINGS.md` — 145 raw findings across 16 lenses (`CR-L01`…`CR-L16`)
- `review-2026-08/TRIAGE.md` — adversarial triage, 145 in → **118 canonical distinct problems**
  (79 UPHELD, 27 MERGED, 21 RECALIBRATED, 11 DEFERRED-VALID, 7 WITHDRAWN). 4 CRITICALs, all survived.
- `review-2026-08/FIX_PLANS.md` — the remediation briefs
- `review-2026-08/BASELINE_2026-08-28.md` — measured "before" numbers. Do not re-derive these:
  `make test-demo` 1,116 passed · `make test` 4,048 passed/36 skipped · coverage 87.86% (floor 80)
  · evals coverage 79.76% (floor 75) · mypy baseline 0 · `demo_game/` mypy **256 errors in 45 files,
  ungated** · 133 grandfathered `rules_baseline` entries · 72 `evals_baseline` entries.
- `review-2026-08/evidence/CR-L01.md` … `CR-L16.md` — per-lens evidence with file:line.

**This changes your dedupe duty.** Before writing ANY finding, grep `review-2026-08/TRIAGE.md` and
`review-2026-08/FINDINGS.md` for it, in addition to `ISSUES.md` and `archive/ISSUES_RESOLVED.md`.
- Duplicates a canonical CR-* finding → still report it, but add `**Already known:** CR-LNN-NN`
  and say whether the tree has moved since 2026-08-28 (fixed / unchanged / worse).
- Contradicts a WITHDRAWN finding → say so; the withdrawal may have been wrong.
- **A CR-* finding marked fixed/remediated that you find still live is a REGRESSION** — raise severity.

Your value-add is what is TRUE ON THE TREE TODAY (HEAD 8d30a3e1) and what the 2026-08 lenses did not
look at. The genuinely new ground is L10–L13: engine portfolio/dead surface, LLM dependence per call
site, prompt content, and runtime coupling/load. Weight your effort there.
