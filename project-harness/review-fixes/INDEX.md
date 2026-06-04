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
- SEV-17 DONE: dynamic labels in `graph_admin_service._hard_delete_node` + `quest_generation_engine._get_candidates` now wrap label in `cypher_identifier(...)` (quest-gen also via `resolve_node_label`, replacing buggy `.capitalize()`). When SEV-04 moves these into `graph/`, keep the wrap. Test: `tests/unit/test_cypher_label_injection.py`.
- SEV-09 DONE: `gossip_handler.CYPHER_SELECT_EVENT` now returns `coalesce(e.is_canonical,false)` , excludes `k.knowledge_state='corrected'`, and orders canonical-first. When SEV-04 moves this query to `graph/gossip_queries.py`, preserve all three clauses. Tests: `tests/unit/test_gossip_event_selection.py` (query-structure guard, runs in CI) + `tests/integration/test_gossip_event_selection_integration.py` (skips w/o Neo4j).
- SEV-07 DONE: `context_budget_enforcer.fill_to_budget` is canonical — sums tier0+tierA up front and `raise TokenBudgetExceededError` if > `prompt_token_budget`; all tier-A kept (no soft-cap drop); only tier B/C trimmed (incl. post-serialize overhead loop). Default FastAPI 500 (no body leak) is the API mapping. `token_budget_enforcer.py` left in place (ISSUE-054, delete needs approval; DEC-057). Tests: `test_context_budget_enforcer_v14.py`.
- SEV-18 DONE: degradation/memory_consolidation log warnings; gossip rumor-record now re-raises (not atomic — defer to SEV-04); TTS logs warning + increments `tts_failures_total`. Tests: `tests/unit/test_error_swallowing_sev18.py` (patch logger directly — caplog fails due to `propagate=False`).
- SEV-02 DONE: `game_controller._dispatch_proposal` now calls `client.post_interaction(player_id, npc_id, proposal_dict)`; `run.py` uses `DEMO_CACHE_VERSION` from `demo_game/constants.py`. Test: `tests/unit/test_sev02_no_engine_imports.py`.
- SEV-13 DONE: `_WORLD_STATE_ID="world"` in seed.py; `put_world_state` now sends `id="world"` and drops faction_standings/time_of_day/weather clobber. SEV-11 (game losable/winnable) builds on this same world-state arc.
- Hard ordering: **SEV-31 → SEV-04 → {SEV-08, SEV-17, SEV-30, SEV-12}**; **SEV-14 → SEV-15(type-gate)**.
- Need my approval before starting: **SEV-05** (public-interface async change), **SEV-10** (graph constraints), **SEV-12** (multi-tenant). SEV-06 couples to SEV-05.
- Debt tickets already logged: ISSUE-052 (mypy), ISSUE-053 (rule baseline), ISSUE-054 (delete redundant token_budget_enforcer). Next issue id: **ISSUE-055**.
- SEV-11 DONE: LOSE_LOCATION_ID→"loc_guard_barracks"; spawn_bribe neutral guard added; earn-hint row in world_panel; poller freeze was already correct. rules baseline ratcheted 57→53.
- test_action_workers + test_spread_rumor_worker have 2 pre-existing failures (unrelated to SEV-11); do not confuse with regressions.

## Ordered checklist

### Block A — guarantee + gates (do first)
- [ ] **FIX-SEV-15** — CI green: clear lint, add type to CI, restore `make check` · HIGH · S(+L) · deps: SEV-14 for type-gating
- [x] **FIX-SEV-01** — Make the anti-hallucination guarantee real (the moat) · **CRITICAL** · M · deps: none
- [ ] *(SEV-25 harness honesty — MEDIUM, see report §3; pair with SEV-15)*

### Block B — security & correctness quick wins (independent)
- [x] **FIX-SEV-16** — Stop leaking exception detail in HTTP responses · HIGH · S · deps: none
- [x] **FIX-SEV-17** — Sanitize dynamic Cypher labels (`cypher_identifier`) · HIGH · S · deps: none (folds into SEV-04)
- [x] **FIX-SEV-09** — Gossip: canonical never distorts; corrected rumors stop spreading · HIGH · S · deps: none
- [ ] *(SEV-19 prompt-log redaction, SEV-20 auth surface, SEV-21 weak creds/DoS — MEDIUM; report §3)*

### Block C — concurrency & engine integrity
- [ ] **FIX-SEV-05** — Lock `emotion_store`/`session_store` · HIGH · M · deps: coordinate public-interface change
- [ ] **FIX-SEV-06** — Cap consolidation fan-out with a Semaphore · HIGH · M · deps: coordinate with SEV-05 (same path)
- [x] **FIX-SEV-07** — Raise `TokenBudgetExceededError` (no silent Tier-A drop) · HIGH · S · deps: none
- [ ] **FIX-SEV-08** — Atomic, possession-checked quest rewards · HIGH · M · deps: SEV-04 (tx ownership)
- [x] **FIX-SEV-18** — Log-and-(re)raise instead of swallowing · HIGH · S · deps: gossip site couples to SEV-04

### Block D — layer & type campaigns (large, sequence internally)
- [ ] *(SEV-31 layer model + contract checker — MEDIUM; prerequisite, report §3)*
- [ ] **FIX-SEV-04** — Move Cypher + transactions into `graph/` · HIGH · L · deps: SEV-31; folds in SEV-17, SEV-30
- [x] **FIX-SEV-14** — Pydantic exit schemas + mypy burn-down · HIGH · L · deps: none; completes SEV-15 gating
- [ ] **FIX-SEV-10** — Core-node constraints + seeder idempotency · HIGH · M · deps: human approval (schema change)

### Block E — product & demo
- [x] **FIX-SEV-02** — Remove `npc_engine` imports from `demo_game` · **CRITICAL** · M · deps: none
- [x] **FIX-SEV-13** — Restore canonical WorldState id `world` · HIGH · S · deps: none (coordinate with SEV-11)
- [x] **FIX-SEV-11** — Make game losable/winnable; fix attribution/neutral bribes · HIGH · M · deps: none
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
