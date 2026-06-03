# Fix-Session Index — NPC Engine Review (2026-06-03)

One file per CRITICAL & HIGH consolidated finding. MEDIUM/LOW findings (SEV-19…SEV-43) are documented in `../REVIEW_FINDINGS.md` §3 and sequenced in §5; promote any to a brief when scheduled. Execute in dependency order; same-block items are parallelizable.

Full report: [`../REVIEW_FINDINGS.md`](../REVIEW_FINDINGS.md) · Raw logs: [`../review-evidence/`](../review-evidence/)

## Carry-forward notes

_State that survives between fixes so a fresh `/fix-next` session needn't rediscover it._
_`/fix-next` maintains this: add a line when a fix affects a later one, delete consumed lines, keep it ≤10 lines._

- Harness gates are live: `make check` = lint + check-rules + type-ratchet + check-harness + test-cov(80%). Baselines: `scripts/rules_baseline.txt` (57), `.mypy_baseline` (256). When a fix shrinks either, run `make check-rules-update` / `make type-ratchet-update`.
- SEV-15 lint portion DONE (commit `afecbb6`); what remains of SEV-15 is flipping `make type` to a hard CI gate AFTER SEV-14 drives mypy to 0.
- SEV-01 DONE: eval guard contract now lives in `evals/runner.py::_guard_expectations` (min_length + fallback keyword_none + tone_judge auto-injected per `case_adv_/case_neg_`). `matchers.py` has `min_length` + empty-`npc_response`-fails schema; `summary.headline` returns "NO GUARD TURNS EVALUATED" at 0 turns and `summary.guarantee_demonstrated` gates `runner.main` exit. `test-cov` now also covers `matchers`+`summary`. SEV-27 (output reliability) is now unblocked. DEC-056 records the auto-inject choice.
- SEV-16 DONE: leaking routes (clock/debts/groups/quest_generation) now return static `error_response(...)` envelopes + log real detail via `get_logger`. Reuse this pattern for SEV-33 (one error envelope). Test: `tests/unit/test_route_error_redaction.py` (`_LEAK_TOKENS` guard).
- Hard ordering: **SEV-31 → SEV-04 → {SEV-08, SEV-17, SEV-30, SEV-12}**; **SEV-14 → SEV-15(type-gate)**.
- Need my approval before starting (schema / DECISIONS): **SEV-10** (graph constraints), **SEV-12** (multi-tenant).
- Debt tickets already logged: ISSUE-052 (mypy), ISSUE-053 (rule baseline). Next issue id: **ISSUE-054**.

## Ordered checklist

### Block A — guarantee + gates (do first)
- [ ] **FIX-SEV-15** — CI green: clear lint, add type to CI, restore `make check` · HIGH · S(+L) · deps: SEV-14 for type-gating
- [x] **FIX-SEV-01** — Make the anti-hallucination guarantee real (the moat) · **CRITICAL** · M · deps: none
- [ ] *(SEV-25 harness honesty — MEDIUM, see report §3; pair with SEV-15)*

### Block B — security & correctness quick wins (independent)
- [x] **FIX-SEV-16** — Stop leaking exception detail in HTTP responses · HIGH · S · deps: none
- [ ] **FIX-SEV-17** — Sanitize dynamic Cypher labels (`cypher_identifier`) · HIGH · S · deps: none (folds into SEV-04)
- [ ] **FIX-SEV-09** — Gossip: canonical never distorts; corrected rumors stop spreading · HIGH · S · deps: none
- [ ] *(SEV-19 prompt-log redaction, SEV-20 auth surface, SEV-21 weak creds/DoS — MEDIUM; report §3)*

### Block C — concurrency & engine integrity
- [ ] **FIX-SEV-05** — Lock `emotion_store`/`session_store` · HIGH · M · deps: coordinate public-interface change
- [ ] **FIX-SEV-06** — Cap consolidation fan-out with a Semaphore · HIGH · M · deps: coordinate with SEV-05 (same path)
- [ ] **FIX-SEV-07** — Raise `TokenBudgetExceededError` (no silent Tier-A drop) · HIGH · S · deps: none
- [ ] **FIX-SEV-08** — Atomic, possession-checked quest rewards · HIGH · M · deps: SEV-04 (tx ownership)
- [ ] **FIX-SEV-18** — Log-and-(re)raise instead of swallowing · HIGH · S · deps: gossip site couples to SEV-04

### Block D — layer & type campaigns (large, sequence internally)
- [ ] *(SEV-31 layer model + contract checker — MEDIUM; prerequisite, report §3)*
- [ ] **FIX-SEV-04** — Move Cypher + transactions into `graph/` · HIGH · L · deps: SEV-31; folds in SEV-17, SEV-30
- [ ] **FIX-SEV-14** — Pydantic exit schemas + mypy burn-down · HIGH · L · deps: none; completes SEV-15 gating
- [ ] **FIX-SEV-10** — Core-node constraints + seeder idempotency · HIGH · M · deps: human approval (schema change)

### Block E — product & demo
- [ ] **FIX-SEV-02** — Remove `npc_engine` imports from `demo_game` · **CRITICAL** · M · deps: none
- [ ] **FIX-SEV-13** — Restore canonical WorldState id `world` · HIGH · S · deps: none (coordinate with SEV-11)
- [ ] **FIX-SEV-11** — Make game losable/winnable; fix attribution/neutral bribes · HIGH · M · deps: none
- [ ] **FIX-SEV-12** — Multi-tenant / world isolation · HIGH · XL · **deps: DECISIONS approval + SEV-04 + SEV-10**
- [ ] *(SEV-28 WS timeout, SEV-33 error envelope, SEV-34 README — MEDIUM; report §3)*

### Block F — hygiene & docs (low-risk, batchable)
- [ ] *(SEV-23 file size, SEV-24 nested infra [delete approval], SEV-26 repo hygiene, SEV-27 structured output [after SEV-01], SEV-29 N+1, SEV-30 event atomicity, SEV-32 docstrings, SEV-35–43 — MEDIUM/LOW; report §3 & §5)*

## Summary

| Severity | Count | Brief files |
|----------|-------|-------------|
| CRITICAL | 2 | SEV-01, SEV-02 |
| HIGH | 16 | SEV-03…SEV-18 |
| MEDIUM | 16 | (in REVIEW_FINDINGS.md §3) |
| LOW | 9 | (in REVIEW_FINDINGS.md §3) |

**Critical path:** SEV-15 → SEV-01 (prove the moat) ‖ SEV-31 → SEV-04 → {SEV-08, SEV-12} ; SEV-14 → SEV-15 type-gating.
**Fastest high-value wins (all S, no deps):** SEV-09, SEV-13, SEV-16, SEV-17, SEV-07.
