# Engine Feature Gaps — Lens X1 (Existing-Engine Feature Gaps)

**Written:** 2026-06-11 (Phase 26 complete, branch `munich-demo`). Codebase read-only analysis.
**Scope:** Every engine in `src/npc_engine/engines/` (plus `retrieval/`), assessed against
`project-harness/expansion/BUSINESS_INTENT.md` and the competitive bar for a middleware that
delivers persistent NPC memory, relationships, and emotional state.
**Note:** Some gaps identified in an earlier draft have since been RESOLVED by the implementation
work that completed Phases 14–26. This file reflects the current code state.

---

## Orientation

After 26 phases and 1967 passing tests the engine is mature. The quality bar for a "gap" is
therefore high: the question is not "does the engine exist?" but "does it deliver the depth
the business thesis requires?" Seven themes emerge from the read:

1. **Proactive dialogue exists but is memory-only triggered** — the `ProactiveDialogueEngine`
   fires only on high-vividness unshared memories. Need, goal, and event triggers are wired
   separately in `IntentFormationEngine` but the two systems are never composed into one
   ranked trigger surface.
2. **Emotion is protocol-gated but personality-modulated variants don't exist yet** —
   `EmotionModelProtocol` and `VadEmotionModel` exist; no second model has been added.
3. **Gossip distortion is now OCP-clean** (strategy registry exists) but distortion _content_
   is still hardcoded English template strings outside `prompts/`.
4. **Memory formation has two paths (arousal + semantic keyword) but no forgetting curve**
   and no player-scoped recall.
5. **Quest chain resolution is implemented** (`QuestChainResolver`, `UNLOCKS` edges) but
   branching (player choice between paths) and fail-consequence chains are absent.
6. **Reputation propagation is 1-hop only, not wired to the tick scheduler** (the module
   docstring says "Used by: tick scheduler (future slice — not wired in this slice)").
7. **Retrieval quality is never measured** — the entire vector + reranker stack has no
   precision@k eval.

---

## Quick Index

| ID | Engine | Title | Value | Effort |
|----|--------|-------|-------|--------|
| EXP-10 | proactive_dialogue + agenda | Unified proactive-trigger surface (memory + need + event) | high | M |
| EXP-11 | dialogue / memory | Player-scoped memory recall in dialogue context | high | M |
| EXP-12 | dialogue | Relation-delta audit: swallowed first-contact deltas | med | S |
| EXP-13 | emotion | Personality-modulated emotion model (second `EmotionModelProtocol` impl) | med | M |
| EXP-14 | emotion | Persistent emotion state (survive restart) | med | M |
| EXP-15 | gossip | Distortion content from `prompts/gossip/*.yaml` (no hardcoded strings) | med | S |
| EXP-16 | gossip | Confidence-weighted, belief-selective distortion routing | med | M |
| EXP-17 | memory | Salience-weighted forgetting curve (charge + recall + recency) | high | M |
| EXP-18 | memory | Memory formation on low-arousal but high-importance events | med | M |
| EXP-19 | quest | Branching quests and fail-consequence chains | high | L |
| EXP-20 | quest_generation | World-state-driven dynamic quest generation | med | L |
| EXP-21 | relationship / reputation | Reputation engine wired to tick scheduler | high | S |
| EXP-22 | relationship | Derived standing fed back into dialogue tone + secret-share gate | high | M |
| EXP-30 | retrieval | Pinned-core + ranked-pool context model (ISSUE-059 root cause) | high | M |
| EXP-31 | retrieval | Retrieval-quality eval harness (precision@k / recall) | high | M |
| EXP-32 | retrieval | Anti-hallucination eval battery (fail on deflections) | high | M |
| EXP-33 | retrieval | Session history persisted across restarts | med | M |
| EXP-34 | mood / need | Need/mood engine outputs fed into dialogue context | med | S |
| EXP-35 | proactive_dialogue | Proactive line delivered over WS to idle-player (API surface) | high | S |
| EXP-36 | knowledge_learning | Contradiction detection and deduplication for learned beliefs | med | M |
| EXP-37 | interaction | Trade dispatch wired: `propose_trade` → economy engine | med | M |
| EXP-38 | events | Player-observable event summary endpoint | med | S |

---

## DIALOGUE — `engines/dialogue/`

**Current state:** Full reactive pipeline: tiered degradation, structured output with
`npc_response + action + facial_expression + relation_deltas + mood_update + learned_facts`,
prompt injection fencing (`_PLAYER_MESSAGE_OPEN/CLOSE` sentinels, L1-05), archetype-keyed
canned fallback, TTS, negotiation context injection. Genuinely strong.

Gaps are all *depth* issues: the response is reactive-only; the relation mutator swallows
first-contact errors; player-specific memory is never retrieved; the stream path bypasses all
post-processing (no knowledge learning, no relation mutation, no emotion update on streaming).

### EXP-10: Unified proactive-trigger surface (memory + need + event + goal)
```
Type: existing-engine-gap
Business rationale: Success criterion "NPCs proactively initiate in-character"
  (BUSINESS_INTENT.md:130); implied ambition "agentic NPCs that initiate, not just react"
  (BUSINESS_INTENT.md:59).
What it does: Two parallel systems exist — ProactiveDialogueEngine (fires on unshared
  high-vividness memories, engines/proactive_dialogue/proactive_engine.py:127) and
  IntentFormationEngine (scores need/event/goal triggers, engines/agenda/intent_formation_engine.py:32)
  — but they are never composed into a single ranked trigger surface. The tick scheduler
  runs each independently; there is no unified "should this NPC speak?" decision that picks
  the best trigger from the combined pool and generates one coherent line.
Current state: ProactiveDialogueEngine.check_trigger only queries unshared memories
  (proactive_engine.py:160-216); it returns None if the NPC has a critical unmet need
  or a fresh witnessed event but no high-vividness unshared memory. IntentFormationEngine
  produces ConversationIntent objects (agenda/conversation_intent_service.py:33) but does
  not call the LLM — enqueues intents to a graph queue that is never consumed by the
  proactive line generator. The two systems share no data path.
Graph/schema additions: none required — both readers already exist. Optional: a shared
  ProactiveTrigger model that carries a `trigger_type: Literal["memory","need","event","goal"]`
  and `score: float`.
API surface: no new HTTP route needed; the existing WS `proactive_line` event is enough.
  Engine-internal composition change only.
Composition: a new thin `ProactiveTriggerRouter` (engines/proactive_dialogue/) ranks
  ProactiveTrigger from both sources by score, picks the highest, and calls
  ProactiveDialogueEngine.generate_line. Layer: engines.
Architecture fit: add-by-new-file (`engines/proactive_dialogue/trigger_router.py`);
  no edits to existing engines required if both expose a compatible trigger interface.
  Check that IntentFormationEngine score scale (0–1.0) matches ProactiveTrigger.memory_vividness
  (0–100) — one normalisation function needed.
Prerequisite enablers: none.
Effort: M    Value: high    Business-fit: high
Risks / unknowns: cadence control — need a cooldown so a desperate NPC does not spam the
  player every tick. A per-NPC last_proactive_tick field (in-memory) is the cheapest guard.
First slice: extract intent scores from ConversationIntent into a comparable float; pick max
  between memory-vividness/100 and need/event/goal score; generate a line only when the
  combined best exceeds a threshold.
Open questions: What prompt framing does a need-driven proactive line use vs a memory-driven
  one? Does each trigger_type deserve its own YAML prompt? → OPEN_QUESTIONS.md
```

### EXP-11: Player-scoped memory recall in dialogue context
```
Type: existing-engine-gap
Business rationale: "NPCs remember shared history" and respond from what they actually know
  (BUSINESS_INTENT.md:22,35). Anti-hallucination depends on surfacing the correct prior
  interactions, not the globally most-vivid NPC memories.
What it does: Retrieves the NPC's memories that concern this specific player — prior
  conversations, promises, named interactions — and injects them into the dialogue context
  ahead of generic NPC memories. Today a player who told an NPC their name two sessions ago
  gets no recognition.
Current state: context_builder.py retrieves memories via get_memories_for_character(session,
  character_id=npc_id, k=3), globally ordered by the graph query default (retrieval/
  context_builder.py line ~120 — exact line varies by the build). There is no
  player_id filter on the memory retrieval call. Memory nodes carry no `subject_ids`
  field linking them to participants. Session store holds only recent turns in-memory
  (dialogue/session_store.py) and is cleared on restart.
Graph/schema additions: Memory.subject_player_id: str | None (nullable — back-compat);
  set on MemoryEngine.create_from_arousal when the triggering context includes a player.
  YAML sketch:
    properties:
      subject_player_id:
        type: string
        description: Player ID present during this memory's formation, or null.
API surface: engine-internal (context assembly); no HTTP route change.
Composition: engines/memory/memory_engine.py::create_from_arousal gains an optional
  subject_player_id kwarg; retrieval/context_builder adds a second graph read
  get_memories_for_character(..., subject_player_id=player_id, k=2) as pinned pool
  items (EXP-30 compatible); falls back to global memories.
Architecture fit: additive — new optional kwarg + one new graph query function.
  Requires DECISIONS approval for the Memory node schema addition.
Prerequisite enablers: EXP-30 (so added player-memories don't overflow the budget).
Effort: M    Value: high    Business-fit: high
Risks / unknowns: back-compat — existing un-tagged memories should still surface (global
  fallback); player_id vs npc_id symmetry when both parties form memories.
First slice: tag new memories with subject_player_id in create_from_arousal; add a
  player-scoped retrieval path in context_builder; assert a tagged memory surfaces before
  a global memory for the same player in a unit test.
Open questions: none.
```

### EXP-12: Relation-delta audit — first-contact deltas silently dropped
```
Type: existing-engine-gap
Business rationale: Commitment "bounded relation mutation with audit delta_log" and
  success criterion "relation values cannot be griefed into extremes"
  (BUSINESS_INTENT.md:47,83). CLAUDE.md "Never swallow errors" (CLAUDE.md strict rule).
What it does: First-contact relation changes (player speaks to an NPC they have never
  interacted with) are silently discarded because no RELATES_TO edge exists yet.
  The fix auto-creates the edge and always writes an audit record.
Current state: engines/dialogue/relation_mutator.py catches RelationEdgeNotFoundError
  and returns without writing an audit row or creating the missing edge. The exact
  comment reads "Missing-edge errors are silently swallowed so the caller's response
  flow is not interrupted" (relation_mutator.py, docstring region). This is a
  deliberate swallow that violates the CLAUDE.md "Never swallow errors" rule and
  loses the first-impression relation signal.
Graph/schema additions: none (RELATES_TO edge and delta_log already defined).
API surface: engine-internal.
Composition: relation_mutator.py catches RelationEdgeNotFoundError, calls an
  ensure-edge writer (graph/graph_writer), then re-applies the delta. Stays within
  the mutation/ layer boundary.
Architecture fit: single-module edit — relation_mutator.py. No layer rule changes.
Prerequisite enablers: none.
Effort: S    Value: med    Business-fit: high
Risks / unknowns: auto-creating the edge may change the observable relation semantics
  for a first-time meeting; needs a test asserting delta_log is written on first
  contact. Edge defaults (trust=0, fear=0, affection=0) must be consistent with
  existing seeded worlds.
First slice: on RelationEdgeNotFoundError, create edge at defaults then apply delta;
  assert delta_log row written in unit test.
Open questions: none.
```

### EXP-35: Proactive line delivered over WS to idle player (API surface gap)
```
Type: existing-engine-gap
Business rationale: "WebSocket token streaming so the player sees the NPC thinking"
  (BUSINESS_INTENT.md:42); success criterion "NPCs proactively initiate in-character"
  requires a WS delivery path (BUSINESS_INTENT.md:130).
What it does: The ProactiveDialogueEngine.generate_line produces a ProactiveLine model
  (proactive_engine.py:260) but there is no WS push path that delivers it to the
  client. The tick scheduler calls run_tick on the proactive_tick_adapter but the
  generated line is logged and discarded — never reaches the connected player.
Current state: proactive_tick_adapter.py generates lines and logs them
  (proactive_tick_adapter.py:run_tick); the WS route only handles incoming
  player messages (api/routes/dialogue_ws.py). There is no server-initiated push
  on the existing dialogue socket for NPC-originated content.
Graph/schema additions: none required for v1.
API surface: new WS server-push message type `{ "type": "proactive_line",
  "npc_id": str, "content": str, "tick": int }` on the existing
  `WS /v1/ws/dialogue/{player_id}` socket.
Composition: tick scheduler calls proactive_tick_adapter; adapter delivers the
  ProactiveLine via the WS connection manager (api/ws_manager or equivalent).
  Requires access to the live connection registry from the scheduler layer —
  needs a DECISIONS entry (scheduler → api dependency is a layer cross).
Architecture fit: the scheduler pushing to the WS layer is a layer dependency
  that currently does not exist; needs DECISIONS approval. Cleanest model: the
  scheduler enqueues to an in-process queue; the WS handler drains the queue
  per player on each heartbeat.
Prerequisite enablers: EXP-10 (unified trigger surface improves line quality).
Effort: S    Value: high    Business-fit: high
Risks / unknowns: layer crossing — scheduler must not import from api/. Queue-based
  decoupling is the safe path. Client SDK must handle the new message type.
First slice: in-process async queue per player_id; WS heartbeat drains it;
  proactive_tick_adapter pushes to the queue.
Open questions: Does the existing WS route handle bi-directional push, or is it
  request-only? → OPEN_QUESTIONS.md
```

---

## EMOTION / MOOD — `engines/emotion/`, `engines/mood/`

**Current state:** `EmotionModelProtocol` exists (`emotion_model_protocol.py:18`) and
`VadEmotionModel` implements it (`vad_emotion_model.py:30`). The protocol is wired via
constructor injection into `EmotionUpdater` with `VadEmotionModel()` as the default
(`emotion_updater.py:58`). The OCP seam is present. What is missing: no second model
has ever been added; `derive_label` remains a closed 5-branch if-chain in `emotion_state.py`;
emotion state is in-memory only and lost on restart.

### EXP-13: Personality-modulated emotion model (second EmotionModelProtocol impl)
```
Type: existing-engine-gap
Business rationale: Implied ambition "OCP-clean extensibility as a commercial moat …
  no EmotionModelProtocol" was the gap; the protocol now exists but the seam has
  never been exercised (BUSINESS_INTENT.md:65). A studio adding a custom "hot-headed
  guard" or "stoic elder" needs a working example of the seam.
What it does: Add a `TraitModulatedEmotionModel` that reads the NPC's Trait nodes to
  scale shock and decay rates — a hot-headed NPC spikes faster, a stoic one decays
  faster. This exercises the OCP seam and proves it works, making it a commercial
  demonstration.
Current state: Only VadEmotionModel exists (vad_emotion_model.py:30). The shock
  divisors are module-level constants (_SHOCK_VALENCE_DIVISOR = 3,
  _SHOCK_AROUSAL_DIVISOR = 2, vad_emotion_model.py:16-17) — hardcoded, not
  parameterised by NPC traits. derive_label is a closed 5-branch if-chain
  (emotion_state.py:27-45) that cannot be replaced without editing the function.
Graph/schema additions: reads existing Trait nodes (already in type_registry);
  no new schema additions.
API surface: engine-internal; npc_state shape unchanged for VAD-compatible models.
Composition: new file engines/emotion/trait_modulated_model.py implementing
  EmotionModelProtocol; injected via EmotionUpdater.__init__(model=...) at the
  composition root (api/dependency_singletons.py). Reads Trait nodes via a new
  graph.trait_reader function.
Architecture fit: add-by-new-file; no edits to EmotionUpdater or VadEmotionModel.
  The trait graph read is a minor addition to graph/trait_reader.py.
Prerequisite enablers: none.
Effort: M    Value: med    Business-fit: high
Risks / unknowns: label back-compat — derive_label is not part of the protocol;
  the new model can compute its own labels. Must keep derive_label in emotion_state.py
  for tests that depend on it.
First slice: extract `reactivity: float` from a Trait node tagged "volatile" or
  "stoic"; multiply shock increments by reactivity; identical output for neutral-trait
  NPCs (back-compat).
Open questions: Should derive_label become part of EmotionModelProtocol to enable
  custom label sets? → OPEN_QUESTIONS.md
```

### EXP-14: Persistent emotion state (survive restart)
```
Type: existing-engine-gap
Business rationale: Thesis "persistent … emotional state per NPC" (BUSINESS_INTENT.md:35).
  The DEC-068 per-studio deployment means restarts happen; neutral-on-boot is a visible
  regression.
What it does: Snapshot emotion state to Neo4j on write and restore on boot so NPCs
  remember their mood across restarts. MoodContagionEngine.initialize() already loads
  mood from Neo4j (mood_contagion_engine.py:69) — the pattern exists; EmotionStore
  needs the same.
Current state: EmotionStore is purely in-memory (emotion_store.py — class docstring
  "in-memory dict"). EmotionUpdater._write_through calls EmotionGraphWriter when injected
  (emotion_updater.py:136) but the writer is optional and not wired by default at the
  composition root. MoodContagionEngine.initialize loads mood labels only (not VAD scalars
  — mood_contagion_engine.py:80-88). There is a mismatch: MoodContagionEngine updates
  set_character_mood (graph) but EmotionUpdater updates EmotionStore (in-memory); neither
  is the canonical source of truth.
Graph/schema additions: Character node gains valence: int, arousal: int,
  mood_label: str, mood_updated_tick: int (the four fields already implied by
  MoodContagionEngine.initialize reading mood+intensity). Needs DECISIONS approval
  (schema change).
API surface: optional GET /npc/{id}/emotion already implied by npc_state route.
Composition: wire EmotionGraphWriter into EmotionUpdater at api/dependency_singletons.py;
  add load_all_emotion_states() to graph/emotion_writer.py called on startup to hydrate
  EmotionStore.
Architecture fit: requires DECISIONS approval for the schema addition;
  composition-root wiring is a one-line change.
Prerequisite enablers: none. Enables EXP-13 (personality model needs stable baselines).
Effort: M    Value: med    Business-fit: high
Risks / unknowns: write amplification — every dialogue turn writes emotion to Neo4j.
  Mitigation: write-through only when valence/arousal delta > N.
First slice: wire EmotionGraphWriter into the updater; add startup hydration;
  assert state survives a simulated restart in a test.
Open questions: Redis vs Neo4j as the durable store; target write-through frequency
  → OPEN_QUESTIONS.md
```

---

## GOSSIP — `engines/gossip/`

**Current state:** Deterministic seeded distortion with a proper OCP-clean strategy registry
(`distortion_strategy.py:47` — `STRATEGY_REGISTRY: dict[str, DistortionStrategy]`). The four
strategies (`omission`, `exaggeration`, `role_swap`, `timeline_shift`) are separate files in
`engines/gossip/strategies/`. This is good. The remaining gap is that the distortion text
itself is still hardcoded English strings inside those strategy files rather than versioned
YAML prompts, and the routing between strategies is still deterministic-random with no
belief-awareness.

### EXP-15: Distortion content from `prompts/gossip/*.yaml` (eliminate hardcoded strings)
```
Type: existing-engine-gap
Business rationale: CLAUDE.md "no prompt strings outside prompts/" (strict rule);
  implied commercial moat "designer extensibility … YAML, no core code edits"
  (BUSINESS_INTENT.md:46).
What it does: Move the hardcoded distortion template strings from strategy files into
  versioned YAML files under prompts/gossip/, so a studio can customise or translate
  gossip distortion text without touching Python.
Current state: Each strategy file (e.g. engines/gossip/strategies/exaggeration.py,
  omission.py) contains the distortion logic as a Python function returning an
  English string computed from the input. The STRATEGY_REGISTRY dispatch is clean
  (distortion_strategy.py:47) but the strings these functions produce are embedded
  in Python, not in prompts/. There is no prompts/gossip/ directory.
Graph/schema additions: none.
API surface: engine-internal.
Composition: add prompts/gossip/distortion_v1.yaml with template strings per type;
  each strategy callable loads its template from the YAML at module import time.
  Pure-deterministic strategies stay pure (no LLM call).
Architecture fit: add-by-new-file (prompts/gossip/); edit each of the 4 strategy
  files to load from YAML — minor but necessary (4 files, 1-2 lines each).
Prerequisite enablers: none.
Effort: S    Value: med    Business-fit: high
Risks / unknowns: YAML format must preserve determinism (same seed → same output);
  test that sha256-seeded output is byte-for-byte identical after the migration.
First slice: create prompts/gossip/distortion_v1.yaml; migrate exaggeration.py first
  as a proof-of-concept; assert deterministic parity in a unit test.
Open questions: none.
```

### EXP-16: Belief/confidence-aware distortion routing
```
Type: existing-engine-gap
Business rationale: "Deterministic, replayable gossip distortion" plus the thesis that
  NPCs have beliefs that influence their information-passing behaviour
  (BUSINESS_INTENT.md:48,35). A skeptic NPC should omit differently than a true believer.
What it does: Route the gossip distortion type based on the receiver's existing belief
  confidence — a receiver who already BELIEVES the rumour at high confidence exaggerates
  it; one who has never heard it omits part. Currently the distortion type is pure-random
  (seed % len(REGISTRY_KEYS), gossip_distort.py:151).
Current state: gossip_distort.py:151 selects the distortion type as
  `REGISTRY_KEYS[seed % len(REGISTRY_KEYS)]` — no belief-awareness. The receiver's
  existing BELIEVES_RUMOR confidence is available in the graph (called belief_confidence
  in the write_entry, gossip_handler.py:264) but is not fed back into type selection.
Graph/schema additions: none (belief_confidence is already read during the same tick).
API surface: engine-internal.
Composition: gossip_distort() gains an optional receiver_confidence: int | None
  parameter; when provided, the type selection uses a confidence-to-type mapping
  from gossip_config.yaml rather than pure seed-mod. Falls back to current behaviour
  when receiver_confidence is None.
Architecture fit: add optional kwarg to gossip_distort() (additive); caller
  gossip_handler._build_write_params passes belief_confidence. No layer rule changes.
Prerequisite enablers: EXP-15 (so distortion content is in YAML before belief-routing
  adds more complexity).
Effort: M    Value: med    Business-fit: med
Risks / unknowns: confidence thresholds for routing are tuning constants — must live
  in gossip_config.yaml, not hardcoded.
First slice: add confidence_to_distortion_type mapping to gossip_config.yaml
  (high_confidence → exaggeration, low_confidence → omission, unknown → seeded);
  wire into gossip_distort.
Open questions: Should LLM-rendered distortion be an opt-in strategy? → OPEN_QUESTIONS.md
```

---

## MEMORY / MEMORY CONSOLIDATION — `engines/memory/`, `engines/memory_consolidation/`

**Current state:** Two formation paths: arousal-triggered (`create_from_arousal`,
memory_engine.py:47) and semantic-keyword-triggered (`create_from_semantic_triggers`,
memory_engine.py:79 — 8 keywords: death, betrayal, war, etc.). Vividness decay has two
variants: flat (`decay_vividness`) and charge-weighted (`decay_vividness_weighted`). The
consolidation engine LLM-summarises session turns with witness-clarity boosting.
Phase 26 added `occurred_at_game_time` and `is_historical` to Memory nodes; the HEARSAY
vs MY_ACCOUNT channel split is implemented in `prompt_builder.py:108-137`.

Gaps: no salience/recall-count curve, no forgetting floor, no player-scoped recall,
memory formation doesn't fire on low-arousal high-importance events (promise, quest accept).

### EXP-17: Salience-weighted forgetting curve (recall reinforcement + forget floor)
```
Type: existing-engine-gap
Business rationale: Thesis "persistent memory that feels human" and anti-hallucination
  depends on the right memories surviving to retrieval (BUSINESS_INTENT.md:35,74).
What it does: Make memories that are recalled more frequently and have higher emotional
  charge decay slower; introduce a forget floor so truly unimportant memories eventually
  become sub-threshold and are not retrieved (without deleting graph nodes). This makes
  the NPC's knowledge base feel organic: the war rumour from last session persists;
  the "customer bought ale" fact from 50 sessions ago fades.
Current state: MemoryEngine.decay_vividness_weighted uses a charge divisor
  (memory_engine.py:131-147) but has no recall_count input and no forget floor.
  Memory nodes have vividness, emotional_charge, and last_recalled_at (per Phase 26
  additions) but no recall_count field. The retrieval context_builder ranks by
  vividness/recency but never updates last_recalled_at or recall_count when a memory
  is used.
Graph/schema additions:
  Memory.recall_count: int default 0
  Memory.never_forget: bool default false  (for plot-critical memories)
  Computed (not stored): salience = f(vividness, |emotional_charge|, recency, recall_count)
  Needs DECISIONS approval.
API surface: engine-internal.
Composition: retrieval/context_builder bumps recall_count + last_recalled_at when
  assembling a memory into context (write-through on retrieval). MemoryEngine gains
  a compute_salience(memory) helper. decay_vividness_weighted reads recall_count to
  lower the decay rate for frequently-recalled memories. Items with vividness < forget_threshold
  are excluded from the context pool (not deleted from graph).
Architecture fit: two optional schema fields (requires DECISIONS); additive engine methods.
Prerequisite enablers: EXP-30 (pool ranking consumes salience).
Effort: M    Value: high    Business-fit: high
Risks / unknowns: tuning the half-life per charge band; never_forget must be set on
  quest-critical knowledge at seed time; back-compat (existing Memory nodes have
  recall_count=null → treat as 0).
First slice: add recall_count field; bump it in context_builder on retrieval; lower
  decay rate for recall_count > 3. No forget floor in v1 (add in v2).
Open questions: Target half-life per charge band is a tuning detail → resolved by
  config constants.
```

### EXP-18: Memory formation on low-arousal but high-importance events
```
Type: existing-engine-gap
Business rationale: "NPCs remember shared history" — promises, agreements, and
  named-NPC introductions are low-arousal but narratively critical
  (BUSINESS_INTENT.md:22,35).
What it does: Form a memory when a quest is accepted, a promise action fires, or a
  player-NPC introduction occurs — events that are semantically important but do not
  spike NPC arousal. Currently these events are never remembered.
Current state: The two existing formation paths are:
  1. create_from_arousal: requires arousal > 70 (memory_engine.py:51)
  2. create_from_semantic_triggers: triggers on 8 hardcoded keywords
     (memory_engine.py:86-98: death, betrayal, war, assassination, plague,
     execution, exile, coup) — all violent; quest-accept and promise are absent.
  Quest acceptance (quest_lifecycle_engine.py:139-189) does not call MemoryEngine.
  Promise/commitment actions are not formed into memories anywhere.
Graph/schema additions: optional Memory.kind: Literal["episodic","commitment","fact"]
  (nullable for back-compat).
API surface: engine-internal.
Composition: add MemoryEngine.create_from_commitment(session, character_id,
  content, game_time) called from QuestLifecycleEngine.accept_quest and from
  action_resolver when action.type is a commitment-class action.
Architecture fit: additive engine method + call sites. OCP-clean if the trigger list
  is a pluggable registry (not hardcoded list).
Prerequisite enablers: EXP-17 (salience model gives non-arousal memories a vividness
  that makes them retrievable).
Effort: M    Value: med    Business-fit: high
Risks / unknowns: defining "importance" without an LLM call — must remain deterministic
  rule-based triggers.
First slice: form a commitment memory when a quest is accepted (one deterministic trigger,
  zero new schema fields, zero LLM calls).
Open questions: none.
```

---

## QUEST / QUEST GENERATION — `engines/quest/`, `engines/quest_generation/`

**Current state:** Solid lifecycle — `QuestStatus` is a proper enum (quest/models.py — `QuestStatus`),
`QuestChainResolver` implements `UNLOCKS(on:outcome)` chaining
(quest_chain_resolver.py:58-120), `fail_quest` is implemented (quest_lifecycle_engine.py:311-358),
rewards are atomic (quest_reward_router.py). Template + LLM slot-fill with world-state
gating via `StoryPacingEngine`. This is mature.

Gaps: branching (multiple possible successors with player-choice selection) is not wired;
world-state event triggers that generate quests are present as stub modules but not
integrated into the scheduler; quest objectives are still flat Literals with no sub-task
hierarchy.

### EXP-19: Quest branching — player choice selects successor at completion
```
Type: existing-engine-gap
Business rationale: "Win AND lose reachable game loop" and living-world thesis
  (BUSINESS_INTENT.md:50,59). A linear chain is not branching — real narrative
  middleware offers player-driven consequential choice.
What it does: Allow a quest node to have multiple UNLOCKS successors disambiguated
  by `on_choice_id`; when the player completes the quest they are prompted to choose
  which branch to activate; QuestChainResolver then offers only the selected next quest.
Current state: QuestChainResolver.resolve calls get_unlocked_quests(session, quest_id,
  outcome) and offers ALL unlocked quests (quest_chain_resolver.py:100-119) — no
  disambiguation by player choice. There is no `on_choice_id` attribute on UNLOCKS
  edges. The quest API has no `POST /quest/{id}/choose` endpoint.
Graph/schema additions:
  UNLOCKS.on_choice_id: str | None  (null = auto-offer on outcome, non-null = requires
  player selection before offering)
  Needs DECISIONS approval.
API surface: new POST /quest/{id}/choose { choice_id: str, player_id: str }
Composition: QuestChainResolver gains a choose(session, quest_id, player_id, choice_id)
  method; the lifecycle engine defers offering when on_choice_id is set; the choice
  route resolves the selection.
Architecture fit: additive schema field (requires DECISIONS); additive API route;
  no edits to existing lifecycle engine.
Prerequisite enablers: none (QuestChainResolver already exists).
Effort: L    Value: high    Business-fit: high
Risks / unknowns: authoring UX for branching quests (YAML template format); ensuring
  the "auto-offer" (on_choice_id=null) path is unchanged.
First slice: add on_choice_id to UNLOCKS; implement the choose endpoint; demo one
  two-branch quest in the village world.
Open questions: Should choice descriptions be LLM-generated per context, or
  author-specified in the quest template? → OPEN_QUESTIONS.md
```

### EXP-20: World-state-driven dynamic quest generation (event trigger integration)
```
Type: existing-engine-gap
Business rationale: "Off-screen simulation: NPCs gossip, witness events, form opinions"
  implies that world events should generate new narrative objectives
  (BUSINESS_INTENT.md:36,59).
What it does: Wire the existing event_quest_trigger.py and world_state_quest_trigger.py
  modules into the tick scheduler so a high-severity event (war breaks out) can
  automatically generate a contextually relevant quest for co-located NPCs.
Current state: engines/quest_generation/event_quest_trigger.py and
  world_state_quest_trigger.py exist as stub modules that define trigger types but
  are not wired into the tick scheduler or the EventHandler post-creation hook.
  QuestGenerationEngine.generate() is only callable via the manual
  POST /quest-generation/generate route — no automatic trigger.
Graph/schema additions: none required for v1.
API surface: engine-internal (scheduler wiring).
Composition: EventHandler.run_tick calls event_quest_trigger.check(event, session)
  post-creation; if trigger fires, calls QuestGenerationEngine.generate with
  cause_event_id (the generate method already accepts this parameter,
  quest_generation_engine.py:119-196). Layer: engines.
Architecture fit: additive wiring; no engine logic changes. Requires scheduler config
  to enable the trigger.
Prerequisite enablers: none.
Effort: L    Value: med    Business-fit: med
Risks / unknowns: quest-per-event may produce too many quests; StoryPacingEngine's
  quest_generation_rate gating already exists to suppress this (world_state.quest_generation_rate,
  quest_generation_engine.py:145-148).
First slice: one trigger type (high_severity_event → delivery_quest) wired as an
  EventHandler post-hook; rate-gated by StoryPacingEngine.
Open questions: none.
```

---

## RELATIONSHIP / REPUTATION — `engines/relationship/`, `engines/reputation/`

**Current state:** `derive_standing(trust, fear, affection) -> Standing` exists and returns
one of five bands (`standing.py:61-86`). `ReputationEngine` implements 1-hop propagation
(`reputation_engine.py:81-210`). Both exist.

Critical gap: `ReputationEngine` module docstring explicitly says "Used by: tick scheduler
(future slice — not wired in this slice)" (`reputation_engine.py:12`). The module has never
been wired. Additionally, the derived `Standing` is not fed into dialogue tone selection or
secret-share gating — consumers still inline magic-number trust thresholds.

### EXP-21: Wire ReputationEngine into the tick scheduler
```
Type: existing-engine-gap
Business rationale: "Persistent relationships" and "off-screen social graph evolves" —
  the propagation engine exists but does nothing because it is never called
  (BUSINESS_INTENT.md:35,36).
What it does: Register ReputationEngine.run_tick in the tick scheduler so the player's
  reputation propagates through the NPC social network each tick — an NPC who likes the
  player tells their allies and those allies gradually warm.
Current state: ReputationEngine.run_tick(session, player_id, npc_ids) exists and is
  functionally complete (reputation_engine.py:81-110) but is not imported in
  api/dependency_singletons.py, not registered in scheduler/tick_scheduler.py, and
  its docstring explicitly flags this: "Used by: tick scheduler (future slice — not
  wired in this slice)" (reputation_engine.py:11).
Graph/schema additions: none (reads RELATES_TO edges; writes trust nudges via
  apply_nudge_fn already injected via __init__).
API surface: engine-internal.
Composition: api/dependency_singletons.py instantiates ReputationEngine with
  PropagationConfig + RelationReader + apply_nudge; scheduler/tick_scheduler.py adds
  it to the cadence map. One composition-root change + one scheduler change.
Architecture fit: strictly additive; no engine logic changes. Only wiring.
Prerequisite enablers: none.
Effort: S    Value: high    Business-fit: high
Risks / unknowns: N×N loop over npc_ids at each tick — PropagationConfig.enabled
  flag already guards this; must ensure max_pairs cap is in the config.
First slice: wire it; add an integration test that verifies the nudge fires after a
  round of propagation.
Open questions: Should propagation run every tick or every N ticks (cadence config)?
```

### EXP-22: Standing fed into dialogue tone and secret-share gate
```
Type: existing-engine-gap
Business rationale: "Persistent relationships per NPC" — studios buy relationships that
  change NPC *behaviour*, not just numbers (BUSINESS_INTENT.md:35). A HOSTILE NPC should
  refuse trade; an ALLIED NPC might share a secret.
What it does: Replace inline `if trust > N` magic-number thresholds in the gossip
  secret-sharing gate and the dialogue system prompt with calls to
  derive_standing(), comparing against the Standing enum.
Current state: gossip knowledge_propagator.py uses a trust threshold to gate secret
  propagation (knowledge_propagator.py — exact threshold is a module constant). Dialogue
  system prompt does not adjust tone by standing. The derive_standing function exists
  (relationship/standing.py:61) but has no callers in gossip/ or dialogue/. The relation
  reader for gossip pair weighting (gossip_handler._build_write_params, gossip_handler.py:218)
  does not call derive_standing.
Graph/schema additions: none (reads existing RELATES_TO scalars).
API surface: engine-internal.
Composition: gossip/knowledge_propagator.py imports derive_standing; replaces raw
  threshold with Standing comparison. Dialogue prompt_builder injects a STANDING=<band>
  line (new prompt key) that system_v1.yaml Rule 16 can use for tone gating.
Architecture fit: additive — calls to an existing pure function. The STANDING line
  in the prompt needs a new rule added to prompts/dialogue/system_v1.yaml (minor
  prompt edit).
Prerequisite enablers: EXP-21 (so standing is propagated and meaningful before
  we gate on it).
Effort: M    Value: high    Business-fit: high
Risks / unknowns: defining the ALLIED threshold for secret-sharing requires tuning;
  must not break existing gossip determinism tests.
First slice: replace the raw trust threshold in knowledge_propagator with
  Standing.ALLIED comparison; add a test confirming secrets propagate at ALLIED but
  not at FRIENDLY.
Open questions: What standing band unlocks dialogue tone changes? → config constant.
```

---

## RETRIEVAL — `retrieval/`

**Current state:** Tiered context (Tier0 fixed / TierA non-compressible / TierB,C vector +
compressible) with cross-encoder reranking (`cross_encoder_reranker.py`) and budget
enforcement (`context_budget_enforcer.py`). Temporal framing via `memory_temporal.py`
(Phase 26). HEARSAY/MY_ACCOUNT channel split done. No precision@k eval.

### EXP-30: Pinned-core + ranked-pool context model (supersedes ISSUE-059)
```
Type: existing-engine-gap
Business rationale: Success criterion "degradation is invisible to the player";
  Tier-A overflow currently degrades knowledge-heavy NPCs to canned
  (BUSINESS_INTENT.md:79); ISSUE-059 was the original symptom.
What it does: Collapse the tier-A/B/C model into two classes: (1) a tiny pinned set
  (world, emotion, persona, session window, active_quest) that is never dropped; (2)
  a ranked pool (everything else) filled by priority × relevance until the token budget
  is hit. A "Tier-A exceeded" failure becomes structurally impossible because the pinned
  set is bounded by construction.
Current state: context_budget_enforcer.py raises ContextBudgetError when
  tier_a_tokens > tier_a_budget (context_budget_enforcer.py:76-83). Categories like
  beliefs, goals, memories, and secrets are appended to tier_a_raw in context_builder.py
  (~lines 341-360) as non-compressible items; the never-trim tier therefore overflows
  for knowledge-heavy NPCs (mira_innkeeper was the live failure, ISSUE-079). Every item
  already carries a priority field — tiers were just coarse priority bands.
Graph/schema additions: none. Adds a pinned: bool field to ContextItem (in-memory,
  not graph).
API surface: engine-internal.
Composition: retrieval/context_builder.py tags pinned items (world, emotion, persona,
  session_turns, active_quest); retrieval/context_budget_enforcer.py becomes "include
  all pinned, then fill ranked pool by priority × relevance until budget."
Architecture fit: edits context_builder.py + context_budget_enforcer.py (two retrieval
  modules); preserves "never drop persona/world" invariant by making it explicit.
Prerequisite enablers: none. Keystone for EXP-11, EXP-17, EXP-33.
Effort: M    Value: high    Business-fit: high
Risks / unknowns: session window must stay bounded (last-N turns); relevance scorer
  must be cheap enough to run per turn.
First slice: introduce pinned flag + two-class fill on the current item set; assert
  pinned-set tokens are bounded for a high-knowledge NPC fixture.
Open questions: Resolved — see DEC-070.
```

### EXP-31: Retrieval-quality eval harness (precision@k / recall)
```
Type: existing-engine-gap
Business rationale: Implied ambition / success criterion "retrieval returns the right
  memories — precision@k/recall against a labeled relevant-set"
  (BUSINESS_INTENT.md:60,76). Phase 15 intent.
What it does: A labeled relevant-set per query + an eval that reports precision@k /
  recall / MRR for the retrieval stack, surfaced as a single make eval-retrieval target.
Current state: The full stack (embedding_index, cross_encoder_reranker, subgraph_retriever)
  exists but only tone and anti-hallucination are judged. grep "precision@|recall@|
  relevant_set|labeled" over src/ tests/ evals/ returns nothing relevant to retrieval
  quality measurement. No retrieval metric exists.
Graph/schema additions: none (eval fixtures, not graph).
API surface: none; new make eval-retrieval + eval module under existing evals/.
Composition: eval harness drives retrieval/ against seeded eval worlds (village/tavern)
  with hand-labeled relevant nodes; reports precision@5, recall@5, MRR.
Architecture fit: new eval files (test/eval layer); no engine edits.
Prerequisite enablers: none. Strongly complements EXP-30.
Effort: M    Value: high    Business-fit: high
Risks / unknowns: building and maintaining the labeled set; no committed precision target.
First slice: 20 labeled queries on the village world → precision@5 + recall printed by
  one command.
Open questions: Target precision@k number → OPEN_QUESTIONS.md (BUSINESS_INTENT.md:106).
```

### EXP-32: Anti-hallucination eval battery (fail on deflections and canned-on-known)
```
Type: existing-engine-gap
Business rationale: Success criterion "NPCs never assert facts they don't know — must be
  measured not asserted; eval must FAIL on empty/fallback/synonym/refusal to known facts"
  (BUSINESS_INTENT.md:39,74).
What it does: An eval battery that probes NPCs about facts they DO know (expecting an
  answer) and facts they DON'T know (expecting a denial), failing on both hallucination
  and on unhelpful refusals to known facts.
Current state: make eval-llm-demo judges tone and some anti-hallucination cases, but
  the matchers reject only empty/canned/short answers; a deflection response to a
  known-fact query still passes. No "recall of known facts" success rate is computed.
  BUSINESS_INTENT.md explicitly flags: "no committed hallucination-rate number exists"
  (BUSINESS_INTENT.md:106).
Graph/schema additions: none.
API surface: none; eval module + make eval-hallucination target.
Composition: eval drives dialogue against seeded worlds with known/unknown probe sets;
  reuses LLM-judge infra under prompts/eval/; adds a new known_fact_recall_judge.
Architecture fit: new eval files; no engine edits.
Prerequisite enablers: EXP-30 (so knowledge-heavy NPCs are not auto-failing via
  canned degradation).
Effort: M    Value: high    Business-fit: high
Risks / unknowns: judging synonym answers; defining the probe set per world.
First slice: 10 known + 10 unknown probes on captain_sorn (northern_war_begins)
  → hallucination rate + known-fact recall rate printed by one command.
Open questions: Target hallucination rate → OPEN_QUESTIONS.md.
```

### EXP-33: Session history persisted across process restarts
```
Type: existing-engine-gap
Business rationale: "Persistent NPC knowledge, relationships, and emotional state" —
  session turn history is part of the short-term conversational context that makes
  NPCs feel aware of the current conversation (BUSINESS_INTENT.md:35).
What it does: Persist the in-memory session turn store to Neo4j (or an optional Redis
  backend) so a server restart does not erase ongoing conversations.
Current state: engines/dialogue/session_store.py — module docstring: "Does NOT persist
  sessions across process restarts." Sessions are dict-in-memory only. This means a
  restart mid-conversation is detectable by the player (NPC forgets what was just said).
  MoodContagionEngine.initialize() shows the load-on-boot pattern already established.
Graph/schema additions: optional Session node (or Character property map); OR write
  to a dedicated session table. Lightest path: persist only the last-N turns
  (already windowed) to a SESSION_TURNS character property.
API surface: engine-internal.
Composition: SessionStore gains save_to_graph(session) / load_from_graph(session)
  calls; api lifespan calls load on boot; session_store calls save after each append.
Architecture fit: additive — no existing callers need to change. Requires DECISIONS
  approval for the storage model choice.
Prerequisite enablers: none.
Effort: M    Value: med    Business-fit: high
Risks / unknowns: write amplification (every turn writes to graph); mitigation:
  async fire-and-forget write, read on demand.
First slice: persist last-5 turns per (player_id, npc_id) to a CHARACTER property
  on shutdown; load on boot.
Open questions: Redis vs Neo4j for session persistence → OPEN_QUESTIONS.md
```

---

## NEED / MOOD / AGENDA — `engines/need/`, `engines/mood/`, `engines/agenda/`

**Current state:** `NeedDecayEngine` ticks and updates levels; `MoodContagionEngine` blends
co-located pairs; `IntentFormationEngine` scores and enqueues intents. All run their ticks.
The gap is that none of their outputs are consumed by the dialogue pipeline — the context
builder does not include unmet needs, the dialogue system prompt has no STANDING-awareness,
and the MoodContagionEngine writes to `set_character_mood` (graph) while `EmotionUpdater`
reads from `EmotionStore` (in-memory) — a divergence between the two emotion sources.

### EXP-34: Need/mood engine outputs fed into dialogue Tier A context
```
Type: existing-engine-gap
Business rationale: "Off-screen simulation surfaces through conversation" —
  if the world runs off-screen but the NPC never references their unmet needs
  or mood state, the simulation is invisible (BUSINESS_INTENT.md:36,80).
What it does: Add an unmet-need context item and a mood-source reconciliation so:
  (a) an NPC with a critical need mentions it organically in dialogue; (b) the
  EmotionStore and MoodContagionEngine graph writes use the same source of truth.
Current state: NeedDecayEngine writes to graph via set_need_level (need_writer.py)
  but get_needs_for_character is not called in retrieval/context_builder.py's Tier A
  assembly. MoodContagionEngine writes via set_character_mood (mood_queries.py) but
  EmotionUpdater reads from EmotionStore (in-memory) — the two can diverge.
  context_builder.py emotion_state is {"current_mood": current_emotion.label}
  sourced from EmotionStore, not from the graph character mood.
Graph/schema additions: none.
API surface: engine-internal.
Composition: (a) add get_needs_for_character to context_builder Tier A (low-priority
  pool item); (b) reconcile EmotionStore vs graph mood on startup (EXP-14 covers
  this more completely — this is the minimal fix).
Architecture fit: additive read in context_builder (one extra graph call); no
  layer rule changes. The divergence fix requires choosing EmotionStore or graph
  as canonical (DECISIONS entry needed).
Prerequisite enablers: EXP-30 (so added need items don't overflow the budget).
Effort: S    Value: med    Business-fit: med
Risks / unknowns: the EmotionStore vs graph mood divergence is the real risk —
  a partial fix may create subtler inconsistencies.
First slice: add unmet-need item to context_builder pool (read from graph, priority=low);
  note the EmotionStore/graph divergence in an ISSUE rather than fixing it here.
Open questions: Which is canonical — EmotionStore or graph mood? → OPEN_QUESTIONS.md
```

---

## KNOWLEDGE LEARNING — `engines/knowledge_learning/`

**Current state:** `KnowledgeExtractionEngine.process()` writes player-stated facts as
belief nodes (knowledge_extraction_engine.py:43-100). Docstring explicitly defers
contradiction detection and deduplication: "Contradiction detection and deduplication
are deferred to slice-3." (knowledge_extraction_engine.py:39).

### EXP-36: Contradiction detection and deduplication for learned beliefs
```
Type: existing-engine-gap
Business rationale: "Anti-hallucination guarantee" — if an NPC accumulates
  contradictory beliefs from different players (player A says the king is dead,
  player B says he lives), the NPC will assert conflicting facts
  (BUSINESS_INTENT.md:39).
What it does: Before writing a new belief, check if the NPC already holds a
  contradictory belief (same entity, opposite claim); either flag it for resolution
  or prefer the higher-confidence belief. Deduplicate near-identical facts.
Current state: KnowledgeExtractionEngine iterates learned_facts and calls
  write_belief for each valid fact with no deduplication check
  (knowledge_extraction_engine.py:69-78). The docstring reads "No deduplication or
  contradiction detection in this slice." (knowledge_extraction_engine.py:39).
  Accumulated contradictory BELIEVES nodes will surface in context and confuse the LLM.
Graph/schema additions: none required for deduplication (MERGE semantics already
  used on write_belief); contradiction detection needs a query to check opposing
  facts.
API surface: engine-internal.
Composition: KnowledgeExtractionEngine.process() calls a new check_contradiction()
  graph reader before writing; logs contradictions as structured warnings; higher-
  confidence belief wins (or both persist flagged as contested).
Architecture fit: additive — new graph reader function + pre-write check. No layer
  changes.
Prerequisite enablers: none.
Effort: M    Value: med    Business-fit: med
Risks / unknowns: semantic similarity for "near-duplicate" detection requires an
  embedding comparison (potentially expensive); a simpler v1 uses exact-match on
  entity+claim key.
First slice: exact-match deduplication (MERGE already handles this — verify that
  write_belief MERGE is idempotent before adding dedup logic).
Open questions: none.
```

---

## INTERACTION — `engines/interaction/`

**Current state:** `dispatch_interaction` routes to `quest_handler` (implemented) but the
trade/negotiation path is a stub.

### EXP-37: Trade dispatch wired (propose_trade → economy engine)
```
Type: existing-engine-gap
Business rationale: Structured dialogue action must drive real interactions
  (BUSINESS_INTENT.md:40); economy engine and NegotiationStore both exist but are
  unconnected.
What it does: Route the `propose_trade` dialogue action through `dispatch_interaction`
  into the economy engine so a dialogue-initiated trade proposal creates a real
  negotiation session.
Current state: engines/interaction/dispatch.py contains a stub handler that returns
  a placeholder InteractionState for non-quest action types. NegotiationStore exists
  (engines/interaction/negotiation_store.py) and is injected into DialogueHandler
  (dialogue_handler.py:101) but the create-new-negotiation path from `propose_trade`
  action is not implemented.
Graph/schema additions: none.
API surface: engine-internal (dispatch.py).
Composition: dispatch.py trade_handler.py imports economy engine and NegotiationStore;
  creates a NegotiationSession on propose_trade. The trade_handler_sync.py module
  already exists (interaction/trade_handler_sync.py) — verify if it contains partial
  implementation.
Architecture fit: replace stub in dispatch.py with a real handler (additive); no
  layer rule changes.
Prerequisite enablers: none.
Effort: M    Value: med    Business-fit: med
Risks / unknowns: negotiation state lifecycle — what terminates a session?
First slice: route propose_trade to NegotiationStore.create_session; return
  NegotiationSession ID in InteractionState.
Open questions: none.
```

---

## EVENTS — `engines/events/`

**Current state:** `EventHandler.run_tick` creates weighted events, seeds NPC awareness,
records witnesses, updates world state conditions, and fires disruption rules. Solid.

### EXP-38: Player-observable event summary endpoint
```
Type: existing-engine-gap
Business rationale: "Drop-in plugin for Unity and Unreal games" — the game engine
  needs to know what world events the player's character is aware of so it can
  drive UI, quests, and NPC reactions (BUSINESS_INTENT.md:17). There is no endpoint
  that returns events the player character has witnessed or is aware of.
What it does: A new read endpoint returning events the player character currently
  knows about — their own KNOWS_ABOUT knowledge plus events at their location in the
  last N ticks.
Current state: Events are created and NPCs are made aware via seed_awareness_tx
  (event_handler.py:162) but there is no API route that queries "what events does
  player X know about?" The game engine has no way to drive its own NPC-event
  reaction UI without calling the dialogue endpoint and asking.
Graph/schema additions: none (reads existing KNOWS_ABOUT edges).
API surface: new GET /player/{player_id}/events?since_tick=N&limit=20
Composition: new graph reader in graph/event_queries.py + a new API route in
  api/routes/. Layer-clean (api → graph).
Architecture fit: add-by-new-file (route + graph query). No engine edits.
Prerequisite enablers: none.
Effort: S    Value: med    Business-fit: med
Risks / unknowns: player character must have a KNOWS_ABOUT relationship seeded;
  currently only NPC awareness is seeded.
First slice: GET /player/{id}/events returns last 10 events at the player's
  current location.
Open questions: none.
```

---

## Cross-engine themes (for the feasibility and roadmap lenses)

1. **Agentic loop is almost there but fragmented** (EXP-10, EXP-35) — ProactiveDialogueEngine
   and IntentFormationEngine both exist and tick, but they are not composed and the generated
   line never reaches the WS client. Two small wiring changes (EXP-10 + EXP-35) close this
   entirely. This is the highest near-term impact cluster.

2. **Retrieval quality is the unproved headline claim** (EXP-31, EXP-32) — both anti-hallucination
   and retrieval precision are asserted but never numerically measured. These are buyer-facing
   success criteria. EXP-31 + EXP-32 together make the product demonstrably correct, not just
   anecdotally correct.

3. **Memory is the shallowest mature engine** (EXP-11, EXP-17, EXP-18) — formation is
   arousal/keyword-gated with no forgetting curve and no player-scoped recall. This directly
   undercuts the "persistent memory + anti-hallucination" thesis: knowledge-heavy NPCs have
   many memories but none are graded by salience or personalised per player.

4. **Two engines exist but are never called** (EXP-21 reputation wiring, EXP-37 trade
   dispatch) — these are quick wins that make existing code produce value.

5. **EmotionStore vs graph mood divergence** (EXP-14, EXP-34) — MoodContagionEngine writes
   to the graph; EmotionUpdater reads from in-memory EmotionStore. They are out of sync.
   This is the lowest-effort high-correctness fix in the emotion cluster.
