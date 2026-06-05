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

- **Gates:** `make check` = lint + check-rules + type-ratchet + check-harness + test-cov(80%). Demo work also runs `make test-demo`. New code: TDD (failing test first), CLAUDE.md OCP add-by-new-file, layers, 300-line/40-line, prompts-in-YAML, Pydantic boundaries.
- **Phase 0 demo-repair DONE** (2026-06-05): engines-500 double-serialize, pledges path drift, embedding offload, WS timeout 120s, trade empty-item_type. EXP-00c (CI smoke) deferred (stop-and-ask for CI config).
- **Pattern — offload CPU on the event loop:** sync model inference via `await asyncio.to_thread(...)` (embeddings done). REUSE for cross-encoder reranker (ISSUE-064) and any new sync ML call.
- **EXP-30 DONE (KEYSTONE):** `ContextItem.pinned: bool` now exists (`context_merger.py`). Pinned-core + ranked-pool policy live in BOTH enforcement paths. `EXP-17` `never_forget` mirrors this convention. EXP-32, EXP-81, EXP-11, EXP-53 now unblocked (Tier-A overflow no longer raises for knowledge-rich NPCs).
- **EXP-50 DONE:** `Standing` enum + `derive_standing` in `engines/relationship/standing.py`; `GET /v1/npc/{id}/relationship/{other_id}` route live; `RelationReader` in `graph/relation_reader.py`. Consumer refactor (gossip gate, dialogue tone) is the next slice — wire using `Standing` import.
- **EXP-31 DONE:** `evals/retrieval_runner.py` + 20 labeled demo-world cases in `evals/cases/retrieval_demo.json`; `make eval-retrieval` target live. EXP-32 still needs Q&A label set; run `make eval-retrieval` to see baseline precision@5/recall@5/MRR before EXP-32.
- **EXP-83 DONE:** `demo_game/quickstart.py` + `make hello` live. Standalone 177-line httpx-only seeder+dialogue script.
- **EXP-84 DONE:** Gossip chain CHAIN tab now shows distortion-type badges ([EXAGGERATION] etc.) per hop.
- **EXP-85 DONE:** `AntiHallucinationBeat` scripted beat in `run_scenes.py`; asks `aldric_merchant` about war, confirms 0 KNOWS_ABOUT edges. Registered as ACT 8 in SCENES.
- **EXP-93 DONE:** BribeScene now uses `adjust_npc_reputation` (HAS_REPUTATION_WITH). ISSUE-060 and ISSUE-066 closed.
- **EXP-81 DONE:** `RemembersYouBeat` in `demo_game/remembers_you_beat.py`; ACT 9 added to `run.py`. `get_npc_relationship` in `client.py` (added by orchestrator pre-dispatch).
- **EXP-91 DONE:** `RelationTicker` in `demo_game/ui/relation_ticker.py`; trust/fear/affection delta overlay in `game_window.py`. TTL=4s polling, best-effort (swallows errors). game_window.py now 337 lines (under DEC-074 ceiling of 350).
- **EXP-11 DONE:** `player_relation` ContextItem in context_builder.py Tier-A (key `"relation:player"`, priority=88, non-pinned). Uses `get_npc_player_edge`. context_builder.py now 446 lines (DEC-073 waiver updated). Potential key collision with subgraph_retriever logged as ISSUE-070.
- **EXP-80 DONE:** `demo_game/sandbox_loop.py` + S-key toggle in `GameWindow`. Pre-existing `test_game_window.py` layout failures (ISSUE-068) not introduced by this batch.
- **DEC-070/072/071 still apply.** DEC-073: `context_builder.py` 446-line waiver (up from 323). DEC-074: `game_window.py` 337-line (under 350 ceiling).
- **Schema/DECISIONS-gated (DROP from parallel batches):** EXP-51, EXP-17-full, EXP-87, EXP-53. EXP-55 deferred.
- **Open residuals:** ISSUE-064 (reranker sync-on-loop), ISSUE-068 (test_game_window.py WorldStatePoller), ISSUE-069 (action_workers catch scope), ISSUE-070 (relation:player key collision). Next ISSUE id: **ISSUE-071**.

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
- [ ] **EXP-17** — salience forgetting curve (first slice: charge-weighted decay) · M · deps: EXP-30 · full version `🔶`
- [ ] **EXP-15** — distortion-strategy registry (open L7-01 if-chain) · M · deps: none · refactor `gossip_distort.py`
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
- [ ] **EXP-52** — personal reputation propagation engine · M · deps: EXP-50
- [ ] **EXP-13** — `EmotionModelProtocol` + personality modulation · M · deps: none · refactor `emotion_updater.py`
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

**EXP-15, EXP-32 (soft), EXP-17 (first slice only), EXP-13** — candidates from Phase 2/3:
- EXP-15: refactor `gossip_distort.py` open L7-01 if-chain → distortion-strategy registry. New file `engines/gossip/distortion_registry.py` + edits `gossip_distort.py`. No schema change.
- EXP-32: measured anti-hallucination eval (new eval files only; deps EXP-30 done, needs Q&A label set — drop if not authored yet).
- EXP-17 (first slice — charge-weighted decay only, NOT the full schema-gated version): edit `retrieval/` decay logic only; no new node/edge. Confirm the brief restricts scope to the non-gated slice.
- EXP-13: `EmotionModelProtocol` + personality modulation — refactor `emotion_updater.py`. No schema change, new protocol file.

**Conflicts to verify before dispatch:** EXP-15 and EXP-17 both touch `retrieval/` adjacently — confirm disjoint files. EXP-13 edits `emotion_updater.py` only.

**Drop from this batch:** EXP-32 if Q&A label set is not ready. EXP-17 full version (schema-gated).

EXP-32 can run once Q&A label set is authored (see `EXP32_EVAL_QA_TASK.md`).
