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
- **Phase 0 demo-repair DONE** (2026-06-05). **EXP-15/16/17/18/13/52/10/53/21/40 DONE.** Tech-debt Batch B DONE (2026-06-09).
- **Pattern — offload CPU on the event loop:** `await asyncio.to_thread(...)`. REUSE for reranker (ISSUE-064).
- **EXP-32 DONE (2026-06-10):** `evals/anti_hallucination_runner.py` + `make eval-anti-hallucination`. JSON fixture at `evals/cases/anti_hallucination_demo.json`. Metrics: grounded/refusal/hallucination counts. DEC-082: 314-line waiver.
- **KE-6 DONE (2026-06-10):** Stable-ID seeding — `id: str | None` on all inner-life request schemas; MERGE semantics in graph writers; `demo_game/seed.py` + `api_seeder.py` + village/tavern seeds updated. Seeders now always upsert (no get-then-skip). Unblocks EXP-92 + EXP-95.
- **EXP-87 DONE (2026-06-10):** `PART_OF` edge type + `location_writer.py` + `graph/location_graph_queries.py` (`get_ancestors`/`get_descendants`) + `api/routes/locations.py` (POST/DELETE/GET). `demo_game/seed.py` wires `loc_city` hierarchy. `part_of.yaml` uses `src_type: location` / `dst_type: location` (BaseEdgeTypeDocument schema). Unblocks richer location-aware scenarios.
- **DEC-070/071/072/073/076/077/082 apply.** DEC-076: `dependencies_engines.py` 333-line. DEC-077: `config.py` 309-line. DEC-082: `anti_hallucination_runner.py` 314-line.
- **Schema/DECISIONS-gated (DROP):** EXP-51, EXP-17-full, EXP-14, EXP-55 deferred.
- **Open residuals:** ISSUE-064..076, ISSUE-082..090. Next ISSUE id: **ISSUE-091**.
- **Phase 17 remaining:** EXP-92 · EXP-95 — briefs written; ready to dispatch. EXP-92 edits `gossip_handler.py` (seed surface) + new `demo_game/determinism_beat.py`. EXP-95 new `demo_game/ui/start_menu.py` + `arc_choice.py` + edit `__main__.py`. No file conflicts between them.

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
- [x] **EXP-53** — dialogue-driven knowledge learning (`learned_facts`→`BELIEVES`, DEC-072) · M · deps: EXP-32 (soft) · `🔶` believes.yaml +3 fields (approved)
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
- [x] **EXP-10** — proactive dialogue + WS `proactive_line` push (both slices complete: `ProactiveDialogueEngine` + `push_proactive_line` + scheduler wiring + `ProactiveMemoryReader` + `PlayerLocationReader`) · L · deps: EXP-30 ✅, EXP-33 ✅
- [ ] **EXP-51** — NPC goal-formation/GOAP (goal.urgency vs routine) · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [x] **EXP-52** — personal reputation propagation engine (both slices: engine + scheduler wiring) · M · deps: EXP-50
- [x] **EXP-13** — `EmotionModelProtocol` + personality modulation · M · deps: none · refactor `emotion_updater.py`
- [ ] **EXP-14** — persistent emotion state (survive restart) · M · `🔶` emotion node/field

### Phase 4 — World richness & deep systems (later / schema-heavy)
- [ ] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` (DEC-071) · L · `🔶` (approved)
- [ ] **EXP-19** — branching quests & consequence chains · L · `🔶`
- [x] **EXP-18** — semantic memory formation beyond arousal · M · deps: EXP-17
- [x] **EXP-20** — Quest status as enum + fail/expire states · S · deps: none · `QuestStatus` enum in `engines/quest/models.py`
- [x] **EXP-21** — world-state-aware quest trigger (first slice + slice-2: scheduler wiring complete) · M · deps: none
- [x] **EXP-40** — trade dispatch: `NegotiationBackedSyncTradeHandler` wired via `dependencies.py` + `main.py` lifespan · M · deps: none
- [ ] **EXP-42** — niche-engine expansions + demo integration (deprioritized) · — · deps: none
- [ ] **EXP-55** — player-model / theory-of-mind · M · `🔶` `player_model` node · DEFERRED (via memories for now)

### Dropped (out of scope)
- ~~EXP-56 localization~~ · ~~EXP-57 voice/STT~~

## Next parallel batch (suggested)

**BATCH 2026-06-09 COMPLETE:** ISSUE-080 · EXP-33 · EXP-21 slice-1 · EXP-40 slice-1 · EXP-00c — all merged, 1763 unit tests green.

**BATCH 2026-06-09 #2 COMPLETE:** EXP-10 s1 · EXP-21 s2 · EXP-40 s2 — all merged, 1774 unit tests green.

**BATCH 2026-06-09 #3 COMPLETE:** EXP-10 s2 · EXP-52 s2 · EXP-53 — all merged, 1796 unit tests green.

**NEXT BATCH candidates (conflict-free):**
- **EXP-32** (M): anti-hallucination eval — DROP until Q&A label set is ready.
- **EXP-92** (M): determinism/replay toggle — needs KE-6 stable-id seeding; DROP until KE-6 done.
- **EXP-95** (M): in-window scenario picker — needs KE-6; DROP.
- **EXP-87** (L): location hierarchy `PART_OF` — `🔶` DEC-071 approved; no conflicting open items. First viable large item.
- **EXP-14** (M): persistent emotion state — `🔶` schema-gated; DROP.
- **EXP-51** (L): NPC GOAP goal formation — `🔶` schema-gated; DROP.

**Previous suggested batch (superseded 2026-06-10):** ~~EXP-87 solo~~ — brief now written; Phase 17 batch below is the canonical next execution plan.

---

### Phase 17 — Demo Foundation + Missing Expansions

Dependency order: KE-6 must land before EXP-92 and EXP-95. EXP-32 and EXP-87 can run in
parallel with KE-6 (no file conflicts). Schema-gated items are drop-from-batch until approved.

- [x] **KE-6** — stable-ID seeding (ISSUE-055) · M · deps: none · ENABLER · brief: `briefs/KE-6-stable-id-seeding.md`
- [x] **EXP-32** — anti-hallucination eval runner + `make eval-anti-hallucination` · M · deps: none (fixture done) · brief: `briefs/EXP-32-anti-hallucination-eval-runner.md`
- [x] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` · L · `🔶` DEC-071 approved · brief: `briefs/EXP-87-location-hierarchy.md`
- [ ] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 ✅ · brief: `briefs/EXP-92-determinism-replay-proof.md`
- [ ] **EXP-95** — in-window scenario picker (demo) · M · deps: KE-6 ✅ · brief: `briefs/EXP-95-scenario-picker.md`

### Phase 17 — Schema-gated (hold until DECISIONS approval)

- [ ] **EXP-51** — NPC GOAP goal-formation · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [ ] **EXP-14** — persistent emotion state · M · `🔶` emotion node/field schema
- [ ] **EXP-19** — branching quests & consequence chains · L · `🔶` schema change

### Dropped / Deprioritized

- ~~EXP-42~~ niche-engine expansions — deprioritized (low commercial value for demo)
- ~~EXP-55~~ player-model / theory-of-mind — DEFERRED (via memories for now, schema-gated)
- ~~EXP-56 localization~~ · ~~EXP-57 voice/STT~~ — dropped out of scope
