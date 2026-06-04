# NPC Engine — Final Hardening & Readiness Review: Consolidated Findings

**Date:** 2026-06-04 · **Branch:** munich-demo · **Mode:** 9-lens parallel review (8 static agents + live verification)
**Prior review:** `REVIEW_FINDINGS.md` (43 SEVs, remediated) · **Evidence:** `review-evidence/final/L1..L9-*.md`

> This is a **regression-aware** review: it verifies the ~41 prior fixes still hold AND hunts new issues.
> Per-lens raw reports with file:line evidence live in `project-harness/review-evidence/final/`.

---

## 1. Verdict

The codebase is **substantially stronger than the prior review left it** — mypy 0, coverage 98.31%,
layer model clean, 0 *mechanical* regressions, win/lose reachable, demo standalone. **But it is NOT
release-clean**, for one reason that only live verification could find and four systemic patterns:

🔴 **The current source tree cannot build a bootable container** (a prior hygiene pass deleted a
required runtime file). Under DEC-068 (each studio clones + runs locally), a fresh checkout ships a
**dead app**. This was invisible to unit tests, static analysis, and the regression checker; only the
live arm caught it.

### Counts by severity (this review)
| Severity | Count | IDs |
|----------|-------|-----|
| CRITICAL | 1 | L9-01 |
| HIGH | 13 | L1-01, L1-02, L1-05, L2-01, L3-01, L3-02, L3-03, L4-01(=L9-03), L5-01, L7-01, L7-02, L9-02, L9-04 |
| MEDIUM | ~20 | L1-03/04/06, L2-03/04, L3-04/05/06/07, L4-02/03/04, L5-02/05, L6-01/02, L7-03/04/06/07, L9-05 |
| LOW | ~10 | L1-07, L2-02, L3-08, L4-05/06/07, L5-04, L7-08/09 |

---

## 2. Systemic patterns (root-cause clusters)

1. **"DONE" overstated — several prior fixes only partially landed.** SEV-04 (raw Cypher + engine
   transactions remain — L2-01), SEV-14 (mypy 0 done, but 120/123 routes still un-modelled — L3-01/02),
   SEV-16 (4 route files fixed, the shared `graph_error_to_http` used by 19 sites was not — L1-02),
   SEV-20 (WS cap constant+helper+test exist, never wired into the endpoint — L1-01), SEV-24 (deleted a
   **required** file as "stale" — L9-01). The harness reports green because baselines/guard-tests were
   written to the *partial* scope.
2. **Asserted-not-measured — persists, now inside the fixes.** The prior review's #1 weakness recurs:
   guard tests verify a helper/constant in isolation while the real path is unprotected — WS cap (L1-01),
   SEV-22 seed log (L4-02), SEV-18 gossip mock can't reach the guarded line (L4-04), and the eval battery
   itself is purely-negative and passes on deflections (L4-05). L8's regression pass is mechanical
   (code-present + test-present), so it cannot catch efficacy gaps — by design.
3. **Boundary typing half-done.** mypy is 0, but the *contract* surface a studio consumes is untyped:
   `ok_response → dict[str,Any]`, no `response_model=`, empty OpenAPI bodies, raw dicts in the one named
   response model and in generic graph services (L3 cluster). This also underlies the demo break (L9-02 ↔ L3-07).
4. **OCP seams missing for the stated roadmap.** Distortion types, emotion models, LLM backends, and the
   planned location hierarchy all require editing closed modules or have no write seam (L7 cluster) —
   directly relevant since location hierarchy (ISSUE-057) is next.
5. **Live-only breaks are unguarded.** Container boot and the scripted demo are not in CI; both are red
   on the current tree (L9-01, L9-02), and `docker-compose up -d` silently serves stale images (L9-05).

---

## 3. Triage table (all findings)

Legend: **Fix now** = Phase 2 this session · **Log** = ISSUES.md, defer · **Decide** = needs your call.

| ID | Sev | Title | Lens | Disposition |
|----|-----|-------|------|-------------|
| L9-01 | 🔴CRIT | Fresh build can't boot — `game_schema.yaml` deleted by SEV-24 | live | **Fix now** (restored; commit + CI boot gate) |
| L9-02 | HIGH | `make demo-run` breaks at ACT 1 — world_state partial-update 422 | live | **Fix now** |
| L9-04 | HIGH | Eval gossip guard tests fail — DIAGNOSED: tier-A context unbounded → TokenBudgetExceededError → canned dialogue (not gossip/fence/model). See ISSUE-059 | live | **Logged** (context-builder redesign, ISSUE-059) |
| L4-01 | HIGH | 8 unit failures (ISSUE-056) — `make check` red; 4 test-only root causes | tests | **Fix now** |
| L1-02 | HIGH | `graph_error_to_http` leaks node_type/node_id in 19 handlers (SEV-16 gap) | sec | **Fix now** |
| L1-01 | HIGH | WS per-key connection cap defined but never enforced (SEV-20 gap) | sec | **Fix now** |
| L1-05 | HIGH | SEV-03 prompt injection still unmitigated (no fencing) | sec | **Decide** (M effort, prompt change) |
| L3-01 | HIGH | 120/123 routes lack `response_model=` — empty OpenAPI (SEV-14 gap) | types | **Decide** (L effort) |
| L3-02 | HIGH | `ok_response` returns `dict[str,Any]` — `OkEnvelope[T]` never added | types | **Decide** (root of L3-01) |
| L3-03 | HIGH | `NPCStateResponse` has raw `dict`/`list[dict]` fields | types | **Fix now** |
| L5-01 | HIGH | 40-line fn / 3-nesting rules ungated & widely violated | clean | **Decide** (gate vs waive) |
| L7-01 | HIGH | Distortion type is a closed 3-place if-chain (OCP) | expand | **Decide** (roadmap) |
| L7-02 | HIGH | `location_writer.py` absent — blocks planned PART_OF hierarchy | expand | **Log** (ISSUE-057 pre-work) |
| L2-01 | HIGH | SEV-04 "DONE" overstated — Cypher/tx outside graph/ remain | arch | **Decide** (relabel + plan) |
| L1-03 | MED | `prompt_builder` debug log bypasses env-gate at LOG_LEVEL=DEBUG | sec | **Fix now** |
| L1-04 | MED | Shipped `.env` `API_KEY_SECRET` no staging/prod rejection | sec | **Fix now** |
| L1-06 | MED | `IDEMPOTENCY_ENFORCE_HEADER=false` no staging/prod gate | sec | **Fix now** |
| L3-07 | MED | generic node/edge services accept `dict[str,Any]` (↔ L9-02) | types | **Fix now** (with L9-02) |
| L3-04 | MED | `BaseEngine.run_tick` untyped dict — 11 engines | types | **Log** |
| L3-05 | MED | `from __future__ import annotations` missing 136/365 (auto-fix) | types | **Fix now** (ruff one-liner) |
| L3-06 | MED | 33 request fields `str` not `Literal`/`Enum` | types | **Log** |
| L4-02 | MED | SEV-22 seed-log test asserted-not-measured | tests | **Fix now** |
| L4-03 | MED | `evals/runner.py` excluded from coverage gate | tests | **Fix now** |
| L4-04 | MED | SEV-18 gossip test mock missing `distortion_level` (guard unreached) | tests | **Fix now** |
| L2-03 | MED | `graph_writer` sole-coordinator claim contradicted (folds SEV-30) | arch | **Decide** |
| L2-04 | MED | `gossip_handler` misleading "session.run" comments | arch | **Fix now** |
| L5-02 | MED | Stray untracked `refactor/` dir with duplicate canonical files | clean | **Fix now** |
| L5-05 | MED | Uncapped waiver text on largest engine files | clean | **Log** |
| L6-01 | MED | Persistent-memory has no cross-session e2e test | product | **Log** |
| L6-02 | MED | Prompt-location doc drift (prompts in `src/npc_engine/prompts/`) | product | **Fix now** (doc) |
| L7-03 | MED | Backend Literal vs registry divergence (validate-pass/runtime-fail) | expand | **Fix now** |
| L7-04 | MED | Location graph raw dict + stringly `kind` | expand | **Log** (with ISSUE-057) |
| L7-06 | MED | No `EmotionModelProtocol`; VAD hardcoded | expand | **Log** |
| L7-07 | MED | Adapter self-registration silent import side-effect | expand | **Fix now** |
| L9-05 | MED | `docker-compose up -d` serves stale image; no boot smoke test | ops | **Fix now** (with L9-01 gate) |
| L1-07 | LOW | `WORLD_ID` default `world_demo` not in `.env` (SEV-13 config gap) | sec | **Fix now** |
| L2-02 | LOW | `observability/` absent from layer model (zero Python) | arch | **Fix now** (DECISIONS) |
| L3-08 | LOW | `TYPE_CHECKING` underused | types | **Log** |
| L4-05 | LOW | Guard cases lack positive `keyword_any` | tests | **Log** |
| L4-06 | LOW | Eval tests manual `sys.path` injection | tests | **Fix now** |
| L4-07 | LOW | tone_judge infra failure keeps `guarantee_demonstrated=True` | tests | **Fix now** |
| L5-04 | LOW | Unlogged TODO | clean | **Fix now** |
| L7-08 | LOW | Fat `LLMClientProtocol` (ISP) | expand | **Log** |
| L7-09 | LOW | get-then-skip seeding (ISSUE-055) | expand | **Log** (ISSUE-055) |

---

## 4. Verified clean (audit attestation)

- **mypy 0** across 365 files (SEV-14 type-checking holds); coverage **98.31%**.
- **Layer model clean** — no upward imports; no LLM in graph/retrieval; no prompt strings outside `prompts/`; DIP composition root intact.
- **Regression (mechanical) 0** — all 41 prior fixes' code + guard tests present (L8).
- **Auth surface** — only `/health` public; 401/403 no-body; `/readiness`, `/docs` gated; rate-limit + eviction + SHA-256 keys; SEV-17 (`cypher_identifier`), SEV-21, SEV-22 hold (L1 verified-clean table, 27 checks).
- **Product** — all 10 promised capabilities wired + reachable; SEV-02 (demo standalone), SEV-11 (win AND lose reachable), SEV-08 (reward atomicity), SEV-01 (eval guards fail on empty/fallback) confirmed.
- **type_registry, LLM factory, TTS protocol** — genuinely OCP-open / well-sized (good templates).

---

## 5. Proposed Phase 2 remediation (for approval)

Grouped into conflict-free batches. "Fix now" items only; "Decide"/"Log" pending your call.

- **Batch 1 — Unbreak build & demo (CRIT/HIGH, do first):** L9-01 (commit schema + CI boot gate),
  L9-02 + L3-07 (world_state partial-update / generic upsert create-vs-update), L9-05 (build-SHA in /health).
- **Batch 2 — Tests green (HIGH):** L4-01 (8 ISSUE-056 fixes, test-only), L4-02/04 (strengthen guards),
  L4-03 (runner coverage), L4-06/07.
- **Batch 3 — Security (HIGH/MED):** L1-02 (error redaction in shared helper), L1-01 (wire WS cap),
  L1-03/04/06, L1-07.
- **Batch 4 — Eval correctness (HIGH):** L9-04 (diagnose propagation vs surfacing vs variance, then fix).
- **Batch 5 — Hygiene/docs (MED/LOW):** L5-02 (remove stray `refactor/`), L2-02/04, L6-02, L3-05
  (ruff auto-import), L7-03/07, L5-04.

**Needs your decision before I touch them:**
- **L1-05** (prompt injection): fence player input / move to chat-roles — a prompt + dialogue change.
- **L3-01/02** (response_model across 123 routes): L effort; do all, a subset (public/graph routes), or log?
- **L5-01** (function-length/nesting): add an enforcing gate (and fix/​waive ~dozens), or formally waive the rule?
- **L2-01 / SEV-04**: relabel "DONE"→"PARTIAL" + ISSUE, or actually relocate the residual Cypher now?
- **L7-01** (distortion registry) & **L7-02** (location writer): roadmap pre-work — do now or log for the hierarchy phase?
