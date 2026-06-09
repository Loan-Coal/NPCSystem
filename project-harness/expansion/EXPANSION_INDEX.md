# Expansion Index — NPC Engine (driver for `/expand-parallel`)

The execution backlog for the expansion roadmap. One self-contained first-slice brief per item lives
in `briefs/EXP-NN-<slug>.md`. Full mini-specs (the "why" + deep detail) live in `ENGINE_GAPS.md`,
`NEW_ENGINES.md`, `DEMO_EXPANSIONS.md`; architecture verdicts in `FEASIBILITY.md`; sequencing in
`EXPANSION_ROADMAP.md`. Execute in dependency order; same-phase non-conflicting items are parallelizable.

`/expand-parallel` reads this file (incl. the Carry-forward block) to pick a conflict-free batch.
`/fix-next` and the review harness are NOT used here — this is feature work, not remediation.

## Carry-forward notes

_State that survives between expansion sessions so a fresh `/expand-parallel` run needn't rediscover it._
_The orchestrator maintains this: add a line when an item unlocks/affects a later one; delete consumed lines; keep it tight._

- **Gates:** `make check` = lint + check-rules + type-ratchet + check-harness + test-cov(80%). Demo work also runs `make test-demo`. New code: TDD (failing test first), CLAUDE.md OCP add-by-new-file, layers, 300-line/40-line, prompts-in-YAML, Pydantic boundaries. All new `src/npc_engine/` files must have `Does NOT:` + `Dependencies injected:` in module docstring (architecture conformance test).
- **Phase 0 demo-repair DONE** (2026-06-05): engines-500, pledges drift, embedding offload, WS timeout, trade 422. EXP-00c (CI smoke) deferred.
- **Pattern — offload CPU on the event loop:** sync model inference via `await asyncio.to_thread(...)`. REUSE for reranker (ISSUE-064) and any new sync ML call.
- **EXP-30/50/31/83/84/85/93/81/91/11/80 DONE** (2026-06-05). EXP-32 needs Q&A fixture before dispatch.
- **EXP-15/16 DONE:** `STRATEGY_REGISTRY` + `DistortionStrategy` Protocol; prefixes moved to `prompts/gossip/distortion.yaml` via `prefix_loader.py`. Add new distortion type = new file + YAML entry only.
- **EXP-17/18 DONE:** `decay_vividness_weighted` in `memory_service.py`; `create_from_semantic_triggers()` in `memory_engine.py` (8 keywords, vividness=60). EXP-18 full-version (recall_count/never_forget) still schema-gated.
- **EXP-13 DONE:** `EmotionModelProtocol` + `VadEmotionModel`. Inject via `EmotionUpdater(store, model=YourModel())`.
- **EXP-52 DONE (slice-1):** `ReputationEngine` + `apply_trust_nudge`. Off by default. Next slice: wire into tick scheduler.
- **EXP-12 DONE:** Structured audit log in `engines/dialogue/relation_mutator.py` (attempt/applied/edge_missing). Tests use `patch("...._LOGGER")` not caplog (configure_logging sets propagate=False).
- **EXP-20 DONE:** `QuestStatus(str, enum.Enum)` in `engines/quest/models.py` (7 members incl. FAILED/EXPIRED). `QuestStateRecord.status: QuestStatus`. Slice-2 (transition logic for FAILED/EXPIRED) still open.
- **DEC-070/071/072/073 still apply.** DEC-073 (old numbering): `context_builder.py` 446-line waiver. DEC-074: `game_window.py` 337-line. DEC-075: `quest_trade_controller.py` 312-line.
- **DEC-073 (2026-06-09): EXP-10 WS `proactive_line` shape approved** — `{type, npc_id, content, reason, tick}`. EXP-10 unblocked; dispatch in next batch (EXP-33 now merged — `main.py` conflict resolved).
- **EXP-33 DONE (2026-06-09):** `GET /admin/debug/retrieval` live. Note: tier/priority metadata is sentinel (`"unknown"/0`) — real metadata needs calling `merge_context` before `fill_to_budget` (follow-up slice).
- **EXP-21 slice-1 DONE:** `WorldStateQuestTrigger` class only. Slice-2 needed: wire into `tick_scheduler.py` + `dependencies_engines.py`.
- **EXP-40 slice-1 DONE:** `SyncTradeHandlerProtocol` + `MinimalSyncTradeHandler`. Slice-2: inject async economy handler. Note: `InteractionState`/`InteractionProposal` should migrate to Pydantic v2 (ISSUE-086).
- **EXP-00c DONE:** `make smoke` target + `test_boot_smoke.py`. API_KEY_SECRET must be ≥16 chars in test fixtures.
- **ISSUE-080 FIXED:** `_force_patch_world_state` added to `demo_game/seed.py` — always force-patches epoch=war.
- **Schema/DECISIONS-gated (DROP from parallel batches):** EXP-51, EXP-17-full, EXP-87, EXP-53 (needs EXP-32 first), EXP-55 deferred.
- **Open residuals:** ISSUE-064..076, ISSUE-082..086. Next ISSUE id: **ISSUE-087**.

## Ordered checklist

Effort: S/M/L/XL · `🔶` = schema/DECISIONS-gated (drop from parallel until granted) · briefs in `briefs/`.

### Phase 0 — Demo repair + contract guard
- [x] **EXP-00a** — fix `/v1/system/engines` 500 (double-serialize) · M · ISSUE-062
- [x] **EXP-00b** — fix demo↔API path drift (pledges) + audit · S · ISSUE-061
- [x] **EXP-00d** — offload embedding encode off event loop · M · ISSUE-063
- [x] **EXP-00e** — WS dialogue timeout 120s · S · ISSUE-065
- [x] **EXP-00f** — confirm-trade empty `item_type` 422 · S · ISSUE-067
- [x] **EXP-00c** — boot + demo-endpoint smoke test in CI (also runs `make test-demo`) · M · deps: none · unblocks regression-proofing all of Phase 0

### Phase 1 — Prove & unblock (parallelizable batch — all new-file-add or single-module, conflict-free)
- [x] **EXP-30** — context: pinned-core + ranked pool (DEC-070) · M · deps: none · KEYSTONE · edits `retrieval/context_builder.py`+`context_budget_enforcer.py`
- [x] **EXP-50** — relationship/affinity engine (first slice: `derive_standing` + read route) · S · deps: none · new `engines/relationship/`
- [x] **EXP-31** — retrieval precision@k/recall eval harness · M · deps: none · new eval files
- [x] **EXP-33** — retrieval debug endpoint `GET /admin/debug/retrieval` (Phase 15 S15.1) · S · deps: EXP-31 (soft) · edits `main.py` · brief: `briefs/EXP-33-retrieval-debug-endpoint.md`
- [x] **EXP-83** — integrator hello-world quickstart · S · deps: none · new `demo_game/quickstart.py` + Makefile
- [ ] **EXP-32** — measured anti-hallucination eval · M · deps: EXP-30 (soft), Q&A label set · new eval files

### Phase 2 — Dialogue + Gossip showcase (the priority)
- [ ] **EXP-53** — dialogue-driven knowledge learning (`learned_facts`→`BELIEVES`, DEC-072) · M · deps: EXP-32 (soft) · `🔶` believes.yaml +3 fields (approved)
- [x] **EXP-11** — player-scoped long-term memory recall in dialogue · M · deps: EXP-30
- [x] **EXP-12** — relation-delta provenance & audit trail · S · deps: none · structured log in `engines/dialogue/relation_mutator.py`
- [x] **EXP-17** — salience forgetting curve (first slice: charge-weighted decay) · M · deps: EXP-30 · full version `🔶`
- [x] **EXP-15** — distortion-strategy registry (open L7-01 if-chain) · M · deps: none · refactor `gossip_distort.py`
- [x] **EXP-16** — belief/secret-selective, prompt-driven distortion · M · deps: EXP-15
- [x] **EXP-81** — cross-session "remembers you" demo · M · deps: EXP-30
- [x] **EXP-84** — gossip telephone-diff view (demo) · S · deps: EXP-15 (soft)
- [x] **EXP-85** — anti-hallucination "I don't know" demo beat · S · deps: none
- [ ] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 stable-id seeding
- [x] **EXP-91** — relationship-delta live ticker (demo) · S · deps: EXP-50
- [x] **EXP-80** — free-play/sandbox mode (demo) · M · deps: none
- [x] **EXP-93** — fix ISSUE-060 bribe → `HAS_REPUTATION_WITH` (demo) · S · deps: none
- [ ] **EXP-95** — in-window scenario picker (demo) · M · deps: KE-6

### Phase 3 — Agentic NPCs
- [ ] **EXP-10** — proactive dialogue + WS `proactive_line` push · L · deps: EXP-30 ✅, EXP-33 (must merge first — shared `main.py`) · DEC-073 approved · brief: `briefs/EXP-10-proactive-dialogue-first-slice.md`
- [ ] **EXP-51** — NPC goal-formation/GOAP (goal.urgency vs routine) · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [x] **EXP-52** — personal reputation propagation engine · M · deps: EXP-50
- [x] **EXP-13** — `EmotionModelProtocol` + personality modulation · M · deps: none · refactor `emotion_updater.py`
- [ ] **EXP-14** — persistent emotion state (survive restart) · M · `🔶` emotion node/field

### Phase 4 — World richness & deep systems (later / schema-heavy)
- [ ] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` (DEC-071) · L · `🔶` (approved)
- [ ] **EXP-19** — branching quests & consequence chains · L · `🔶`
- [x] **EXP-18** — semantic memory formation beyond arousal · M · deps: EXP-17
- [x] **EXP-20** — Quest status as enum + fail/expire states · S · deps: none · `QuestStatus` enum in `engines/quest/models.py`
- [x] **EXP-21** — world-state-aware quest trigger (first slice: new `WorldStateQuestTrigger`) · M · deps: none · brief: `briefs/EXP-21-world-state-quest-trigger.md` · slice-2 (scheduler wiring) still open
- [x] **EXP-40** — trade dispatch: inject `SyncTradeHandlerProtocol` (first slice) · M · deps: none · brief: `briefs/EXP-40-trade-dispatch-sync-handler.md` · slice-2 (async economy wiring) still open
- [ ] **EXP-42** — niche-engine expansions + demo integration (deprioritized) · — · deps: none
- [ ] **EXP-55** — player-model / theory-of-mind · M · `🔶` `player_model` node · DEFERRED (via memories for now)

### Dropped (out of scope)
- ~~EXP-56 localization~~ · ~~EXP-57 voice/STT~~

## Next parallel batch (suggested)

**BATCH 2026-06-09 COMPLETE:** ISSUE-080 · EXP-33 · EXP-21 slice-1 · EXP-40 slice-1 · EXP-00c — all merged, 1754 unit tests green.

**NEXT BATCH:** EXP-10 · EXP-21 slice-2 · EXP-40 slice-2 · EXP-32 (if Q&A ready)
- **EXP-10**: proactive dialogue. Deps: EXP-33 merged ✅. Edits `main.py` + `dialogue_ws.py` + new engine files. Brief + DEC-073 ready.
- **EXP-21 slice-2**: wire `WorldStateQuestTrigger` into `tick_scheduler.py` + `dependencies_engines.py`. May conflict with EXP-10 on `tick_scheduler.py` — group if so.
- **EXP-40 slice-2**: inject async economy handler. Edits `dispatch.py` + `dependencies.py`. No conflict with EXP-10.
- **EXP-32**: measured anti-hallucination eval. Still needs Q&A label set from `EXP32_EVAL_QA_TASK.md` — DROP until ready.
- **EXP-14**: schema-gated — DROP until emotion node approved.
