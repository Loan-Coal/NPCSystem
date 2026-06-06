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
- **EXP-15 DONE:** `STRATEGY_REGISTRY` + `DistortionStrategy` Protocol in `engines/gossip/distortion_strategy.py`. EXP-16 now unblocked — move hardcoded template strings to `prompts/gossip/distortion.yaml`.
- **EXP-17 DONE (slice-1):** `decay_vividness_weighted` + `CYPHER_DECAY_VIVIDNESS_WEIGHTED` in `memory_service.py`/`memory_queries.py`. Full-version `recall_count`/`never_forget` fields still schema-gated. EXP-18 unblocked by this slice (formation beyond arousal threshold can proceed).
- **EXP-13 DONE:** `EmotionModelProtocol` (runtime_checkable) in `engines/emotion/emotion_model_protocol.py`; `VadEmotionModel` in `vad_emotion_model.py`. `EmotionUpdater` now accepts the protocol. New emotion models = new files. Inject via `EmotionUpdater(store, model=YourModel())`.
- **EXP-52 DONE (slice-1):** `ReputationEngine` in `engines/reputation/reputation_engine.py` + `apply_trust_nudge` in `graph/reputation_nudge.py`. Off by default (`reputation_rules.yaml enabled: false`). Next slice: wire into tick scheduler + evaluate diffusion.
- **DEC-070/072/071/073/074/075 still apply.** DEC-073: `context_builder.py` 446-line waiver. DEC-074: `game_window.py` 337-line. DEC-075: `quest_trade_controller.py` 312-line.
- **Schema/DECISIONS-gated (DROP from parallel batches):** EXP-51, EXP-17-full, EXP-87, EXP-53 (needs EXP-32 first), EXP-55 deferred.
- **Open residuals:** ISSUE-064..070, ISSUE-072..076. Next ISSUE id: **ISSUE-077**.

## Ordered checklist

Effort: S/M/L/XL · `🔶` = schema/DECISIONS-gated (drop from parallel until granted) · briefs in `briefs/`.

### Phase 0 — Demo repair + contract guard
- [x] **EXP-00a** — fix `/v1/system/engines` 500 (double-serialize) · M · ISSUE-062
- [x] **EXP-00b** — fix demo↔API path drift (pledges) + audit · S · ISSUE-061
- [x] **EXP-00d** — offload embedding encode off event loop · M · ISSUE-063
- [x] **EXP-00e** — WS dialogue timeout 120s · S · ISSUE-065
- [x] **EXP-00f** — confirm-trade empty `item_type` 422 · S · ISSUE-067
- [ ] **EXP-00c** — boot + demo-endpoint smoke test in CI (also runs `make test-demo`) · M · deps: none · unblocks regression-proofing all of Phase 0

### Phase 1 — Prove & unblock (parallelizable batch — all new-file-add or single-module, conflict-free)
- [x] **EXP-30** — context: pinned-core + ranked pool (DEC-070) · M · deps: none · KEYSTONE · edits `retrieval/context_builder.py`+`context_budget_enforcer.py`
- [x] **EXP-50** — relationship/affinity engine (first slice: `derive_standing` + read route) · S · deps: none · new `engines/relationship/`
- [x] **EXP-31** — retrieval precision@k/recall eval harness · M · deps: none · new eval files
- [x] **EXP-83** — integrator hello-world quickstart · S · deps: none · new `demo_game/quickstart.py` + Makefile
- [ ] **EXP-32** — measured anti-hallucination eval · M · deps: EXP-30 (soft), Q&A label set · new eval files

### Phase 2 — Dialogue + Gossip showcase (the priority)
- [ ] **EXP-53** — dialogue-driven knowledge learning (`learned_facts`→`BELIEVES`, DEC-072) · M · deps: EXP-32 (soft) · `🔶` believes.yaml +3 fields (approved)
- [x] **EXP-11** — player-scoped long-term memory recall in dialogue · M · deps: EXP-30
- [x] **EXP-17** — salience forgetting curve (first slice: charge-weighted decay) · M · deps: EXP-30 · full version `🔶`
- [x] **EXP-15** — distortion-strategy registry (open L7-01 if-chain) · M · deps: none · refactor `gossip_distort.py`
- [ ] **EXP-16** — belief/secret-selective, prompt-driven distortion · M · deps: EXP-15
- [x] **EXP-81** — cross-session "remembers you" demo · M · deps: EXP-30
- [x] **EXP-84** — gossip telephone-diff view (demo) · S · deps: EXP-15 (soft)
- [x] **EXP-85** — anti-hallucination "I don't know" demo beat · S · deps: none
- [ ] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 stable-id seeding
- [x] **EXP-91** — relationship-delta live ticker (demo) · S · deps: EXP-50
- [x] **EXP-80** — free-play/sandbox mode (demo) · M · deps: none
- [x] **EXP-93** — fix ISSUE-060 bribe → `HAS_REPUTATION_WITH` (demo) · S · deps: none
- [ ] **EXP-95** — in-window scenario picker (demo) · M · deps: KE-6

### Phase 3 — Agentic NPCs
- [ ] **EXP-10** — proactive dialogue + WS `proactive_line` push · L · deps: EXP-30 · API-surface add
- [ ] **EXP-51** — NPC goal-formation/GOAP (goal.urgency vs routine) · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [x] **EXP-52** — personal reputation propagation engine · M · deps: EXP-50
- [x] **EXP-13** — `EmotionModelProtocol` + personality modulation · M · deps: none · refactor `emotion_updater.py`
- [ ] **EXP-14** — persistent emotion state (survive restart) · M · `🔶` emotion node/field

### Phase 4 — World richness & deep systems (later / schema-heavy)
- [ ] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` (DEC-071) · L · `🔶` (approved)
- [ ] **EXP-19** — branching quests & consequence chains · L · `🔶`
- [ ] **EXP-18** — semantic memory formation beyond arousal · M · deps: EXP-17
- [ ] **EXP-21** — world-state-aware dynamic quest generation · M · deps: none
- [ ] **EXP-40** — interaction trade-dispatch (stub → real; fixes ISSUE-067 deeper) · M · deps: none
- [ ] **EXP-42** — niche-engine expansions + demo integration (deprioritized) · — · deps: none
- [ ] **EXP-55** — player-model / theory-of-mind · M · `🔶` `player_model` node · DEFERRED (via memories for now)

### Dropped (out of scope)
- ~~EXP-56 localization~~ · ~~EXP-57 voice/STT~~

## Next parallel batch (suggested)

**EXP-16, EXP-18, EXP-12, EXP-20** — candidates from Phase 2/3/4 (all deps satisfied, no schema changes):
- **EXP-16**: distortion content → YAML. Deps: EXP-15 ✅. New `prompts/gossip/distortion.yaml`; edits `distortion_strategy.py` strategy callables to load prefix strings from YAML instead of hardcoded `_PREFIX` constants. No other file.
- **EXP-18**: semantic memory formation beyond arousal threshold. Deps: EXP-17 ✅. Edits `memory_engine.py` + `memory_queries.py` (new Cypher), no schema change (reuses existing `Memory` node fields).
- **EXP-12**: relation-delta provenance & audit trail. Deps: none. Edits `mutation/relation_mutator.py` only — adds structured log entry per write.
- **EXP-20**: Quest status as enum + fail/expire states. Deps: none. Edits `engines/quest/quest_lifecycle_engine.py` + `models.py` — adds `QuestStatus` enum (no new edge/node).

**Conflicts:** EXP-16 (new yaml + edits `distortion_strategy.py`) and EXP-18 (edits `memory_engine.py`+`memory_queries.py`) are fully disjoint. EXP-12 and EXP-20 each touch a single distinct file. All four are safe to dispatch in parallel.

**Drop if not ready:** EXP-32 (still needs Q&A label set). EXP-40 (interaction dispatch — confirm brief before dispatch).
