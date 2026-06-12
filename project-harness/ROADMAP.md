# NPCSystem — Engine Roadmap

**Status:** Phases 0–26 complete; the 2026-06-11→12 expansion program (EXP-201..230) is **fully shipped**
(slice-1 of each item — engines/models/graph/demo surfaces built + tested, `make check` 2062 / 86.18%).
Many engines, however, are **built but dormant** (not wired into the tick loop / composition root, and
not exposed via a REST/WS route the demo can reach). This file's **"Next"** section is the slice-2 plan:
**Phase F activates + exposes the engines** so the demo can use them, **Phase G surfaces them** in the demo,
and **Phase H expands the demo into a game** (economy depth, content/branching, legacy gameplay engines) on
top of those APIs. Overnight execution driver: `project-harness/DEMO_BUILD_LOOP.md` (looped `/expand-parallel`).

## Archive (completed history)

| Range | Where |
|-------|-------|
| Phases 0–13 (+ engine audit, session log → S13.3) | `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 (proactive dialogue, retrieval evals, moderation, API exit contract, arch-debt drain, runtime correctness, P3 sweep, eval fixtures, temporal framing, voice polish) + full session log | `project-harness/archive/ROADMAP_phase14-26_2026-06-11.md` |
| 2026-06-01 Munich hackathon roadmap | `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md` |
| 2026-06-03 codebase review (BLOCK, 43 findings) — remediation backlog, now drained across Phases 20–26 | `project-harness/archive/review-2026-06-03/` |
| Legacy expansion backlog (EXP-10..57, KE-6) — prior `/expand-parallel` program | `project-harness/expansion/EXPANSION_INDEX.md` (history section) |

---

## Next — Slice-2: activate engines (Phase F) → surface them (Phase G) → make it a game (Phase H)

> The Phase A–E program built each capability as a **slice 1** (engine logic + graph + tests, mostly
> new-file-add) but deliberately deferred the **wiring** (scheduler tick / composition-root injection /
> WS delivery) and the **API read routes**. The demo is a pure REST/WS client (zero `src/` imports), so a
> built engine is only usable by the demo once it (a) **runs** in the live system and (b) is **reachable**
> via a route. **Phase F closes both gaps; Phase G then builds the demo on top.** Deferred-item source:
> `project-harness/expansion/OVERNIGHT_LOOP.md` §Deferred follow-ups. Driver for execution: `/expand-next`
> (or `/expand-parallel` for the conflict-free wiring/route batches).
> **Sequencing rule:** F → G → H. Every G step depends on an F route/wiring it surfaces; Phase H consumes the
> F routes (plus four small H0 legacy enablers) and is otherwise pure demo-side. The demo-expansion analysis
> behind Phase H lives in `project-harness/demo-expansion/` (see its `RECONCILIATION.md` for what the
> EXP-201..230 program changed under it). H1 (economy) and H2 (content) are mostly type-A and can start
> before H0/H3; H3 (legacy-engine panels) waits on its H0 enabler.

### Phase F — Activate & expose (engine wiring + API routes)
- **Goal:** every built-but-dormant Phase A–E engine **runs** in the tick loop / composition root **and**
  is **reachable** by the demo via a REST/WS route. Exit-of-phase: the demo client can observe, for a live
  NPC, its relationship phase, the NPC's model of the player, active schemes, director beats, and receive
  proactive lines over WS.
- **Effort:** ~3 sessions · **Leverages:** `api/dependencies_engines.py` (scheduler composition root — already
  wires proactive + reputation engines), the tick scheduler, `dialogue_ws.push_proactive_line` (exists),
  `engines/relationship/standing.py`.
- **Constraints:** DIP — all wiring through `api/dependencies.py` / `dependencies_engines.py` (sole composition
  roots); `scheduler→api` delivery uses the DEC-098 in-process queue (no upward import); the new
  F3.5 `dialogue_turn` node + edge needs a fresh `DECISIONS.md` entry before it lands; routes are additive (auth on all).

#### F1 — Tick & composition-root wiring (make the engines actually run)
- [x] **F1.1 (EXP-201 s2)** — call `write_relationship_phase` after the relation delta in `dialogue_handler`. Exit: a phase transition is persisted during a live dialogue turn (integration test).
- [x] **F1.2 (EXP-209+210 s2)** — wire `trigger_router` into the tick scheduler (form proactive intents from memory/need/event) **and drain `ProactiveQueue` → `push_proactive_line`** over the dialogue WS. Exit: an idle connected player receives an NPC-initiated line end-to-end (WS integration test). *(memory source live; need/event are a clean router seam, deferred — ISSUE-094.)*
- [x] **F1.3 (EXP-219 s2)** — inject `TraitModulatedEmotionModel` into `EmotionUpdater` via the composition root (config-selectable vs `VadEmotionModel`). Exit: emotion deltas are trait-modulated in a live tick. *(global demo-default traits via `build_emotion_model`; per-NPC trait fetch deferred — ISSUE-096.)*
- [x] **F1.4 (EXP-226 s2)** — wire `PlayerModelEngine` into the scheduler (update each NPC's model of the player per tick window). Exit: `player_model` nodes update on tick (integration test). *(`PlayerModelTick` over co-located pairs; new scheduler slot + composition wiring.)*
- [x] **F1.5 (EXP-227 s2)** — wire the drama `director` into the scheduler (evaluate `decide()` on idle/plateau; emit the beat via the events engine). Exit: the director injects a beat during a live idle run. *(`DirectorTick` gates `EventHandler.run_tick` on `decide()`; idle + HOSTILE paths live; plateau-tick tracking deferred — ISSUE-097.)*
- [ ] **F1.6 (EXP-229 s2)** — wire `SchemingEngine` into the scheduler (advance active scheme steps per tick) + **detection** by reviving `engines/investigation` (discover schemes). Exit: a scheme advances a step across ticks and an investigating NPC can surface it. **⏸ DEFERRED — needs design call (DEC-107 / ISSUE-099): per-tick `add_scheme_step` MERGEs an invalid bare Event; how schemes manifest per tick is a human decision. Blocks F2.3 + G2.2 only.**
- [x] **F1.7 (EXP-212 s2)** — add a forgetting-decay tick that prunes/decays `is_forgettable` non-pinned memories on a schedule. Exit: low-salience memories decay over ticks (integration test). *(`MemoryDecayTick` self-gates on `MEMORY_DECAY_TICK_INTERVAL`, charge-weighted decay; batch-pruning/deletion deferred — decay satisfies the exit.)*

#### F2 — API read surfaces (so the demo can SEE the new state)
- [x] **F2.1** — `GET` relationship **phase** for an NPC↔player (extend `routes/relationship.py`, which today returns only standing). Exit: route returns `relationship_phase` + `phase_started_at_tick`. *(via `get_relation_phase_row`; also fixed the route's latent `response_model` envelope mismatch.)*
- [x] **F2.2 (EXP-226)** — `GET` player-model (the NPC's model of the player) via a new `routes/player_model.py`. Exit: route returns perceived_trust/intent for (npc, player). *(`GET /npc/{npc_id}/player-model/{player_id}`, reads F1.4 PlayerModel nodes.)*
- [ ] **F2.3 (EXP-229)** — `GET` active schemes for an NPC (+ discovered flag) via a new `routes/schemes.py`. Exit: route returns the NPC's active schemes + steps.
- [x] **F2.4 (EXP-209/227)** — confirm/add the proactive **pending-intents** route (`GET /v1/dialogue/pending`) and a director-beat read. Exit: the demo client can poll pending NPC-initiated intents + recent director beats. *(pending route already existed — confirmed; added `DirectorBeatLog` + non-destructive `GET /v1/dialogue/director-beats`.)*
- [x] **F2.5 (EXP-228, optional)** — read surface that marks `is_deception=true` beliefs (for the buyer-facing "tell"). Exit: a route/flag distinguishes deception beliefs without leaking them as truth. *(beliefs read now returns the `is_deception` edge flag; content unchanged.)*

#### F3 — Engine correctness & cleanup (so the activated engines behave well)
- [ ] **F3.1 (EXP-202 s2)** — replace the random `SECRET_BASE_PROBABILITY` gossip secret-share gate with a `Standing` threshold (gate secret-sharing by standing). Exit: secret-share probability tracks standing band.
- [ ] **F3.2 (EXP-204 s2)** — surface NPC **mood** (canonical `EmotionStore`, DEC-099) into the dialogue context (needs already surfaced). Exit: dialogue context carries a mood line.
- [ ] **F3.3 (EXP-228 s2)** — wire `classify_deception_belief` into the **live** anti-hallucination eval loop (`_classify_case`). Exit: a planted `is_deception` belief is not scored as a hallucination failure, while ordinary unsupported claims still are.
- [x] **F3.4 (EXP-214 cleanup)** — DI-inject `MemoryEngine` into `quest_lifecycle_engine` via the composition root (remove the `__init__` instantiation). Exit: no module-level engine instantiation; `make check` green. *(injected via `get_memory_engine()` singleton; default-fallback keeps direct callers working.)*
- [ ] **F3.5 (EXP-230 s2)** — migrate session persistence from the current JSON-blob-on-Character-property to a **first-class `dialogue_turn` node** carrying the *existing* temporal convention (`occurred_at_game_time` + integer `tick`, same fields events/memories use), anchored to the NPC and player. Fixes the `player_id` property-key collision (OQ-9), removes per-player property sprawl, and makes turns queryable/orderable/prunable (keep-last-N by deleting oldest `tick`). Add an index on `(npc_id, player_id, tick)`. **Needs a DECISIONS entry (new node type + edge).** Exit: turns persist as `dialogue_turn` nodes ordered by `tick`; distinct player ids never collide; `SessionStore` round-trips via the nodes on restart. *(NB: a unified reified `GameTime` node — time-as-a-node that events/memories/turns all link to — is intentionally NOT this task; it is a separate, repo-wide architecture decision, valuable only if cross-entity temporal correlation becomes a feature, and must be bucketed (per-day) to avoid supernodes. Do not couple it to session persistence.)*
- [ ] **F3.6 (EXP-217 seed)** — seed player `KNOWS_ABOUT` edges so `GET /player/{id}/events` returns data for the demo player. Exit: the player-events endpoint returns seeded events on a fresh `make demo-seed`.

### Phase G — Demo expansion (use the now-live engines)
- **Goal:** surface the activated engines in the pygame demo — connect the built-but-static panels to live
  data, add new panels/beats for the cognition layer, and add an "intrigue" scenario that exercises
  deception + scheming + player-model. This is the recordable, sells-the-engine demo.
- **Effort:** ~2.5 sessions · **Leverages:** the F2 routes, existing panels (`RetrievalPanel`, `FactionBoard`,
  `RightPanel` tabs), `EngineClient`, the scripted runner + interactive window.
- **Constraints:** pure demo-side (zero `src/` imports); each G step consumes an F2 route (do not start a G
  step whose route isn't live); demo file-size waivers apply (DEC-029/032/034/036/049/074/075/105).

#### G1 — Connect built-but-static surfaces to live data
- [ ] **G1.1 (EXP-207 s2)** — live-wire the facial-expression glyph (window updates `left_panel` per dialogue turn). Exit: glyph updates live during play.
- [ ] **G1.2 (EXP-208 s2)** — retrieval-explainer poller (auto-refresh the RETRIEVAL panel each turn via `get_retrieval_debug`). Exit: panel updates live.
- [ ] **G1.3 (EXP-221 s2)** — render the PART_OF location breadcrumb in the live window draw loop. Exit: breadcrumb shows for nested locations live.
- [ ] **G1.4 (EXP-201)** — show relationship **phase** (per NPC) in the relationship/left panel via F2.1. Exit: the NPC's phase is visible and updates.

#### G2 — New demo surfaces for the cognition engines (need F2 routes)
- [ ] **G2.1 (EXP-226)** — "What they think of YOU" player-model panel (via F2.2). Exit: panel shows the focused NPC's perceived_trust/intent.
- [ ] **G2.2 (EXP-229)** — intrigue/scheme board: active NPC schemes + steps, hidden vs discovered (via F2.3). Exit: schemes render; discovery flips a step's state.
- [ ] **G2.3 (EXP-227)** — surface director beats (a "something stirs" cue when the director injects) (via F2.4). Exit: an injected beat shows in the window.
- [ ] **G2.4 (EXP-209/210)** — proactive dialogue in the **interactive** window end-to-end (NPC hails the player live over WS; highlight + prefill already built in EXP-225). Exit: an idle player is hailed live in the window.
- [ ] **G2.5 (EXP-228)** — deception "tell" affordance: a subtle buyer-facing reveal when an NPC states a flagged false belief (via F2.5). Exit: the demo can reveal a deception without breaking the in-fiction illusion.

#### G3 — Content & scenarios that exercise the new layer
- [ ] **G3.1** — a scripted **"Intrigue"** scenario (new `demo_game/scenarios/`) that drives deception + scheming + player-model into one recordable arc (works under `--cinematic`). Exit: `make demo-run` plays the intrigue arc end-to-end.
- [ ] **G3.2** — seed enrichment so the new panels have data on first run (scheme seeds, KNOWS_ABOUT from F3.6, a deception setup). Exit: panels are non-empty on a fresh `make demo-seed`.

### Phase H — Demo-game expansion (consume the APIs; make the demo a *game*)
- **Goal:** turn the demo from a tech-demo into a game — a multi-objective win/lose **economy**, more **content**
  with real **branching**, and the **legacy gameplay engines** (treaty/oath/investigation/chapter/story-pacing)
  that Phase G does not cover. Phase G surfaces the *cognition* layer; Phase H adds *economy + content + legacy*.
- **Effort:** ~3–4 sessions · **Leverages:** existing `EngineClient` (gold/quest/reputation/pledge methods),
  `game_end_checker.py`, the 14-tab `RightPanel` + poller framework, `seed.py` (KE-6 idempotent), EXP-218's
  `POST /quest/{id}/choose` route, EXP-223's 8-NPC/4-location world.
- **Source analysis:** `project-harness/demo-expansion/` (DEMO_INTENT/DORMANT_ENGINES/CONTENT_PLAN/ECONOMY_DEPTH/
  FEASIBILITY/DEMO_EXPANSION_ROADMAP/OPEN_QUESTIONS) + `RECONCILIATION.md`. Each H item cites its `DEMO-Dx` mini-spec.
- **Constraints:** pure demo-side (zero `src/` imports) **except** the named **H0** enablers; each demo item
  consumes an existing/F/H0 route; demo file-size waivers apply (DEC-029/032/034/036/049/074/075/105); the
  D3 `evaluate_game_end` rewrite must stay ≤40 lines / ≤3 nesting (extract `check_win_multi`/`compute_grade`).
- **Baseline (verified 2026-06-12):** `game_end_checker.py` still single-win (2/3 factions ≥ 50) + inert single-lose
  (`iron_legion`→`loc_guard_barracks`); world is 8 NPCs / 4 locations / 3 alliable factions.

#### H0 — Small legacy-engine enablers (engine-side; routes/client the demo needs that Phase F does not add)
> Engine work, tracked separately; orchestrator lands each before its H3 consumer. None need schema (DEC-free).
- [ ] **H0.1 (E-1, DEMO-D1-01)** — `EngineClient.break_pledge` wrapper over the existing `pledges.py:114` break endpoint. Exit: client can break a pledge; unblocks oath-break (H3.1).
- [ ] **H0.2 (E-2, DEMO-D1-02)** — `EngineClient.create_treaty`/`get_faction_treaties`/`break_treaty` over the existing `treaties.py` route (no route change). Exit: client can broker/list/break treaties; unblocks H3.2 + the treaty win path (H1.1).
- [ ] **H0.3 (E-3, DEMO-D1-03)** — new read-only `api/routes/investigations.py` (`GET`) over `investigation_engine.get_investigation_context` + `EngineClient.get_investigation`. Exit: client reads investigation context (alibi/contradiction half not covered by EXP-229 schemes). Reuse F2.3 `schemes.py` for the discovery half.
- [ ] **H0.4 (E-4, DEMO-D1-04)** — new read-only `api/routes/chapters.py` (`GET /chapters/current`) over `chapter_engine.get_current_chapter` + `EngineClient.get_current_chapter`. Exit: client reads the current chapter/act; unblocks H3.4.
- [ ] **H0.5 (DEMO-D2-06 dep)** — `EngineClient.post_quest_choice` wrapper over EXP-218's existing `POST /quest/{id}/choose`. Exit: the demo can resolve a quest branch choice; unblocks the branch primitive (H2.1).

#### H1 — Win/lose economy depth (Pillar 3 · mostly type-A · delta to `game_end_checker.py`)
- [ ] **H1.1 (DEMO-D3-01)** — multi-objective win: faction-standing **OR** wealth **OR** quest-chain (**OR** brokered treaty via H0.2). Exit: any one path triggers a win; faction/wealth/quest paths need no enabler.
- [ ] **H1.2 (DEMO-D3-02)** — currency win/lose axis (`WEALTH_WIN_THRESHOLD`; bankruptcy `BANKRUPTCY_LOSE_THRESHOLD` armed after gold was once positive) over `GoldPoller`. Exit: gold can win or lose the game.
- [ ] **H1.3 (DEMO-D3-03)** — faction tension/overreach: gains with one faction cost a rival via `adjust_npc_reputation` (`client.py:1414`) as a branch/quest effect (type-A; server-side auto-decrement deferred type-C). Exit: a rival penalty fires on a friendly action.
- [ ] **H1.4 (DEMO-D3-04)** — tick deadline pressure: relative `DEADLINE_TICKS` from a latched start tick via `get_clock_state().current_tick`. Exit: missing objectives by the deadline loses (needs auto-tick on).
- [ ] **H1.5 (DEMO-D3-05)** — ≥2 distinct reachable failure states (bankruptcy H1.2 + deadline H1.4 + an authored `CONTROLS` legion trigger via `upsert_edge`), with a `failure_reason` → `LOSE_SUBTITLES` end-card. Exit: the inert single-lose is replaced by ≥2 player-caused losses.
- [ ] **H1.6 (DEMO-D3-06)** — end-screen score/grade `compute_grade(...) → S/A/B/C` over the win axes. Exit: a graded end-card renders.

#### H2 — Content & branching (Pillar 2 · type-A · rebaselined from 8 NPC / 4 loc)
- [ ] **H2.1 (DEMO-D2-06)** — branch primitive: `branch_node.py` + `branch_state.py` + `branch_effects.py` (typed effects: belief/rep/world-state/quest, OCP one-file-per-effect) + `ui/branch_panel.py`, resolving choices over existing client methods + H0.5. Exit: a player choice forks outcomes in the running demo.
- [ ] **H2.2 (DEMO-D2-01)** — cast expansion 8→14 NPCs; split NPC data into `demo_game/seed_npc_data.py` (data-only) to respect the size rule. Exit: new NPCs seed idempotently (KE-6).
- [ ] **H2.3 (DEMO-D2-02)** — locations 4→7 + a district tier via `post_part_of` (`client.py:776`, already live). Exit: nested locations seed; breadcrumb shows them (EXP-221).
- [ ] **H2.4 (DEMO-D2-03)** — factions 3→5 alliable. Exit: two new factions seed with standings the economy can read.
- [ ] **H2.5 (DEMO-D2-04)** — quests ~6→18 across 6 chains over the full quest lifecycle (`post_quest_*`). Exit: chains are acceptable/completable and feed H1.1's quest-chain win path.
- [ ] **H2.6 (DEMO-D2-05)** — rival quest variants + a `GameController` accept-guard (can't accept opposing-faction quests simultaneously). Exit: accepting one rival quest locks the other.
- [ ] **H2.7 (DEMO-D2-08)** — promote Village/Tavern eval worlds to playable Free-Play: de-hardcode `game_end_checker` win/lose constants to be per-world. Exit: all three worlds are pickable + winnable.
- [ ] **H2.8 (DEMO-D2-07)** — replayable scenario forks: `BranchBeat` in scripted scenes (`scenarios/`) over H2.1, with a persisted `BranchState`. Exit: a scripted scenario replays to a different outcome.

#### H3 — Legacy gameplay-engine surfaces (Pillar 1 · consume H0 enablers)
- [ ] **H3.1 (DEMO-D1-01/D2-11)** — oath panel + `pledge_poller`: swear/list (type-A over `post_pledge`/`get_pledges_for_npc`) + break (H0.1) + an oath-driven betrayal arc (H2.1). Exit: the player swears, breaks, and the relationship turns.
- [ ] **H3.2 (DEMO-D1-02/D2-09)** — treaty board (H0.2): broker/break treaties between factions + a treaty-broker quest chain. Exit: a brokered treaty is a visible objective (feeds H1.1).
- [ ] **H3.3 (DEMO-D1-03)** — investigation "solve-the-crime" panel (H0.3 + F2.3 schemes): surface alibi/rumor contradictions + discovered schemes, each clue linking to its graph provenance. Exit: a crime is solvable from graph contradictions.
- [ ] **H3.4 (DEMO-D1-04/D2-10)** — chapter act/season banner (H0.4) + chapter-paced campaign (A-fallback: quest-count-driven banner if H0.4 slips). Exit: the current act renders and advances.
- [ ] **H3.5 (DEMO-D1-05)** — story-pacing tension HUD: render `max_event_severity`/`quest_generation_rate` (already persisted + returned by `get_world_state`, verified) as a pressure gauge. Exit: a live tension meter updates. (type-A, no enabler.)

#### Deferred (type-C — needs a `DECISIONS.md` call; not in the overnight set)
- [ ] **H-D1 (DEMO-D1-06b)** — engine military battle sim with a balanced player military verb (army strength + verb). See OPEN_QUESTIONS OQ-5.
- [ ] **H-D2 (DEMO-D3-03s)** — server-side automatic cross-faction standing decrement (emergent rival tension). See OPEN_QUESTIONS OQ-6.

---

## Completed ✅ — Expansion program (2026-06-11→12 · EXP-201..230, slice 1)

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
- [x] **EXP-202** standing → dialogue tone (slice 1; 0ad8c02). STANDING line in prompt + system_v1 tone rule; secret-share gate = slice 2 deferred.
- [x] **EXP-203** relation-delta first-contact fix (creates edge instead of swallowing error; f511d42). first-contact delta persists; regression test green.
- [x] **EXP-204** need fed into dialogue context (slice 1; DEC-099; e0ec882). Top unmet need surfaces as optional Tier-B item; mood slice 2 deferred.
- [x] **EXP-205** proactive dialogue act in scripted runner (demo; 6007e04). ACT-11 NPC-initiated beat plays.
- [x] **EXP-206** temporal memory readout (demo; 62975ea). Memory panel shows occurred_at + historical marker.
- [x] **EXP-207** facial-expression glyph rendering (demo; ff126b4). Portrait zone renders glyph; live wiring is a follow-up.

### Phase B — "Prove the moat"
- **Goal:** surface the (already-built) anti-hallucination + retrieval evals to the buyer.
- **Effort:** ~0.5 session · **Notes:** EXP-31/32 eval runners already shipped; only the demo panel remains.
- [x] **EXP-208** retrieval-explainer panel (demo; 1caaa04). RETRIEVAL tab renders retrieved items; live poller wiring is a follow-up.

### Phase C — "Close the agentic loop" (schema: DEC-097/098)
- **Goal:** NPCs act on their own state and reach the player; memory becomes player-scoped + decaying.
- **Effort:** ~1.5 sessions · **Leverages:** ProactiveDialogue/IntentFormation engines (wired but undelivered), `push_proactive_line()` helper.
- **Constraints:** DEC-098 (scheduler→api queue), DEC-097 (memory.yaml fields). Orchestrator applies schema before the batch. EXP-211 + EXP-212 share `memory.yaml`/`memory_engine.py`/`context_builder.py` → one worker.
- [x] **EXP-209** unified proactive-trigger surface (slice 1; dc18e67). `select_trigger` router; scheduler wiring = slice 2.
- [x] **EXP-210** proactive delivery queue (slice 1; e958799). `ProactiveQueue`; dialogue_ws drain = slice 2.
- [x] **EXP-211** player-scoped memory recall (c571ae7). `subject_player_id` + player-scoped reader surfaces memory in context.
- [x] **EXP-212** salience forgetting curve (c571ae7). `compute_salience`/`is_forgettable` + `MEMORY_FORGET_THRESHOLD`; decay sched = slice 2.

### Phase D — "Deepen the systems" (schema: DEC-100/101)
- **Goal:** richer gossip drift, interactive economy, visible politics, more game.
- **Effort:** ~2 sessions · **Leverages:** distortion registry, NegotiationStore, location PART_OF (fixed).
- **Constraints:** EXP-223 needs faction-count review in `game_end_checker.py`; EXP-207 & EXP-221 both edit `left_panel.py` (one worker); EXP-205 & EXP-222 both edit `run.py` (one worker).
- [x] **EXP-213** belief/confidence-aware distortion routing (7be05fe). Receiver confidence biases distortion type (deterministic).
- [x] **EXP-214** commitment memory formation (DEC-100; 0adc89f). Quest accept forms a kind=commitment memory.
- [x] **EXP-215** belief contradiction detection + dedup (2ac16eb). Duplicate/contradictory learned beliefs skipped pre-write.
- [x] **EXP-216** trade dispatch → NegotiationStore (fc56e75). Composition root wires NegotiationBacked default.
- [x] **EXP-217** player-observable event summary endpoint (42682f4). `GET /player/{id}/events` + reader + tests green.
- [x] **EXP-218** quest branching on player choice (DEC-101; d9b318a). `choose` + `POST /quest/{id}/choose`; null auto-unlocks.
- [x] **EXP-219** personality-modulated emotion model (6ca22af). `TraitModulatedEmotionModel` 2nd impl; wiring = slice 2.
- [x] **EXP-220** faction standing board (demo; 69f7c80). FACTION tab shows standings.
- [x] **EXP-221** location hierarchy breadcrumb (demo; 8e14e11). PART_OF breadcrumb builder; draw wiring = slice 2.
- [x] **EXP-222** cinematic / recording mode (demo; 6c69444). `--cinematic` formatted run; default unchanged.
- [x] **EXP-223** richer world (demo; 36bec00). +3 NPCs +1 location in existing factions; faction count intact.
- [x] **EXP-224** mood-contagion visualiser (demo; 5e1f230). Emotion panel shows a contagion pair (DEC-105 size waiver).
- [x] **EXP-225** proactive window surface (demo; c26c224). Intent NPC highlighted + input pre-filled.

### Phase E — "Emergent cognition" (flagship; schema: DEC-102/103/104)
- **Goal:** NPCs that model the player, hold/act on false beliefs, and pursue multi-step covert goals.
- **Effort:** ~3+ sessions · **Leverages:** relationship phase (EXP-201), knowledge_extraction, events/story_pacing.
- **Constraints:** new node/edge types applied just-in-time by orchestrator (DEC-102/103/104); EXP-228 requires the anti-hallucination eval to treat `is_deception=true` as intended; EXP-229 revives `investigation` for detection. STOP + surface if the type-registry gate can't be made green.
- [x] **EXP-226** player-model / theory-of-mind engine (DEC-102; 4148fef). player_model node upsert/read via HAS_PLAYER_MODEL; wiring = slice 2.
- [x] **EXP-227** player-aware drama director engine (7b0f1d9). `decide` injects a beat on idle/plateau/hostile; wiring = slice 2.
- [x] **EXP-228** NPC deception / false-belief engine (DEC-103; 3b42061). NPC plants a flagged false belief; eval has a deception carve-out (live wiring = slice 2).
- [x] **EXP-229** long-horizon covert scheming engine (DEC-104; f985fbe). Form/cap/advance a scheme via scheme node+edges; detection = slice 2.
- [x] **EXP-230** session history persisted across restart (c30df84). save/load_to_graph + lifespan hooks (best-effort); dedicated node = follow-up.

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
