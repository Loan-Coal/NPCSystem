# Fix-Session Index — NPC Engine Review (2026-06-03)

One file per CRITICAL & HIGH consolidated finding. MEDIUM/LOW findings (SEV-19…SEV-43) are documented in `../REVIEW_FINDINGS.md` §3 and sequenced in §5; promote any to a brief when scheduled. Execute in dependency order; same-block items are parallelizable.

Full report: [`../REVIEW_FINDINGS.md`](../REVIEW_FINDINGS.md) · Raw logs: [`../review-evidence/`](../review-evidence/)

## Carry-forward notes

_State that survives between fixes so a fresh `/fix-next` session needn't rediscover it._
_`/fix-next` maintains this: add a line when a fix affects a later one, delete consumed lines, keep it ≤10 lines._

- Harness gates are live: `make check` = lint + check-rules + type-ratchet + check-harness + test-cov(80%). Baselines: `scripts/rules_baseline.txt` (57), `.mypy_baseline` (256). When a fix shrinks either, run `make check-rules-update` / `make type-ratchet-update`.
- SEV-15 DONE: `make check` now uses hard `make type` gate (mypy 0); CI `static-analysis` job runs `make type` (gating). `type-ratchet` kept but no longer in `check` path.
- SEV-01 DONE: eval guard contract now lives in `evals/runner.py::_guard_expectations` (min_length + fallback keyword_none + tone_judge auto-injected per `case_adv_/case_neg_`). `matchers.py` has `min_length` + empty-`npc_response`-fails schema; `summary.headline` returns "NO GUARD TURNS EVALUATED" at 0 turns and `summary.guarantee_demonstrated` gates `runner.main` exit. `test-cov` now also covers `matchers`+`summary`. SEV-27 (output reliability) is now unblocked. DEC-056 records the auto-inject choice.
- SEV-16 DONE: leaking routes (clock/debts/groups/quest_generation) now return static `error_response(...)` envelopes + log real detail via `get_logger`. Reuse this pattern for SEV-33 (one error envelope). Test: `tests/unit/test_route_error_redaction.py` (`_LEAK_TOKENS` guard).
- SEV-17 DONE: dynamic labels in `graph_admin_service._hard_delete_node` + `quest_generation_engine._get_candidates` now wrap label in `cypher_identifier(...)` (quest-gen also via `resolve_node_label`, replacing buggy `.capitalize()`). When SEV-04 moves these into `graph/`, keep the wrap. Test: `tests/unit/test_cypher_label_injection.py`.
- SEV-09 DONE: `gossip_handler.CYPHER_SELECT_EVENT` now returns `coalesce(e.is_canonical,false)` , excludes `k.knowledge_state='corrected'`, and orders canonical-first. When SEV-04 moves this query to `graph/gossip_queries.py`, preserve all three clauses. Tests: `tests/unit/test_gossip_event_selection.py` (query-structure guard, runs in CI) + `tests/integration/test_gossip_event_selection_integration.py` (skips w/o Neo4j).
- SEV-07 DONE: `context_budget_enforcer.fill_to_budget` is canonical — sums tier0+tierA up front and `raise TokenBudgetExceededError` if > `prompt_token_budget`; all tier-A kept (no soft-cap drop); only tier B/C trimmed (incl. post-serialize overhead loop). Default FastAPI 500 (no body leak) is the API mapping. `token_budget_enforcer.py` left in place (ISSUE-054, delete needs approval; DEC-057). Tests: `test_context_budget_enforcer_v14.py`.
- SEV-18 DONE: degradation/memory_consolidation log warnings; gossip rumor-record now re-raises (not atomic — defer to SEV-04); TTS logs warning + increments `tts_failures_total`. Tests: `tests/unit/test_error_swallowing_sev18.py` (patch logger directly — caplog fails due to `propagate=False`).
- SEV-02 DONE: `game_controller._dispatch_proposal` now calls `client.post_interaction(player_id, npc_id, proposal_dict)`; `run.py` uses `DEMO_CACHE_VERSION` from `demo_game/constants.py`. Test: `tests/unit/test_sev02_no_engine_imports.py`.
- SEV-13 DONE: `_WORLD_STATE_ID="world"` in seed.py; `put_world_state` now sends `id="world"` and drops faction_standings/time_of_day/weather clobber. SEV-11 (game losable/winnable) builds on this same world-state arc.
- Hard ordering: **SEV-31 → SEV-04 → {SEV-08, SEV-30, SEV-12}**; SEV-42 DONE so SEV-23 ordering constraint satisfied.
- SEV-04 FULLY DONE (engines): all engine domains migrated to graph/. New files: `graph/event_queries.py`, `graph/faction_politics_queries.py`, `graph/quest_generation_queries.py`. world_reader/world_writer now accept AsyncTransaction for in-tx world state ops. rules_baseline ratcheted to 40. Remaining raw Cypher: `retrieval/`, `world/`, `scheduler/` — not engine violations, lower priority, SEV-08 unblocked.
- ISSUE-056: 8 remaining pre-existing test failures (sev06, sev27, sev18, quest_event_provenance) — quest_lifecycle+routing fixed by SEV-08. Not caused by SEV-08.
- SEV-08 DONE: `check_item_possession_in_tx` (item_queries), `execute_item_transfer_in_tx` (item_writer), `execute_currency_transfer_in_tx` (currency_writer) are new tx-accepting helpers. `apply_rewards` now opens one tx: possession check → delivery collect → reward grants → state+flag+event. DEC-058 waives currency_writer.py 327-line limit.
- SEV-05 DONE: `EmotionStore.get/set` and all `SessionStore` mutation methods are now `async def` + `asyncio.Lock`. `EmotionUpdater` methods also async. Callers updated: `dialogue_handler`, `gossip_handler`, `mood_contagion_engine`, `memory_consolidation_engine`, `npc_state` route. SEV-06 (Semaphore fan-out) follows same scheduler path — no further interface changes needed.
- **SEV-10 APPROVED**: schema change confirmed. api_seeder idempotency strategy still open — see FIX-SEV-10.md (get-then-skip vs client-supplied stable id).
- **SEV-24 APPROVED**: delete 6 nested infra files under src/npc_engine/. **SEV-12 still needs DECISIONS + SEV-04 + SEV-10**.
- All medium/low briefs now written (SEV-23 through SEV-43 except SEV-30). Next issue id: **ISSUE-055**.
- SEV-31 DONE: `scripts/check_layers.py` + `make check-layers` enforce layer ranks; `world/` and `mutation/` assigned rank 2 (graph peer, per actual import edges); `reindex_job_service` moved to `retrieval/`; two engines' upward api imports removed (now raise ValueError if registry not injected). SEV-04 is now unblocked.
- test_action_workers + test_spread_rumor_worker have 2 pre-existing failures (unrelated); do not confuse with regressions.
- SEV-36: shock on any high-severity event (incl. positive) is INTENTIONAL — do not add valence gate. Quest terminal state deferred to DECISIONS.
- SEV-23 DONE: dependency_singletons split → dependencies_infra/stores/engines/advanced + thin re-exporter. political_writer split into 3. api_seeder split into api_seeder/seed_data/seed_http. quest.py helpers → quest_helpers.py. chapter_labeler.py extracted. EmbeddingIndexProtocol → context_protocols.py. Waivers: chapter_engine.py ~322 lines (DEC-062), context_builder.py ~464 lines (DEC-016 updated). rules baseline ratcheted to 38.
- SEV-32 DONE: scripts/docstring_audit.py (CI gate) + scripts/migrate_docstrings.py (one-shot migration); 154 files got Layer: added; check-docstrings added to make check. DEC-063. Placeholder Purpose:/Dependencies:/Used by: values should be filled over time.

## Ordered checklist

### Block A — guarantee + gates (do first)
- [x] **FIX-SEV-15** — CI green: clear lint, add type to CI, restore `make check` · HIGH · S(+L) · deps: SEV-14 for type-gating
- [x] **FIX-SEV-01** — Make the anti-hallucination guarantee real (the moat) · **CRITICAL** · M · deps: none
- [x] **FIX-SEV-25** — Harness honesty: fix stale status docs · MEDIUM · S · deps: none

### Block B — security & correctness quick wins (independent)
- [x] **FIX-SEV-16** — Stop leaking exception detail in HTTP responses · HIGH · S · deps: none
- [x] **FIX-SEV-17** — Sanitize dynamic Cypher labels (`cypher_identifier`) · HIGH · S · deps: none (folds into SEV-04)
- [x] **FIX-SEV-09** — Gossip: canonical never distorts; corrected rumors stop spreading · HIGH · S · deps: none
- *(SEV-19, SEV-20, SEV-21, SEV-22, SEV-40, SEV-41 — done in earlier sessions, no brief files)*

### Block C — concurrency & engine integrity
- [x] **FIX-SEV-05** — Lock `emotion_store`/`session_store` · HIGH · M · deps: approved
- [x] **FIX-SEV-06** — Cap consolidation fan-out with a Semaphore · HIGH · M · deps: SEV-05 (same path)
- [x] **FIX-SEV-07** — Raise `TokenBudgetExceededError` (no silent Tier-A drop) · HIGH · S · deps: none
- [x] **FIX-SEV-08** — Atomic, possession-checked quest rewards · HIGH · M · deps: SEV-04 (tx ownership)
- [x] **FIX-SEV-18** — Log-and-(re)raise instead of swallowing · HIGH · S · deps: gossip site couples to SEV-04

### Block D — layer & type campaigns (large, sequence internally)
- [x] **FIX-SEV-31** — Layer model + contract checker · MEDIUM · M · deps: none → **blocks SEV-04**
- [x] **FIX-SEV-04** — Move Cypher + transactions into `graph/` · HIGH · L · deps: SEV-31; folds in SEV-17, SEV-30
- [x] **FIX-SEV-14** — Pydantic exit schemas + mypy burn-down · HIGH · L · deps: none; completes SEV-15 gating
- [x] **FIX-SEV-10** — Core-node constraints + seeder idempotency · HIGH · M · deps: approved (see FIX-SEV-10.md for open api_seeder idempotency strategy Q)
- [x] **FIX-SEV-29** — Batch N+1 graph queries (gossip + embedding reconciler) · MEDIUM · M · deps: none

### Block E — product & demo
- [x] **FIX-SEV-02** — Remove `npc_engine` imports from `demo_game` · **CRITICAL** · M · deps: none
- [x] **FIX-SEV-13** — Restore canonical WorldState id `world` · HIGH · S · deps: none (coordinate with SEV-11)
- [x] **FIX-SEV-11** — Make game losable/winnable; fix attribution/neutral bribes · HIGH · M · deps: none
- [ ] **FIX-SEV-12** — Multi-tenant / world isolation · HIGH · XL · **deps: DECISIONS approval + SEV-04 + SEV-10**
- [x] **FIX-SEV-28** — WS recv timeout + watchdog · MEDIUM · S · deps: none
- [x] **FIX-SEV-33** — Consistent error envelope for integrators · MEDIUM · M · deps: none
- [x] **FIX-SEV-34** — Fix stale README + command table · MEDIUM · S · deps: none

### Block F — hygiene & docs (low-risk, batchable)
- [x] **FIX-SEV-24** — Delete stale nested infra files under `src/npc_engine/` · MEDIUM · S · deps: approved
- [x] **FIX-SEV-26** — Repo hygiene: git rm cached logs; fix .gitignore · MEDIUM · S · deps: none
- [x] **FIX-SEV-23** — Split unwaived over-300-line files · MEDIUM · L · deps: none (do SEV-42 first to avoid moving reindex_job_service twice)
- [x] **FIX-SEV-27** — Structured-output reliability (temperature + schema + retry) · MEDIUM · M · deps: SEV-01 done
- [x] **FIX-SEV-32** — Bulk-migrate module docstrings to canonical format · MEDIUM · L · deps: none
- [x] **FIX-SEV-35** — Unify `delta_ticks` bound to `MAX_DELTA_TICKS=1000` · LOW · S · deps: none
- [ ] **FIX-SEV-36** — Separate gossip distortion probability from confidence · LOW · M · deps: none (shock behavior intentional — see brief)
- [x] **FIX-SEV-37** — Demo low-severity cluster (magic strings, print, config, QUIT) · LOW · S · deps: none
- [x] **FIX-SEV-38** — Eval-matcher weaknesses + mock LSP · LOW · M · deps: none
- [x] **FIX-SEV-39** — Targeted tests for worst-covered risk modules · LOW · L · deps: none
- [x] **FIX-SEV-42** — Rename duplicate llm_config_loader; relocate reindex_job_service · LOW · S · deps: none
- [x] **FIX-SEV-43** — Contract guards: assert test paths exist + parse symbols · LOW · M · deps: none
- *(SEV-30 event atomicity — MEDIUM · M · deps: SEV-04; no brief yet)*

## Summary

| Severity | Count | Brief files |
|----------|-------|-------------|
| CRITICAL | 2 | SEV-01, SEV-02 |
| HIGH | 16 | SEV-03…SEV-18 |
| MEDIUM | 16 | SEV-23…SEV-34 + SEV-36 |
| LOW | 9 | SEV-35, SEV-37…SEV-43 |

**Critical path:** SEV-15 → SEV-01 (prove the moat) ‖ SEV-31 → SEV-04 → {SEV-08, SEV-12} ; SEV-14 → SEV-15 type-gating.
**Fastest high-value wins (all S, no deps):** SEV-09, SEV-13, SEV-16, SEV-17, SEV-07.
