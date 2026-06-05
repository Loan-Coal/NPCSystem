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
- **Phase 0 demo-repair DONE** (2026-06-05): engines-500 double-serialize (`system.py`), pledges path drift (`client.py`→`/v1/admin/pledges`), embedding `to_thread` offload (`embedding_index.py`), WS dialogue timeout 120s (`constants.py`), trade empty-`item_type` (`quest_trade_controller.py`). Demo is playable. Only EXP-00c (CI smoke test) remains in Phase 0.
- **Pattern — offload CPU on the event loop:** sync model inference must run via `await asyncio.to_thread(...)` (done for embeddings). REUSE for the cross-encoder reranker (ISSUE-064) and any new sync ML call.
- **Pattern — `pinned`/`never_forget` flag:** EXP-30 adds a `pinned: bool` on `ContextItem` (non-droppable core); EXP-17 adds `never_forget: bool` on Memory (plot-load-bearing). Same concept — use one shared convention across both.
- **DEC-070:** context = pinned-core + ranked pool (supersedes tier A/B/C). v1 orders the pool by `priority` only; relevance (`context_relevance_engine`/`context_scoring`) is the fast-follow. **DEC-072:** NPCs learn facts via a single-pass `learned_facts` field on the dialogue output → existing `BELIEVES` edge (+3 optional provenance fields on `believes.yaml`, approved); no `LEARNED_FROM` edge, no 2nd LLM pass; player-sourced facts are grounded; learned beliefs are gossipable; contradictions keep both + `CONTRADICTS`. **DEC-071:** `PART_OF` location edge + `location_writer.py` approved (EXP-87).
- **Affinity (EXP-50):** 5 bands on `standing = clamp(trust+affection−fear, −100, 100)` — HOSTILE[-100,-50) WARY[-50,-15) NEUTRAL[-15,15] FRIENDLY(15,50] ALLIED(50,100]; enum + named config cutoffs. Consumer refactor order: gossip secret-share gate first, then dialogue tone. First slice = `derive_standing` + read route (no consumer edit → conflict-free).
- **Player is a `character` node** (`seed.py`, `player_demo`, `is_player:true`). Reuse `relates_to`/`has_reputation_with`/`knows_about` with the player as endpoint — no `player_model` node now (EXP-55 deferred; second-order ToM via memories).
- **Eval metrics report-only** (no SLA gate). EXP-32/31 Q&A label-set authoring task: `expansion/EXP32_EVAL_QA_TASK.md` (recommend local Opus generation against the seed graph).
- **Schema/DECISIONS-gated (DROP from parallel batches until granted):** EXP-51 (`GOAL_TARGETS` edge), EXP-17-full (`Memory.salience/recall_count/never_forget` fields — first slice charge-weighted decay is NOT gated), EXP-87 (`PART_OF` — approved DEC-071 but coordinate the base-edge add). EXP-53 (`believes.yaml` +3 optional fields — approved DEC-072). EXP-55 deferred.
- **Open residuals (logged):** ISSUE-064 (reranker sync-on-loop), ISSUE-066 (2 pre-existing demo-worker test fails — bribe/spread-rumor clock fallback), ISSUE-067 deeper (engine should populate `negotiation_state.item_type` — ties to EXP-40). Next ISSUE id: **ISSUE-068**.

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
- [ ] **EXP-30** — context: pinned-core + ranked pool (DEC-070) · M · deps: none · KEYSTONE · edits `retrieval/context_builder.py`+`context_budget_enforcer.py`
- [ ] **EXP-50** — relationship/affinity engine (first slice: `derive_standing` + read route) · S · deps: none · new `engines/relationship/`
- [ ] **EXP-31** — retrieval precision@k/recall eval harness · M · deps: none · new eval files
- [ ] **EXP-83** — integrator hello-world quickstart · S · deps: none · new `demo_game/quickstart.py` + Makefile
- [ ] **EXP-32** — measured anti-hallucination eval · M · deps: EXP-30 (soft), Q&A label set · new eval files

### Phase 2 — Dialogue + Gossip showcase (the priority)
- [ ] **EXP-53** — dialogue-driven knowledge learning (`learned_facts`→`BELIEVES`, DEC-072) · M · deps: EXP-32 (soft) · `🔶` believes.yaml +3 fields (approved)
- [ ] **EXP-11** — player-scoped long-term memory recall in dialogue · M · deps: EXP-30
- [ ] **EXP-17** — salience forgetting curve (first slice: charge-weighted decay) · M · deps: EXP-30 · full version `🔶`
- [ ] **EXP-15** — distortion-strategy registry (open L7-01 if-chain) · M · deps: none · refactor `gossip_distort.py`
- [ ] **EXP-16** — belief/secret-selective, prompt-driven distortion · M · deps: EXP-15
- [ ] **EXP-81** — cross-session "remembers you" demo · M · deps: EXP-30
- [ ] **EXP-84** — gossip telephone-diff view (demo) · S · deps: EXP-15 (soft)
- [ ] **EXP-85** — anti-hallucination "I don't know" demo beat · S · deps: none
- [ ] **EXP-92** — determinism/replay toggle (demo) · M · deps: KE-6 stable-id seeding
- [ ] **EXP-91** — relationship-delta live ticker (demo) · S · deps: EXP-50
- [ ] **EXP-80** — free-play/sandbox mode (demo) · M · deps: none
- [ ] **EXP-93** — fix ISSUE-060 bribe → `HAS_REPUTATION_WITH` (demo) · S · deps: none
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

## First runnable parallel batch (suggested)
**EXP-30, EXP-50 (first slice), EXP-31, EXP-83** — four disjoint file sets (retrieval / new engine / eval / demo),
zero schema, zero shared existing files. Briefs written. EXP-32 follows once EXP-30 lands (shares the eval dir
with EXP-31 — sequence them, don't parallelize the two eval items).
