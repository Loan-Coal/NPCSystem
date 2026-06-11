# NPCSystem — Engine Roadmap

**Status:** Phases 0–26 complete + a prior /expand-parallel expansion backlog (legacy EXP-10..57)
largely shipped. This file's "Next" section is the **forward** plan from the 2026-06-11 expansion
analysis, reconciled against code (10 re-proposed items were already built and dropped).

## Archive (completed history)

| Range | Where |
|-------|-------|
| Phases 0–13 (+ engine audit, session log → S13.3) | `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 (proactive dialogue, retrieval evals, moderation, API exit contract, arch-debt drain, runtime correctness, P3 sweep, eval fixtures, temporal framing, voice polish) + full session log | `project-harness/archive/ROADMAP_phase14-26_2026-06-11.md` |
| 2026-06-01 Munich hackathon roadmap | `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md` |
| 2026-06-03 codebase review (BLOCK, 43 findings) — remediation backlog, now drained across Phases 20–26 | `project-harness/archive/review-2026-06-03/` |
| Legacy expansion backlog (EXP-10..57, KE-6) — prior `/expand-parallel` program | `project-harness/expansion/EXPANSION_INDEX.md` (history section) |

---

## Next — Expansion program (2026-06-11 EXPANSION_ANALYSIS, reconciled)

> Source: `project-harness/expansion/EXPANSION_ROADMAP.md`; mini-specs in `ENGINE_GAPS.md` /
> `NEW_ENGINES.md` / `DEMO_EXPANSIONS.md`; seams in `FEASIBILITY.md`; granted decisions DEC-097..104.
> **Reconciliation:** the analysis was run without the prior execution backlog and re-proposed shipped
> work; a code-grounded verification dropped 10 already-built items and renumbered the real remainder
> to **EXP-201..230** (collision-free with the legacy EXP-10..57 scheme). Mapping + per-item deps live
> in `project-harness/expansion/EXPANSION_INDEX.md` (the execution driver).
> **Throughline:** the simulation computes correctly but is invisible to the dialogue layer and the
> buyer — most work is connective (wire computed state into what the player sees and the LLM reads).
> **Execution:** `/expand-parallel` autonomous loop — see `project-harness/expansion/OVERNIGHT_LOOP.md`.

### Phase A — "Make it visible" (no schema)
- **Goal:** connect computed engine state to player + buyer; turn the scripted demo into a recordable pitch.
- **Effort:** ~1 session · **Leverages:** relationship/reputation engines (wired), parsed-but-unrendered demo data.
- **Constraints:** demo is a pure REST/WS client (zero `src/` imports); no graph schema change.
- [x] **EXP-201** relationship affinity phase engine (slice 1: `derive_phase` + `relation_phase_writer`, new files; unit tests green, a397661). Slice-2 call-site wiring in `dialogue_handler.py` deferred.
- [ ] **EXP-202** standing → dialogue tone + secret-share gate. Exit: dialogue prompt reflects Standing; gate test green.
- [x] **EXP-203** relation-delta first-contact fix (creates edge instead of swallowing error; f511d42). first-contact delta persists; regression test green.
- [x] **EXP-204** need fed into dialogue context (slice 1; DEC-099; e0ec882). Top unmet need surfaces as optional Tier-B item; mood slice 2 deferred.
- [ ] **EXP-205** proactive dialogue act in scripted runner (demo). Exit: ACT-11 NPC-initiated beat plays.
- [x] **EXP-206** temporal memory readout (demo; 62975ea). Memory panel shows occurred_at + historical marker.
- [ ] **EXP-207** facial-expression glyph rendering (demo). Exit: portrait zone renders glyph from parsed field.

### Phase B — "Prove the moat"
- **Goal:** surface the (already-built) anti-hallucination + retrieval evals to the buyer.
- **Effort:** ~0.5 session · **Notes:** EXP-31/32 eval runners already shipped; only the demo panel remains.
- [ ] **EXP-208** retrieval-explainer panel (demo) — wraps live `GET /admin/debug/retrieval`. Exit: RETRIEVAL tab shows why each line was grounded.

### Phase C — "Close the agentic loop" (schema: DEC-097/098)
- **Goal:** NPCs act on their own state and reach the player; memory becomes player-scoped + decaying.
- **Effort:** ~1.5 sessions · **Leverages:** ProactiveDialogue/IntentFormation engines (wired but undelivered), `push_proactive_line()` helper.
- **Constraints:** DEC-098 (scheduler→api queue), DEC-097 (memory.yaml fields). Orchestrator applies schema before the batch. EXP-211 + EXP-212 share `memory.yaml`/`memory_engine.py`/`context_builder.py` → one worker.
- [ ] **EXP-209** unified proactive-trigger surface (memory+need+event). Exit: trigger router emits intents; test green.
- [ ] **EXP-210** proactive line delivered over WS to idle player (DEC-098 queue). Exit: idle player receives NPC-initiated line.
- [ ] **EXP-211** player-scoped memory recall in dialogue (DEC-097 `subject_player_id`). Exit: player-specific memory surfaces in context.
- [ ] **EXP-212** salience-weighted forgetting curve (DEC-097 `recall_count`/`never_forget`). Exit: low-salience memories decay; pinned never forget.

### Phase D — "Deepen the systems" (schema: DEC-100/101)
- **Goal:** richer gossip drift, interactive economy, visible politics, more game.
- **Effort:** ~2 sessions · **Leverages:** distortion registry, NegotiationStore, location PART_OF (fixed).
- **Constraints:** EXP-223 needs faction-count review in `game_end_checker.py`; EXP-207 & EXP-221 both edit `left_panel.py` (one worker); EXP-205 & EXP-222 both edit `run.py` (one worker).
- [ ] **EXP-213** belief/confidence-aware distortion routing. Exit: receiver confidence biases distortion type.
- [ ] **EXP-214** commitment/fact memory formation (DEC-100 `Memory.kind`). Exit: promises form retrievable memories.
- [ ] **EXP-215** belief contradiction detection + dedup. Exit: contradictory learned beliefs flagged/merged.
- [ ] **EXP-216** trade dispatch → NegotiationStore (PARTIAL: wire `NegotiationBackedSyncTradeHandler` default). Exit: propose_trade opens a negotiation session.
- [ ] **EXP-217** player-observable event summary endpoint. Exit: `GET` returns recent events; route test green.
- [ ] **EXP-218** quest branching on player choice (DEC-101 `unlocks.on_choice_id`). Exit: choice selects successor quest.
- [ ] **EXP-219** personality-modulated emotion model (2nd `EmotionModelProtocol` impl). Exit: trait-driven emotion deltas; test green.
- [ ] **EXP-220** faction standing board (demo). Exit: FACTION tab shows standings.
- [ ] **EXP-221** location hierarchy breadcrumb (demo). Exit: panel shows PART_OF chain.
- [ ] **EXP-222** cinematic / recording mode (demo; needs EXP-205). Exit: `--cinematic` produces formatted run.
- [ ] **EXP-223** richer world (more NPCs/locations; resolve faction-count first). Exit: seed adds NPCs/locations idempotently.
- [ ] **EXP-224** mood-contagion visualiser (demo). Exit: emotion panel shows contagion across a pair.
- [ ] **EXP-225** proactive window surface (demo PARTIAL: NPC highlight + input pre-fill). Exit: intent NPC highlighted, input pre-filled.

### Phase E — "Emergent cognition" (flagship; schema: DEC-102/103/104)
- **Goal:** NPCs that model the player, hold/act on false beliefs, and pursue multi-step covert goals.
- **Effort:** ~3+ sessions · **Leverages:** relationship phase (EXP-201), knowledge_extraction, events/story_pacing.
- **Constraints:** new node/edge types applied just-in-time by orchestrator (DEC-102/103/104); EXP-228 requires the anti-hallucination eval to treat `is_deception=true` as intended; EXP-229 revives `investigation` for detection. STOP + surface if the type-registry gate can't be made green.
- [ ] **EXP-226** player-model / theory-of-mind engine (DEC-102 player_model node+edge). Exit: per-player belief node written + readable.
- [ ] **EXP-227** player-aware drama director engine. Exit: director injects a beat on plateau/idle.
- [ ] **EXP-228** NPC deception / false-belief engine (DEC-103 believes deception fields). Exit: NPC holds a flagged false belief; eval treats it as intended.
- [ ] **EXP-229** long-horizon covert scheming engine (DEC-104 scheme node+edges). Exit: a 2-step scheme advances across ticks.
- [ ] **EXP-230** session history persisted across restart (SESSION_TURNS). Exit: session survives a restart.

### Already shipped — dropped from this program (verified in code 2026-06-11)
EXP-14 (emotion persistence, write-through), EXP-20-equiv (world-state quest triggers wired),
analysis EXP-93 (ISSUE-060 bribe fix — `adjust_npc_reputation` already in `run_scenes.py:242`),
EXP-72 (gossip distortion diff — `gossip_chain.py:128`), EXP-76 (degradation label), EXP-78 (relation
ticker), EXP-31/32 (retrieval + anti-hallucination eval runners), EXP-15 (distortion prompts YAML),
EXP-95 (scenario picker), plus EXP-80/81/85/92 demo beats.

---

## Parked backlog (carried forward, not active)

- [ ] **S17.9** — Legacy niche-engine expansions + demo integration (succession, clique, investigation,
  skill, military, treaty). Low commercial value; kept in code, no active dev. (NB: `investigation` is
  revived inside EXP-229's detection half.)
- [ ] **S21.6** — File-size rule cluster, `demo_game/` scope (`client.py` 1524L, `seed.py` 1265L,
  `run.py`, `run_scenes.py`, `game_controller.py`, `ui/*`, `scenarios/*`). Demo code, high split
  risk, low value; several already waived (DEC-029/032/034/049/074/075).
- [ ] **Phase X — Engine SDKs (Unity / Unreal)** — DEFERRED COMMERCIAL MILESTONE. Drop-in plugins
  wrapping the REST/WS API; highest commercial ROI but its own 8+ session milestone, sequenced after
  the OpenAPI contract is frozen. See OPEN_QUESTIONS OQ-13 (start vs finish engine depth).
  - [ ] **SX.1** OpenAPI contract freeze + versioned client spec.
  - [ ] **SX.2** Unity C# package (REST + WS, auth, models).
  - [ ] **SX.3** Unreal plugin (parity).
  - [ ] **SX.4** Sample integration scene per engine + docs.

---

## Engine Scope Decisions (reference)

| Engine | Status | Decision |
|--------|--------|----------|
| gossip, emotion, need, mood, routine, agenda | works, ticks | Showcased (Phases 1, 6) |
| quest_generation, quest (lifecycle) | works | Showcased (Phases 2–3) |
| memory_consolidation | works | Showcased (S6.3 — headline feature) |
| chapter, story_pacing | works | Promoted to gameplay (Phase 7) |
| faction_politics, oath, treaty | complete | Completed + showcased (S2.3, S2.4, S6.2) |
| military | implemented | Implemented S6.5 (ISSUE-031) |
| reputation + gossip | works | Productized (Phase 8 networked reputation) |
| relationship, planning, knowledge_learning, economy/currency | works | Built in legacy EXP backlog (EXP-50/51/52/53/40) |
| secrets, leverage, pledges, beliefs | works | One consequence surfaced (S6.2) |
| succession, clique | works, niche | Graveyard — kept in code |
| investigation, skill | works, niche | Graveyard — investigation revived in EXP-229 |

---

## Testing Strategy (forward)

`make test` + `make test-demo` green before every merge. New work ships with tests.
`make check` (lint · check-rules · check-layers · check-docstrings · type · check-harness · test-cov ≥80%)
is the canonical health gate. Green as of Phase 25 completion (1967 passed, 22 skipped, 85.70% coverage).
