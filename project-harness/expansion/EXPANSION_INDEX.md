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
- **Phase 17 COMPLETE (2026-06-10):** KE-6 + EXP-32 + EXP-87 + EXP-92 + EXP-95 all merged. 1879 engine tests + 614 demo tests green.
- **Pattern — offload CPU on the event loop:** `await asyncio.to_thread(...)`. REUSE for reranker (ISSUE-064).
- **EXP-92 DONE (2026-06-10):** `gossip_handler.py` now returns `seeds_used: dict[str, int]` (sharer→receiver key). `DeterminismBeat` demo scene proves same `tick_override=42` → same seeds side-by-side. Pre-existing DEC-061 waiver covers handler 386-line overage.
- **EXP-95 DONE (2026-06-10):** `demo_game/arc_choice.py` + `demo_game/ui/start_menu.py` + `demo_game/__init__._dispatch()`. `make demo` now shows a 4-option pygame start menu. ISSUE-091: `__init__` imports game_window at load time (P3, didn't manifest in test-demo).
- **DEC-070/071/072/073/076/077/082 apply.** DEC-076: `dependencies_engines.py` 333-line. DEC-077: `config.py` 309-line. DEC-082: `anti_hallucination_runner.py` 314-line.
- **Schema/DECISIONS-gated (DROP):** EXP-51, EXP-17-full, EXP-14, EXP-55, EXP-19 deferred.
- **Open residuals:** ISSUE-064..076, ISSUE-082..091. Next ISSUE id: **ISSUE-092**.
- **No unchecked Phase 17 items remain.** Next batch = schema-gated items only (need DECISIONS approval before dispatch).

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
- [x] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 stable-id seeding
- [x] **EXP-91** — relationship-delta live ticker (demo) · S · deps: EXP-50
- [x] **EXP-80** — free-play/sandbox mode (demo) · M · deps: none
- [x] **EXP-93** — fix ISSUE-060 bribe → `HAS_REPUTATION_WITH` (demo) · S · deps: none
- [x] **EXP-95** — in-window scenario picker (demo) · M · deps: KE-6

### Phase 3 — Agentic NPCs
- [x] **EXP-10** — proactive dialogue + WS `proactive_line` push (both slices complete: `ProactiveDialogueEngine` + `push_proactive_line` + scheduler wiring + `ProactiveMemoryReader` + `PlayerLocationReader`) · L · deps: EXP-30 ✅, EXP-33 ✅
- [ ] **EXP-51** — NPC goal-formation/GOAP (goal.urgency vs routine) · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [x] **EXP-52** — personal reputation propagation engine (both slices: engine + scheduler wiring) · M · deps: EXP-50
- [x] **EXP-13** — `EmotionModelProtocol` + personality modulation · M · deps: none · refactor `emotion_updater.py`
- [ ] **EXP-14** — persistent emotion state (survive restart) · M · `🔶` emotion node/field

### Phase 4 — World richness & deep systems (later / schema-heavy)
- [x] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` (DEC-071) · L · `🔶` (approved)
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

**BATCH 2026-06-10 COMPLETE:** EXP-92 · EXP-95 — both merged, 1879 engine + 614 demo tests green.

**NEXT BATCH candidates:** All remaining unchecked items are schema/DECISIONS-gated. No conflict-free
deployable batch exists until at least one of the following DECISIONS entries is approved:
- **EXP-51** (L): `🔶` requires `GOAL_TARGETS` edge + precedence DEC.
- **EXP-14** (M): `🔶` requires emotion node/field schema DEC.
- **EXP-19** (L): `🔶` requires branching quest schema DEC.
Grant DECISIONS approval and `/expand-parallel` will auto-select the approved item(s).

---

### Phase 17 — Demo Foundation + Missing Expansions

Dependency order: KE-6 must land before EXP-92 and EXP-95. EXP-32 and EXP-87 can run in
parallel with KE-6 (no file conflicts). Schema-gated items are drop-from-batch until approved.

- [x] **KE-6** — stable-ID seeding (ISSUE-055) · M · deps: none · ENABLER · brief: `briefs/KE-6-stable-id-seeding.md`
- [x] **EXP-32** — anti-hallucination eval runner + `make eval-anti-hallucination` · M · deps: none (fixture done) · brief: `briefs/EXP-32-anti-hallucination-eval-runner.md`
- [x] **EXP-87** — location hierarchy `PART_OF` + `location_writer.py` · L · `🔶` DEC-071 approved · brief: `briefs/EXP-87-location-hierarchy.md`
- [x] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 ✅ · brief: `briefs/EXP-92-determinism-replay-proof.md`
- [x] **EXP-95** — in-window scenario picker (demo) · M · deps: KE-6 ✅ · brief: `briefs/EXP-95-scenario-picker.md`

### Phase 17 — Schema-gated (hold until DECISIONS approval)

- [ ] **EXP-51** — NPC GOAP goal-formation · L · `🔶` `GOAL_TARGETS` edge + precedence DEC
- [ ] **EXP-14** — persistent emotion state · M · `🔶` emotion node/field schema
- [ ] **EXP-19** — branching quests & consequence chains · L · `🔶` schema change

### Dropped / Deprioritized

- ~~EXP-42~~ niche-engine expansions — deprioritized (low commercial value for demo)
- ~~EXP-55~~ player-model / theory-of-mind — DEFERRED (via memories for now, schema-gated)
- ~~EXP-56 localization~~ · ~~EXP-57 voice/STT~~ — dropped out of scope
