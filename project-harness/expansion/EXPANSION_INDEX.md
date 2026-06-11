# Expansion Index — NPC Engine (driver for `/expand-parallel`)

The execution backlog for the 2026-06-11 expansion program, **reconciled against code**. One
self-contained first-slice brief per item lives in `briefs/EXP-2NN-<slug>.md` (the orchestrator writes
any missing brief before dispatch, per skill §3). Full mini-specs in `ENGINE_GAPS.md` / `NEW_ENGINES.md`
/ `DEMO_EXPANSIONS.md` (legacy analysis ids); architecture verdicts in `FEASIBILITY.md`; sequencing in
`EXPANSION_ROADMAP.md`; granted decisions in `DECISIONS.md` DEC-097..104. Execute in dependency order;
same-phase non-conflicting items are parallelizable. Autonomous loop runbook: `OVERNIGHT_LOOP.md`.

`/expand-parallel` reads this file (incl. the Carry-forward block) to pick a conflict-free batch.
`/fix-next` and the review harness are NOT used here — this is feature work, not remediation.

## Carry-forward notes

_State that survives between expansion sessions so a fresh `/expand-parallel` run needn't rediscover it._
_The orchestrator maintains this: add a line when an item unlocks a later one; delete consumed lines._

- **Gate:** `make check` = lint · check-rules · check-layers · check-docstrings · type · check-harness ·
  test-cov(≥80%). Demo work also runs `make test-demo`. New code: TDD (failing test first), CLAUDE.md
  OCP add-by-new-file, layers, 300-line/40-line/3-nesting, prompts-in-YAML, Pydantic boundaries. All new
  `src/npc_engine/` files need module docstring with `Does NOT:` + `Dependencies injected:` (arch
  conformance test). Logger: `extra={...}` style. Edge YAML: `dst_type` is a single string.
- **Schema is orchestrator-only.** Workers must NOT add/edit a base node/edge or change schema — they
  STOP and report. The orchestrator applies the pre-approved schema (DEC-097/100/101/102/103/104)
  just-in-time before the batch that needs it, gates it, then dispatches workers to build against it.
- **Reconciliation (2026-06-11):** the fresh analysis re-proposed shipped work; code verification
  dropped 10 already-built items and renumbered the real 30 to **EXP-201..230** (collision-free with
  legacy EXP-10..57). See §Mapping. Legacy backlog history is at the bottom of this file.
- **Already-built seams to REUSE (do not rebuild):** `derive_standing()` in
  `engines/relationship/standing.py`; `push_proactive_line()` in `api/dialogue_ws.py:126`;
  `ProactiveDialogueEngine` + `IntentFormationEngine` (wired in scheduler, undelivered);
  `NegotiationBackedSyncTradeHandler` in `engines/interaction/trade_handler_sync.py:104` (built, unwired);
  distortion prompts in `prompts/gossip/distortion.yaml`; PART_OF edges seeded (`seed.py:450`); temporal
  memory fields on Memory nodes (Phase 26); `EmotionModelProtocol` (one impl `VadEmotionModel`).
- **WORKTREE BASE (critical for integration):** `isolation:worktree` forks from `worktree.baseRef`
  = `fresh` (origin/<default>), which is STALE vs local munich-demo (setup commits are unpushed). The
  EXP-201 worker that ran `git merge munich-demo` FIRST integrated cleanly; the two that didn't
  conflicted. **Every worker prompt MUST instruct: `git merge munich-demo` in the worktree before
  building.** (User could instead set `worktree.baseRef: head` in settings.local.json to remove the
  per-worker merge — orchestrator can't edit settings.) Integrate by cherry-picking the feature commit.
- **EXP-201 seam:** `engines/relationship/affinity_engine.py` (`RelationshipPhase` enum + pure
  `derive_phase`) + `graph/relation_phase_writer.py` (`write_relationship_phase(session,src,dst,phase:str,tick)`)
  → slice-2 wiring (call after relation mutation in `engines/dialogue/dialogue_handler.py`) is a small
  follow-up usable by EXP-202/227. The writer takes phase as **str** (pass `RelationshipPhase.value`).
- **MERGE-FIRST PROVEN (cycle 2):** with the mandatory `git merge munich-demo` first, all 3 edit-based
  workers cherry-picked clean. Keep mandating it every cycle. Integration may still surface gate issues
  (a new graph call must be mocked in EVERY test file that drives the caller — grep for the call site).
- **EXP-204 seam:** `get_needs_for_character` is now called in `context_builder.build_serialized_context`
  via `_maybe_append_top_need`; any new test exercising that builder must mock
  `context_builder.get_needs_for_character`. `ensure_relation_edge` now exists in `graph_writer.py` (EXP-203).
- **PHASE A COMPLETE** (EXP-201/202/203/204/205/206/207 all ✅). New seams: `prompt_builder_standing.py`
  (`build_standing_line`), `demo_game/proactive_dialogue_beat.py` (ACT-11 pattern), `EXPRESSION_GLYPHS`
  in left_panel. Deferred follow-ups: EXP-201 slice-2 wiring, EXP-202 secret-gate slice-2, EXP-207 live
  `set_facial_expression` wiring.
- **NEXT BATCH:** Phase B = EXP-208 (single demo item — retrieval-explainer panel). Then **Phase C**
  needs schema: orchestrator applies DEC-097 (memory.yaml fields) + DEC-098 (proactive queue) BEFORE
  dispatching EXP-209/210/211/212; EXP-211 + EXP-212 share memory.yaml/memory_engine/context_builder →
  ONE worker.

## Mapping & reconciliation (analysis id → execution id)

Verdicts from the 2026-06-11 code-grounded verification. **DONE** items are excluded from the checklist.

| exec id | analysis id | title | verdict | note |
|---------|-------------|-------|---------|------|
| EXP-201 | EXP-40 | relationship affinity phase engine | TODO | legacy EXP-40 was trade (done) — no relation to this |
| EXP-202 | EXP-22 | standing → dialogue tone + secret gate | TODO | uses existing `derive_standing()` |
| EXP-203 | EXP-12 | relation-delta first-contact fix | TODO | legacy EXP-12 `[x]` was wrong; bug live at `relation_mutator.py:53` |
| EXP-204 | EXP-34 | need/mood → dialogue context | TODO | DEC-099 |
| EXP-205 | EXP-70 | proactive act in scripted runner (demo) | TODO | engine done; scripted ACT-11 missing |
| EXP-206 | EXP-74 | temporal memory readout (demo) | TODO | fields exist, panel doesn't render them |
| EXP-207 | EXP-77 | facial-expression glyph (demo) | TODO | field parsed, not displayed |
| EXP-208 | EXP-71 | retrieval-explainer panel (demo) | TODO | route exists, no client method/tab |
| EXP-209 | EXP-10 | unified proactive-trigger surface | TODO | engines uncomposed |
| EXP-210 | EXP-35 | proactive WS delivery | TODO | DEC-098; helper exists |
| EXP-211 | EXP-11 | player-scoped memory recall | TODO | DEC-097; legacy `[x]` wrong |
| EXP-212 | EXP-17 | salience forgetting curve | TODO | DEC-097; legacy `[x]` wrong |
| EXP-213 | EXP-16 | belief-confidence distortion routing | TODO | legacy `[x]` wrong; still seed-mod |
| EXP-214 | EXP-18 | commitment/fact memory formation | TODO | DEC-100 |
| EXP-215 | EXP-36 | belief contradiction detection + dedup | TODO | engine docstring admits gap |
| EXP-216 | EXP-37 | trade dispatch → NegotiationStore | PARTIAL | wire default in `api/dependencies.py` |
| EXP-217 | EXP-38 | player-observable event endpoint | TODO | new route |
| EXP-218 | EXP-19 | quest branching on player choice | TODO | DEC-101; chain exists, `choose()`+field don't |
| EXP-219 | EXP-13 | personality-modulated emotion model | TODO | legacy `[x]` wrong; no 2nd impl |
| EXP-220 | EXP-73 | faction standing board (demo) | TODO | new tab |
| EXP-221 | EXP-75 | location hierarchy breadcrumb (demo) | TODO | edges seeded, no UI |
| EXP-222 | EXP-79 | cinematic / recording mode (demo) | TODO | needs EXP-205 |
| EXP-223 | EXP-87 | richer world (demo) | TODO | verify faction-count in `game_end_checker.py` |
| EXP-224 | EXP-89 | mood-contagion visualiser (demo) | TODO | single-NPC panel today |
| EXP-225 | EXP-82 | proactive window surface (demo) | PARTIAL | bubble exists; highlight+prefill missing |
| EXP-226 | EXP-41 | player-model / theory-of-mind engine | TODO | DEC-102 (new node+edge) |
| EXP-227 | EXP-42 | player-aware drama director engine | TODO | new engine dir |
| EXP-228 | EXP-43 | NPC deception / false-belief engine | TODO | DEC-103 |
| EXP-229 | EXP-44 | long-horizon covert scheming engine | TODO | DEC-104; revives investigation |
| EXP-230 | EXP-33 | session history persisted across restart | TODO | SESSION_TURNS |

**DONE (dropped):** EXP-93, EXP-72, EXP-76, EXP-78, EXP-32, EXP-31, EXP-15, EXP-95, EXP-20, EXP-14.

## Ordered checklist

Effort: S/M/L/XL · `🔶` = orchestrator applies pre-approved schema before this item's batch (DEC granted) ·
`⚠conflict` = shares an existing file with another item (group into one worker).

### Phase A — Make it visible (no schema)
- [x] **EXP-201** relationship affinity phase engine (slice 1: derive_phase + writer, new files) · S · DONE a397661 · slice-2 wiring (call `write_relationship_phase` after relation mutation in `dialogue_handler.py`) deferred — see carry-forward
- [x] **EXP-202** standing → dialogue tone (slice 1) · M · DONE 0ad8c02 · STANDING line via new `prompt_builder_standing.py` + system_v1 Rule 16; secret-share gate (gossip) = slice 2 deferred
- [x] **EXP-203** relation-delta first-contact fix · S · DONE f511d42 · `ensure_relation_edge` added to `graph_writer.py`
- [x] **EXP-204** need/mood → dialogue context (DEC-099) · S · DONE e0ec882 · slice 1 = needs (top unmet → Tier-B); mood slice 2 deferred
- [x] **EXP-205** proactive act in scripted runner (demo) · S · DONE 6007e04 · new `demo_game/proactive_dialogue_beat.py` (ACT 11) + run.py; uses `client.get_pending_intents`. (run.py still ⚠conflict EXP-222)
- [x] **EXP-206** temporal memory readout (demo) · S · DONE 62975ea · memory_panel renders occurred_at + historical marker
- [x] **EXP-207** facial-expression glyph (demo) · S · DONE ff126b4 · `EXPRESSION_GLYPHS` + glyph in left_panel; live wiring (`game_window.set_facial_expression`) is a follow-up. (left_panel still ⚠conflict EXP-221)

### Phase B — Prove the moat
- [ ] **EXP-208** retrieval-explainer panel (demo) · M · deps: none · new `demo_game/ui/retrieval_panel.py` + `EngineClient.get_retrieval_debug()` + `RightPanel.RETRIEVAL` tab

### Phase C — Close the agentic loop (🔶 DEC-097/098)
- [ ] **EXP-209** unified proactive-trigger surface · M · deps: none · new `engines/proactive_dialogue/trigger_router.py`
- [ ] **EXP-210** proactive WS delivery 🔶DEC-098 · S · deps: EXP-209 (soft) · new `engines/proactive_dialogue/proactive_queue.py`; edit `api/dialogue_ws.py`
- [ ] **EXP-211** player-scoped memory recall 🔶DEC-097 · M · deps: none · edit `memory.yaml`(orch), `engines/memory/memory_engine.py`, `retrieval/context_builder.py` ⚠conflict(EXP-212)
- [ ] **EXP-212** salience forgetting curve 🔶DEC-097 · M · deps: none · edit `memory.yaml`(orch), `engines/memory/memory_engine.py`, `retrieval/context_builder.py` ⚠conflict(EXP-211 — same worker)

### Phase D — Deepen the systems (🔶 DEC-100/101)
- [ ] **EXP-213** belief/confidence-aware distortion routing · M · deps: none · edit `engines/gossip/gossip_distort.py`, `gossip_handler.py`, `prompts/gossip/gossip_config.yaml`
- [ ] **EXP-214** commitment/fact memory formation 🔶DEC-100 · M · deps: none · edit `memory.yaml`(orch), `memory_engine.py`, `engines/quest/quest_lifecycle_engine.py`
- [ ] **EXP-215** belief contradiction detection + dedup · M · deps: none · new `graph/` reader; edit `engines/knowledge_learning/knowledge_extraction_engine.py`
- [ ] **EXP-216** trade dispatch → NegotiationStore (PARTIAL) · S · deps: none · edit `api/dependencies.py`
- [ ] **EXP-217** player event summary endpoint · S · deps: none · new `graph/event_queries.py` + `api/routes/player_events.py`
- [ ] **EXP-218** quest branching on player choice 🔶DEC-101 · L · deps: none · edit `unlocks.yaml`(orch), `engines/quest/quest_chain_resolver.py`, new route
- [ ] **EXP-219** personality-modulated emotion model · M · deps: none · new `engines/emotion/trait_modulated_model.py`
- [ ] **EXP-220** faction standing board (demo) · S · deps: none · new `EngineClient.get_faction_standings()` + UI tab
- [ ] **EXP-221** location hierarchy breadcrumb (demo) · S · deps: none · edit `demo_game/ui/left_panel.py` ⚠conflict(left_panel.py: EXP-207)
- [ ] **EXP-222** cinematic / recording mode (demo) · M · deps: EXP-205 (soft) · edit `demo_game/run.py` ⚠conflict(run.py: EXP-205)
- [ ] **EXP-223** richer world (demo) · M · deps: none · edit `demo_game/seed.py`, `constants.py`; verify `game_end_checker.py` faction-count first
- [ ] **EXP-224** mood-contagion visualiser (demo) · M · deps: none · edit `demo_game/ui/emotion_panel.py` + EmotionPoller
- [ ] **EXP-225** proactive window surface (demo PARTIAL) · S · deps: none · edit `demo_game/ui/game_window.py`

### Phase E — Emergent cognition (🔶 DEC-102/103/104; flagship, schema-heavy)
- [ ] **EXP-226** player-model / theory-of-mind engine 🔶DEC-102 · M · deps: none · new `base_nodes/player_model.yaml`+`base_edges/has_player_model.yaml`(orch) + `engines/player_model/`
- [ ] **EXP-227** player-aware drama director engine · M · deps: EXP-201 (soft) · new `engines/director/`
- [ ] **EXP-228** NPC deception / false-belief engine 🔶DEC-103 · L · deps: EXP-32(done, eval coupling) · edit `believes.yaml`(orch) + new `engines/deception/`
- [ ] **EXP-229** long-horizon covert scheming engine 🔶DEC-104 · XL · deps: EXP-228 · new `scheme.yaml`+2 edges(orch) + engine + revive `investigation`
- [ ] **EXP-230** session history persisted across restart · M · deps: none · edit `engines/dialogue/session_store.py` + lifespan hooks

## Next candidate batch (suggested)

**LAST BATCH (cycle 3):** EXP-202 ✅ · EXP-205 ✅ · EXP-207 ✅ — integrated (0ad8c02/6007e04/ff126b4 +
fix 32adae2), gate green (make check 1985, demo 644). **Phase A COMPLETE.**
**NEXT:** Phase B = EXP-208 (retrieval-explainer panel, demo, solo). Then Phase C (apply DEC-097/098 schema first).
**All workers must `git merge munich-demo` before building.**

---

## Legacy backlog history (prior /expand-parallel program — for reference only)

The legacy EXP-10..57 / KE-6 program (Phases 0–4, batches through 2026-06-10) shipped relationship
(EXP-50), GOAP planning (EXP-51), reputation propagation (EXP-52), knowledge learning (EXP-53), trade
dispatch (EXP-40), proactive engine wiring (EXP-10), persistent emotion (EXP-14), branching-chain
scaffold (EXP-19), location hierarchy (EXP-87/KE-6), and most demo beats (EXP-80/81/84/85/91/92/93/95).
Those `[x]` items and their briefs remain in `briefs/`. The 2026-06-11 verification found several legacy
`[x]` marks were optimistic (EXP-11/12/13/16/17/19 had unbuilt residual slices) — those residuals are
captured as EXP-201..230 above. Do not re-open the legacy ids; work the EXP-2xx set.
