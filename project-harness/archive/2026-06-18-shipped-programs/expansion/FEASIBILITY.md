# NPC Engine Expansion — Architecture Feasibility Assessment (X3)

**Written:** 2026-06-11. Read-only analysis against `munich-demo` branch.
**Author lens:** X3 — Architecture & Feasibility Fit.
**Scope:** Every EXP-NN proposal from lenses X1 (EXP-10..EXP-38), X2 (EXP-40..EXP-44), and X4 (EXP-70..EXP-99). Assessed against the actual code seams verified during this review.

---

## Orientation Notes (Corrections to lens claims)

Several claims in X1 and X2 require correction based on direct code verification before the per-proposal table:

**EXP-21 (Reputation wiring) — already DONE.**
`get_reputation_engine()` exists in `src/npc_engine/api/dependencies_engines.py:314` and `get_tick_scheduler()` at line 388 passes `reputation_engine=get_reputation_engine()` to the `TickScheduler` constructor. `tick_scheduler.py:551` shows `self._reputation_engine.run_tick(...)` already wired into the tick loop. X1's claim that it is "not wired in this slice" is stale. This is no longer a gap — it is DONE.

**EXP-14 (Persistent emotion state) — already DONE.**
`EmotionBootstrapper` exists at `src/npc_engine/engines/emotion/emotion_bootstrap.py` and is called in `main.py:125` during the lifespan startup. `EmotionGraphWriter` exists at `graph/emotion_writer.py`. The emotion_bootstrap docstring still says "not yet connected" but the main.py evidence overrides it. This is functionally DONE (verify the write-through path is also wired — the updater's `EmotionGraphWriter` optional injection).

**EXP-40 (Relationship phase engine) — seam confirmed clean.**
`relates_to.yaml` at line 11–12 confirms `relationship_phase` and `phase_started_at_tick` exist with `required: false`. Zero Python files write to them (confirmed by grep). The seam is genuinely open for a new-file-add engine. X2 assessment confirmed accurate.

**EXP-15 (Gossip distortion YAML) — OCP registry confirmed clean but hardcoded strings persist.**
`STRATEGY_REGISTRY` in `distortion_strategy.py:47` is a proper OCP-clean dict. Each of the 4 strategy files (`omission.py`, `exaggeration.py`, `role_swap.py`, `timeline_shift.py`) implements the `DistortionStrategy` protocol. The registry itself does NOT need editing to add a 5th strategy — adding a new key is sufficient. However EXP-15's claim about moving template strings to YAML is still valid; the strategy callables contain hardcoded English logic.

**EXP-35 (Proactive WS push) — push helper already exists.**
`dialogue_ws.py:126` has `push_proactive_line(ws, line)`. The "layer crossing" concern X1 flags is partially mitigated: the function exists in the api layer. The remaining gap is the scheduler calling it — that still requires the in-process queue pattern. The scheduler does pass `proactive_dialogue_engine` to `TickScheduler` already (`dependencies_engines.py:387`), so the engine itself is wired; only the WS delivery path is missing.

**EXP-13 (Trait-modulated emotion model) — protocol is already exercised.**
`EmotionModelProtocol` is fully built (`emotion_model_protocol.py`), wired via constructor injection into `EmotionUpdater`, and `VadEmotionModel` implements it. The FINAL_REVIEW_FINDINGS §L7 note that "no EmotionModelProtocol" was a gap is stale (L7-06 was the prior state). Adding a second impl is now purely a new-file-add.

---

## 1. Per-Proposal Feasibility Table

### X1 Proposals — EXP-10 through EXP-38

| EXP-NN | Title | Fit | Seam Used | Effort | X3 Effort (vs X1) | Prereq Enablers |
|--------|-------|-----|-----------|--------|-------------------|-----------------|
| EXP-10 | Unified proactive-trigger surface (memory + need + event) | **new-file-add** | New `trigger_router.py` in `engines/proactive_dialogue/`; composes existing `ProactiveDialogueEngine` + `IntentFormationEngine` outputs. No edit to either engine. | M | Agree M | None (both engines already wired in scheduler) |
| EXP-11 | Player-scoped memory recall in dialogue context | **closed-edit + DECISIONS** | Adds optional kwarg to `memory_engine.py::create_from_arousal`; adds a player-filtered query to `retrieval/context_builder.py`. Requires Memory node schema addition (`subject_player_id`). Memory.yaml currently has no such field. | M | Agree M | EXP-30 (done); DECISIONS call for Memory schema field |
| EXP-12 | Relation-delta audit — first-contact deltas swallowed | **closed-edit** | Single-module edit to `engines/dialogue/relation_mutator.py`. No layer change, no schema change. Catches `RelationEdgeNotFoundError` and creates the edge before re-applying. | S | Agree S | None |
| EXP-13 | Personality-modulated emotion model (second impl) | **new-file-add** | `EmotionModelProtocol` OCP seam confirmed open. New `engines/emotion/trait_modulated_model.py` + minor addition to `graph/trait_reader.py`. Composition root wires it via `EmotionUpdater.__init__`. | M | Agree M | None |
| EXP-14 | Persistent emotion state (survive restart) | **ALREADY DONE** | `EmotionBootstrapper` in `main.py:125`. Write-through path needs final verification of `EmotionGraphWriter` injection into `EmotionUpdater`. If write-through is unwired, one composition-root line in `dependencies_stores.py`. | S (if write-through gap only) | X1 rated M — disagree, effort is S or DONE | None |
| EXP-15 | Distortion content from `prompts/gossip/*.yaml` | **closed-edit (minor)** | STRATEGY_REGISTRY is OCP-clean for adding new strategies via new file. However moving existing hardcoded strings INTO YAML requires editing each of the 4 existing strategy files (1–2 lines each). Classified as minor closed-edit because those 4 files must change. New `prompts/gossip/` directory is a pure add. | S | Agree S | None |
| EXP-16 | Belief/confidence-aware distortion routing | **closed-edit (minor)** | Adds optional `receiver_confidence` kwarg to `gossip_distort.py::gossip_distort()` and passes it from `gossip_handler._build_write_params`. The gossip_distort.py and gossip_handler.py are closed modules — two small additive edits. New config key in `gossip_config.yaml` is a pure add. | M | Agree M | EXP-15 (recommended but not hard) |
| EXP-17 | Salience-weighted forgetting curve | **closed-edit + DECISIONS** | Adds `recall_count: int` and `never_forget: bool` to Memory node (memory.yaml). Schema currently has neither field. Requires DECISIONS call. `context_builder.py` and `memory_engine.py` both need additive edits. | M | Agree M | DECISIONS call for 2 Memory schema fields; EXP-30 (done) |
| EXP-18 | Memory formation on low-arousal high-importance events | **closed-edit (minor)** | Adds `MemoryEngine.create_from_commitment()` method (additive). Adds call sites in `quest_lifecycle_engine.py` and `action_resolver`. The optional schema field `Memory.kind` is optional (nullable back-compat). Schema addition is minor additive. | M | Agree M | EXP-17 (soft — new memories need salience to be retrievable) |
| EXP-19 | Quest branching — player choice selects successor | **closed-edit + DECISIONS** | `unlocks.yaml` needs a new optional field `on_choice_id`. QuestChainResolver gains a new `choose()` method (additive). New API route `POST /quest/{id}/choose`. The route addition is a closed-edit to the routes package. | L | Agree L | DECISIONS call for UNLOCKS schema addition |
| EXP-20 | World-state-driven dynamic quest generation | **closed-edit (minor)** | Wires existing stub modules (`event_quest_trigger.py`, `world_state_quest_trigger.py`) into the `EventHandler.run_tick` post-creation path. `EventHandler` is a closed module; one additive call site needed. `QuestGenerationEngine.generate()` already accepts `cause_event_id`. | L | Agree L — the integration surface is large even if each edit is small | None |
| EXP-21 | Wire ReputationEngine into tick scheduler | **ALREADY DONE** | Verified: `dependencies_engines.py:388` passes `reputation_engine=get_reputation_engine()` and `tick_scheduler.py:551` calls `run_tick`. X1's "not wired" claim is stale. | — | X1 rated S — now DONE | — |
| EXP-22 | Standing fed into dialogue tone + secret-share gate | **closed-edit (minor)** | Calls existing pure `derive_standing()` function. Two edits: (a) `gossip/knowledge_propagator.py` replaces raw threshold with Standing comparison; (b) `engines/dialogue/prompt_builder.py` injects STANDING line + new rule in `prompts/dialogue/system_v1.yaml`. Both are minor additive edits to closed modules, not structural changes. | M | Agree M | EXP-21 (DONE, so no blocker) |
| EXP-30 | Pinned-core + ranked-pool context model | **ALREADY DONE** | X4 status notes confirm: "ISSUE-059 FIXED in EXP-30; `TokenBudgetExceededError` on tier0+tierA now structurally impossible." `context_builder.py` and `context_budget_enforcer.py` already updated. | — | DONE | — |
| EXP-31 | Retrieval-quality eval harness (precision@k) | **new-file-add** | Pure eval layer — new files under `evals/` + new `make eval-retrieval` target. No engine edits. New labeled fixture data for village/tavern worlds. | M | Agree M | None |
| EXP-32 | Anti-hallucination eval battery (known/unknown probes) | **new-file-add** | Pure eval layer — extends existing LLM-judge infra under `prompts/eval/`. New `known_fact_recall_judge.yaml` + eval runner expansion. No engine edits. | M | Agree M | EXP-30 (DONE — so knowledge-heavy NPCs no longer auto-canned) |
| EXP-33 | Session history persisted across restarts | **closed-edit + DECISIONS** | `session_store.py` needs `save_to_graph()` / `load_from_graph()` methods. Storage model (Character property vs Session node) requires DECISIONS call. Composition root wires the calls. Minor additive edits. | M | Agree M | DECISIONS call for storage model |
| EXP-34 | Need/mood outputs fed into dialogue context | **closed-edit (minor)** | One additive read in `retrieval/context_builder.py` (pool item). EmotionStore vs graph mood divergence is the structural risk — a DECISIONS entry is needed to choose the canonical source before the divergence is fixed. | S | Agree S | EXP-30 (DONE). DECISIONS entry for canonical emotion source. |
| EXP-35 | Proactive line delivered over WS to idle player | **closed-edit + DECISIONS** | `push_proactive_line()` helper exists in `dialogue_ws.py:126`. Scheduler → api push still requires a DECISIONS entry (layer direction). In-process queue pattern is the clean path: new `engines/proactive_dialogue/proactive_queue.py` + minor edits to `proactive_tick_adapter.py` and `dialogue_ws.py`. | S | Agree S | EXP-10 (soft); DECISIONS entry for scheduler→api decoupling pattern |
| EXP-36 | Contradiction detection + deduplication for learned beliefs | **closed-edit (minor)** | Adds `check_contradiction()` graph reader (new function in `graph/`). Calls it from `KnowledgeExtractionEngine.process()` before writing. New graph reader is add-by-new-function; the process() call site is a minor additive edit. | M | Agree M | None |
| EXP-37 | Trade dispatch wired (propose_trade → NegotiationStore) | **closed-edit (minor)** | `dispatch.py` trade handler stub replaced with real routing to `NegotiationStore.create_session()`. `NegotiationStore` is already injected into `DialogueHandler`. One module edit. `trade_handler_sync.py` may already contain partial impl — verify before implementing. | M | Agree M | None |
| EXP-38 | Player-observable event summary endpoint | **new-file-add** | New graph reader function in `graph/event_queries.py` (additive). New API route file `api/routes/player_events.py`. Layer-clean (api → graph). No engine edits. | S | Agree S | None |

---

### X2 Proposals — EXP-40 through EXP-44

| EXP-NN | Title | Fit | Seam Used | Effort | X3 Effort (vs X2) | Prereq Enablers |
|--------|-------|-----|-----------|--------|-------------------|-----------------|
| EXP-40 | Relationship affinity phase engine | **new-file-add** | `relates_to.yaml` already has `relationship_phase` + `phase_started_at_tick` as optional fields — confirmed. Three new files: `engines/relationship/affinity_engine.py`, `engines/relationship/phase_rules_loader.py`, `graph/relation_phase_writer.py`. One additive call site post-`relation_mutator.apply()` in `dialogue_handler.py`. No schema change required. | S | Agree S | None — cleanest quick win in X2 |
| EXP-41 | Player-model / theory-of-mind engine | **new-file-add (after DECISIONS)** | Requires two new type_registry YAML files (`base_nodes/player_model.yaml`, `base_edges/has_player_model.yaml`). This is a schema addition gating DECISIONS approval. Once approved, pure new engine dir `engines/player_model/` + new `graph/player_model_writer.py`. No edit to existing engines. | M | Agree M | DECISIONS call (new node + edge); EXP-40 (soft) |
| EXP-42 | Player-aware drama director engine | **new-file-add (schema: optional)** | If `targets_player_id` optional field is NOT added to `event.yaml`, this is a pure new-file-add: new `engines/director/` directory. If the optional field IS added, a minor schema addition requires a DECISIONS entry. The engine can ship without the field in slice-1 (director targets by player location inference, not graph field). | M | Agree M | EXP-40 (soft — relationship plateau signal); can ship without EXP-41 |
| EXP-43 | NPC deception / false-belief engine | **new-file-add (after DECISIONS)** | `believes.yaml` needs `is_deception: bool` + `deception_goal_id: str` (both optional additive fields). This is a minor schema addition requiring DECISIONS approval. New engine dir `engines/deception/` is pure new-file-add after approval. Critical coordination required with anti-hallucination eval runner. | L | Agree L | DECISIONS call for `believes.yaml` field additions; EXP-40 (soft) |
| EXP-44 | Long-horizon covert scheming engine | **new-file-add (after multiple DECISIONS)** | Requires 3 new type_registry entries: `base_nodes/scheme.yaml`, `base_edges/executes_scheme.yaml`, `base_edges/scheme_step.yaml`. Multiple DECISIONS calls required. Once all approved, engine dir is pure new-file-add. Dispatcher calls into existing engines (deception, gossip, interaction) without editing them — OCP compliant. | XL | Agree XL | EXP-43 (hard for false-belief steps); EXP-40 (soft); multiple DECISIONS calls |

---

### X4 Proposals — EXP-70 through EXP-99

| EXP-NN | Title | Fit | Seam Used | Effort | X3 Effort (vs X4) | Prereq Enablers |
|--------|-------|-----|-----------|--------|-------------------|-----------------|
| EXP-70 | Proactive dialogue act in scripted runner | **new-file-add (demo-side)** | New `ProactiveDialogueBeat` in `demo_game/run_scenes.py`; wired as ACT 11 in `run.py`. Consumes existing `GET /v1/dialogue/pending`. Proactive engine is confirmed live (scheduler wires it). | S | Agree S | Confirm `proactive_dialogue_engine.run_tick` produces intents for demo NPCs (seed-side nudge needed) |
| EXP-71 | Retrieval-explainer panel | **new-file-add (demo-side)** | New `EngineClient.get_retrieval_debug()` method in `client.py`; new `demo_game/ui/retrieval_panel.py`; tab added to `RightPanel` enum. Route already exists (`debug_retrieval.py`). Pure demo-side. | M | Agree M | None |
| EXP-72 | Gossip distortion diff view | **new-file-add (demo-side)** | Extend `ui/gossip_chain.py` to render `distorted_summary` + `distortion_type` per hop. Data is already in the `KNOWS_ABOUT` edge payload fetched at `game_window.py:237-240`. Pure demo-side. | S | Agree S | None |
| EXP-73 | Faction standing board | **new-file-add (demo-side)** | New `EngineClient.get_faction_treaties()` wrapper; extend `ui/politics_panel.py` or add `ui/faction_board.py`; new FACTION tab in `RightPanel`. Routes exist. No treaties seeded by default — standings work standalone. Pure demo-side. | S (standings only) / M (with treaties) | Agree | None |
| EXP-74 | Temporal memory readout | **new-file-add (demo-side)** | Update `ui/memory_panel.py` to render `occurred_at_game_time` + `is_historical`. Fields already returned by `get_memories()` (`client.py:685`). No polling change. Pure demo-side. | S | Agree S | None (Phase 26 fields already exist) |
| EXP-75 | Location hierarchy display (PART_OF breadcrumb) | **new-file-add (demo-side)** | Small addition to `left_panel.py` to query PART_OF edges upward. Route exists via `client.get_graph_edges()`. ISSUE-057 FIXED. Pure demo-side. Graceful no-op if no PART_OF edges seeded. | S | Agree S | Verify seed.py calls `post_part_of` for the 3 demo locations |
| EXP-76 | Degradation-as-feature relabelling | **closed-edit (demo-side, minor)** | Update `DegradationBadge` in `ui/widgets.py` to render tier name alongside colour dot. Single widget edit. Pure demo-side. | S | Agree S | None |
| EXP-77 | Facial-expression glyph rendering | **closed-edit (demo-side, minor)** | Extend `left_panel.py` to render a glyph from `EXPRESSION_GLYPHS` dict. `facial_expression` already parsed at `game_controller.py:312`. Pure demo-side. | S | Agree S | None |
| EXP-78 | Relationship-delta live ticker | **closed-edit (demo-side, minor)** | Extend `left_panel.py` to render `relation_deltas` transient toast. Data already parsed at `game_controller.py:515-527`. Pure demo-side. | S | Agree S | None |
| EXP-79 | Cinematic / recording mode | **new-file-add (demo-side)** | Add `cinematic: bool` flag to `DemoRunner`; update print helpers for formatted output; add `--cinematic` CLI arg. Pure demo-side. | M | Agree M | EXP-93 (fix ISSUE-060 for full-arc recording) |
| EXP-80 | Sandbox mode | **ALREADY IMPLEMENTED** | `SandboxLoop` at `sandbox_loop.py`; S key toggles. No work needed. | — | DONE | — |
| EXP-81 | Cross-session memory recall demo | **ALREADY IMPLEMENTED (scripted)** | ACT 10 `RemembersYouBeat` in `run.py:443-447`. Window "New Session" button is residual S-effort. | S (window button only) | DONE (scripted) | — |
| EXP-82 | Proactive dialogue window surface | **closed-edit (demo-side, minor)** | Extend `game_window.py` event loop to highlight intent NPC + pre-fill input. `NpcInitiativePoller` and bubble display already exist. Pure demo-side. | S | Agree S | Confirm proactive engine produces intents at demo scale |
| EXP-83 | Integrator hello-world quickstart | **ALREADY IMPLEMENTED** | `demo_game/quickstart.py` exists. Residual gaps: field name bug (`response_text` vs `npc_response`), `make hello` target, README section. | S (residual gaps only) | DONE (script) | — |
| EXP-85 | Anti-hallucination beat in scripted runner | **ALREADY IMPLEMENTED** | ACT 9 `AntiHallucinationBeat` in `run.py:435-440`. Window surface remains optional. | — | DONE | — |
| EXP-87 | Richer world (more NPCs / locations) | **new-file-add (demo-side)** | Extend seed data in `seed.py` and `constants.py`. `PART_OF` infrastructure live. Win/lose logic in `game_end_checker.py` must be reviewed for 3-faction assumption before adding factions. Pure demo-side. | M (more NPCs) / L (with hierarchy) | Agree | PART_OF FIXED; EXP-75 (pairing); verify `game_end_checker.py` faction logic |
| EXP-89 | Mood-contagion visualiser | **closed-edit (demo-side, minor)** | Extend `EmotionPoller` to track a list of NPCs; add two-row section to `ui/emotion_panel.py`. Pure demo-side. Contagion magnitude may be subtle without a strong seeded event. | M | Agree M | None — but contagion visibility depends on NPC pair relationship strength |
| EXP-92 | Determinism / replay proof toggle | **ALREADY IMPLEMENTED** | ACT 8 `DeterminismBeat` in `run.py:417-424`. Window surface remains optional. | — | DONE | — |
| EXP-93 | Fix ISSUE-060 (ACT-3 abort) | **closed-edit (demo-side)** | Single method swap in `run_scenes.py::BribeScene.execute()`: `put_npc_reputation` → `adjust_npc_reputation`. Verify `stands_with.yaml` supports character→faction semantics before assuming no schema change needed. DECISIONS entry may be required. | S (if schema clean) / M (if schema change) | Agree | Verify `stands_with.yaml` character→faction validity |
| EXP-95 | In-window scenario picker | **new-file-add / verify (demo-side)** | `ArcChoice` enum + `start_menu.py` exist. Verify `__main__.py` routes all four arcs. If wiring is incomplete, minor additive edits. Pure demo-side. Reseed latency on arc switch is a UX issue, not a blocker. | S (verify/complete) | Agree | EXP-80 DONE |
| EXP-96 | Story-pacing / chapter readout | **depends on engine** | No `GET /v1/system/chapter` route exists in the routes glob. `story_pacing` engine is confirmed thin (🟡). A demo panel cannot be built until an engine read route exists. **Engine-side work required first.** | S (demo) + M (engine route) | Agree — flags correctly as engine-dependent | Engine chapter/pacing read route (does not currently exist) |
| EXP-97 | Live gossip-activity counter per tick | **depends on engine** | `GET /v1/system/engines` exists but no `gossip_pairs_this_tick` field confirmed. Demo panel is S-effort; engine metric addition is M-effort. No grep hit for `gossip_pairs_this_tick`. | S (demo) + M (engine metric) | Agree — flags correctly as engine-dependent | Engine per-tick activity metric |
| EXP-99 | Needs-driven behaviour demo | **depends on engine** | NEEDS tab + `get_needs_for_npc()` exist. Decay-over-ticks display is pure demo-side. Need→behaviour coupling depends on whether routine engine actually consumes Need nodes. `need_decay_engine.py` is confirmed built; whether need thresholds trigger observable behaviour requires code verification. | M | Agree M | Verify routine engine consumes Need thresholds |

---

## 2. Keystone Enablers

Three enablers unlock the most downstream EXP-NNs. Building these first returns the highest multiplier on all subsequent proposals.

### Keystone 1 — DECISIONS call: Memory node schema additions (`subject_player_id`, `recall_count`, `never_forget`)

**Unlocks:** EXP-11, EXP-17, EXP-18 (all three have Memory schema dependencies).

These three fields are all optional/nullable and back-compatible. They can be batched into one DECISIONS entry and one `memory.yaml` edit. The cascade effect is high: EXP-11 (player-scoped recall) and EXP-17 (salience curve) are both rated HIGH value by X1 and both require these fields. EXP-18 (commitment memories) adds `Memory.kind` but can ship as a separate smaller decision. The root fix is getting human approval for the two core fields (`subject_player_id`, `recall_count`) in a single DECISIONS entry.

**Estimated combined value unlocked:** 3 HIGH proposals (EXP-11, EXP-17) + 1 MED (EXP-18).

### Keystone 2 — EXP-40: Relationship affinity phase engine (pure new-file-add, S effort)

**Unlocks:** EXP-22 (Standing → dialogue tone gate, gains phase signal), EXP-41 (player-model uses phase for targeting), EXP-42 (drama director reads relationship plateau), EXP-43 (deception engine targets WARY/HOSTILE phases).

EXP-40 is the only S-effort, pure-new-file-add proposal in the X2 group. It populates already-declared YAML fields (no schema change required), and every other significant X2 proposal lists it as a soft prerequisite. Building it first unlocks the social-graph depth story across all downstream engines. The `relates_to.yaml` seam is confirmed open and clean.

**Estimated combined value unlocked:** 4 downstream proposals (EXP-22 MED→HIGH, EXP-41 HIGH, EXP-42 MED, EXP-43 HIGH).

### Keystone 3 — EXP-93 + EXP-72 + EXP-70 (demo credibility cluster)

**Unlocks:** EXP-79 (cinematic mode requires full-arc clean run), a credible studio pitch from a recording.

EXP-93 (fix ISSUE-060 ACT-3 abort) is a single method swap and unblocks every full-arc scripted demo use. EXP-72 (gossip distortion diff view, S effort) is the highest-leverage demo enhancement because the data is already in the payload — it makes the gossip moat visually undeniable. EXP-70 (proactive dialogue ACT 11, S effort) closes the "NPCs initiate" success criterion in the scripted demo. Together these three S-effort items (one fix + two additions) transform the scripted demo from a partial run to a compelling end-to-end pitch artifact. EXP-79 (cinematic mode) follows once the arc is clean.

**Estimated combined value unlocked:** Full scripted demo credibility; EXP-79 (M effort) becomes unblocked; studio recording becomes feasible.

---

## 3. DECISIONS-Required List

The following proposals cannot proceed to implementation without a human schema or layer approval call. Each entry states what the decision must resolve.

| EXP-NN | Decision Required | What Must Be Decided |
|--------|-------------------|----------------------|
| EXP-11 | Memory node schema: `subject_player_id: str \| None` | Add optional field to `memory.yaml`; confirm back-compat for un-tagged existing memories |
| EXP-17 | Memory node schema: `recall_count: int`, `never_forget: bool` | Add both optional fields to `memory.yaml`; define forget-threshold constant in config |
| EXP-18 | Memory node schema: `kind: Literal["episodic","commitment","fact"] \| None` | Add nullable optional field to `memory.yaml`; confirm back-compat (null = episodic) |
| EXP-19 | UNLOCKS edge schema: `on_choice_id: str \| None` | Add optional field to `unlocks.yaml`; define auto-offer vs player-choice semantics |
| EXP-33 | Session persistence storage model | Neo4j CHARACTER property vs new SESSION_TURNS node; Redis backend consideration |
| EXP-34 | EmotionStore vs graph mood canonical source | Choose one source of truth; resolve divergence between MoodContagionEngine (graph) and EmotionUpdater (in-memory) |
| EXP-35 | Scheduler → api layer decoupling pattern | Approve in-process queue pattern (new `proactive_queue.py`) as the acceptable scheduler→WS delivery mechanism without creating upward layer imports |
| EXP-41 | New node: `player_model`; new edge: `HAS_PLAYER_MODEL` | Full schema approval for two new type_registry entries |
| EXP-42 | Optional: event node field `targets_player_id: str \| None` | Approve or reject adding this field to `event.yaml`; if rejected, director ships slice-1 without it |
| EXP-43 | `believes.yaml` schema additions: `is_deception: bool`, `deception_goal_id: str \| None` | Add two optional fields; coordinate anti-hallucination eval update to treat `is_deception=true` beliefs as intended (not guard failures) |
| EXP-44 | Three new type_registry entries: `scheme` node, `EXECUTES_SCHEME` edge, `SCHEME_STEP` edge | Full schema approval for all three; define max active schemes per NPC config cap |
| EXP-93 | `stands_with.yaml` semantics for character→faction | Confirm whether the existing edge type supports character→faction, or whether a new edge type is required |

**Note:** EXP-11, EXP-17, and EXP-18 share the same YAML file (`memory.yaml`). All three can be batched into a single DECISIONS entry covering all Memory node field additions, reducing the decision count from 3 to 1 for the memory cluster.

---

## 4. Quick Wins

Proposals that are pure new-file-add OR pure demo-side with S effort and high value. These can be executed in any order without DECISIONS calls or layer approvals.

| EXP-NN | Title | Why It's a Quick Win | Estimated Session Cost |
|--------|-------|----------------------|------------------------|
| **EXP-40** | Relationship affinity phase engine | S effort, pure new-file-add, no schema change, populates already-declared optional fields, unlocks 4 downstream proposals. The highest-value quick win in the entire expansion set. | ~1 session |
| **EXP-21** | *(already done)* | Confirmed wired. No work needed. Note this in ISSUES.md as resolved. | 0 |
| **EXP-14** | *(already done — verify write-through)* | `EmotionBootstrapper` confirmed wired in `main.py:125`. One remaining verification: is `EmotionGraphWriter` injected into `EmotionUpdater` at the composition root? If not, one line in `dependencies_stores.py`. | ~30 min |
| **EXP-12** | Relation-delta first-contact fix | S effort, single-module edit, directly fixes a "never swallow errors" CLAUDE.md violation. High business-fit. | ~1 hour |
| **EXP-38** | Player-observable event summary endpoint | S effort, pure new-file-add (one graph query + one route file), no schema change. Directly serves the Unity/Unreal plugin integration story. | ~2 hours |
| **EXP-72** | Gossip distortion diff view | S effort, pure demo-side. Data already in KNOWS_ABOUT payload. Makes the gossip moat visually undeniable. Part of Keystone 3. | ~1 hour |
| **EXP-70** | Proactive dialogue act in scripted runner | S effort, pure demo-side. Route and interactive poller confirmed live. Makes the highest-differentiation engine feature visible in a recording. Part of Keystone 3. | ~2 hours |
| **EXP-93** | Fix ISSUE-060 ACT-3 abort | S effort (if schema clean), single method swap. Blocks all full-arc recordings. Part of Keystone 3. | ~1 hour |
| **EXP-74** | Temporal memory readout | S effort, pure demo-side, zero new files. Fields already returned by `get_memories()`. Makes Phase 26 temporal cognition visible to buyers. | ~30 min |
| **EXP-76** | Degradation-as-feature relabelling | S effort, single widget edit. Converts a failure-colour badge into a product feature. | ~30 min |
| **EXP-77** | Facial-expression glyph rendering | S effort, single left-panel edit. Data already parsed. | ~30 min |
| **EXP-78** | Relationship-delta live ticker | S effort, additive left-panel toast. Data already parsed at `game_controller.py:515-527`. | ~30 min |
| **EXP-35** | Proactive line delivered over WS | S effort once DECISIONS entry approved for queue pattern. `push_proactive_line()` helper already exists in `dialogue_ws.py:126`. | ~2 hours (post-DECISIONS) |
| **EXP-22** | Standing fed into dialogue tone | M effort but no DECISIONS call; EXP-21 is DONE so no blocker. Calls existing `derive_standing()`. High business-fit. | ~1 session |

**Already-built-but-unwired engines confirmed live (no action needed):**
- EXP-21 (reputation propagation) — wired at `dependencies_engines.py:388` and `tick_scheduler.py:551`.
- EXP-14 (emotion persistence) — `EmotionBootstrapper` wired in `main.py:125`. Verify write-through injection only.
- EXP-30 (pinned-core context model) — confirmed DONE per X4 status notes.

---

## 5. X3-Specific Risk Flags

The following risks were not surfaced by X1/X2/X4 and should be noted before implementation work begins.

**EXP-20 and EXP-37: Verify partial implementations before full design.** `event_quest_trigger.py` and `world_state_quest_trigger.py` are described as "stub modules" but ARE imported and wired into `TickScheduler` at `dependencies_engines.py:384-386`. The tick scheduler already passes them. This means EXP-20 may be closer to completion than X1 implies — or the wiring exists but the trigger logic is a no-op. Code verification of `event_quest_trigger.py::check()` is required before estimating effort. Similarly, `trade_handler_sync.py` (EXP-37) may contain partial implementation — verify before designing.

**EXP-44: Dispatcher calls into graveyard engines.** The scheming engine's `scheme_executor.py` would call `engines/deception/` (EXP-43, not yet built) and optionally `engines/investigation/` (graveyard, explicitly "no active dev" per ROADMAP). If the investigation-discovery path is desired, un-graveyarding `investigation` engine would require a separate DECISIONS entry. Without it, EXP-44 schemes are permanently undetectable, which may be a design gap.

**EXP-42 (Drama director) + EXP-34 (Need→dialogue context): conflicting canonical emotion sources.** Both proposals read player engagement state and NPC mood. If EmotionStore and graph mood diverge (the unresolved issue flagged for EXP-34), the director and need-dialogue proposals will disagree about NPC state. The DECISIONS call to pick one canonical source (Keystone prerequisite for EXP-34) should be resolved before either EXP-34 or EXP-42 is implemented.

**EXP-15 + EXP-16 ordering matters for determinism.** EXP-15 migrates distortion strings to YAML while preserving seeded determinism. EXP-16 then adds belief-confidence routing. If EXP-16 is implemented before EXP-15, the belief-confidence config in `gossip_config.yaml` will coexist with hardcoded strategy strings — creating an inconsistent authoring surface. The ordering EXP-15 → EXP-16 should be enforced.

**EXP-87 (richer world): win/lose logic is faction-count-gated.** `game_end_checker.py` is noted as assuming 3 factions. Before adding new factions to the seed world, this logic must be made configurable or the assertion must be removed. This is not a blocker for adding flat new NPCs in existing factions, but it is a blocker for adding new factions.
