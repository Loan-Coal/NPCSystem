# TEMPORARY: delete by end of Sprint 5. Reason: census artifact for T9.1b-d collapse batches; no longer needed once T9.1d closes.

# Ports Layer Census — T9.1a

Counted 2026-09-18, after Sprints 1–3 deletions. Rule: KEEP if implementors ≥ 2 OR callers ≥ 3;
otherwise COLLAPSE. Counts are AST-annotation-precise: docstring mentions are excluded; the
repository file (structural implementor) is excluded from callers.

**Total ports: 32 | KEEP: 8 | COLLAPSE: 24 (including 1 dead port with 0 implementors)**

Batch assignments for T9.1b–d:
- **T9.1b**: rows 1–8
- **T9.1c**: rows 9–16
- **T9.1d**: rows 17–24 (includes `trait_read_port` at row 24 — dead port, also removes `TraitModulatedEmotionModel`)
- Rows 25–32 are KEEP; no action required.

---

## COLLAPSE rows (rows 1–24)

| # | Port file | Protocol(s) | Impl | Callers | Verdict | Consuming engine(s) | Wiring site | Mock tests |
|---|-----------|-------------|------|---------|---------|---------------------|-------------|------------|
| 1 | `emotion_port.py` | `EmotionGraphPort` | 1 | 1 | COLLAPSE | `emotion_updater` | `api/dependencies_stores.py:79` | `test_emotion_persistence`, `test_emotion_repository` |
| 2 | `economy_port.py` | `EconomyGraphPort` | 1 | 1 | COLLAPSE | `trade_engine` | `api/dependencies_engines/core.py:142` | `test_economy_engine`, `test_economy_repository` |
| 3 | `memory_port.py` | `MemoryGraphPort` | 1 | 1 | COLLAPSE | `memory_engine` | `api/dependencies_engines/core.py:114` | `test_memory_engine`, `test_memory_engine_weighted_decay`, `test_memory_service`, `test_memory_repository` |
| 4 | `need_port.py` | `NeedGraphPort` | 1 | 1 | COLLAPSE | `need_decay_engine` | `api/dependencies_advanced/social.py:36` | `test_need_decay_engine` |
| 5 | `routine_port.py` | `RoutineGraphPort` | 1 | 1 | COLLAPSE | `routine_engine` | `api/dependencies_engines/core.py:177` | `test_routine_engine` |
| 6 | `story_pacing_port.py` | `StoryPacingGraphPort` | 1 | 1 | COLLAPSE | `story_pacing_engine` | `api/dependencies_engines/core.py:162` | `test_sev04_story_pacing_graph_queries`, `test_story_pacing_engine` |
| 7 | `political_port.py` | `PoliticalGraphPort` | 1 | 1 | COLLAPSE | `agenda_engine` | `api/dependencies_advanced/politics.py:34` | `test_agenda_engine` |
| 8 | `investigation_port.py` | `InvestigationGraphPort` | 1 | 1 | COLLAPSE | `investigation_engine` | `api/dependencies_advanced/progression.py:75` | `test_investigation_engine`, `test_investigation_repository` |
| 9 | `player_model_port.py` | `PlayerModelGraphPort` | 1 | 1 | COLLAPSE | `player_model_tick` | `api/dependencies_engines/tick_slots.py:149` | `test_player_model_repository`, `test_player_model_tick` |
| 10 | `chapter_port.py` | `ChapterGraphPort` | 1 | 1 | COLLAPSE | `chapter_engine` | `api/dependencies_advanced/progression.py:53` | `test_chapter_engine` |
| 11 | `emotion_bootstrap_port.py` | `EmotionBootstrapGraphPort` | 1 | 1 | COLLAPSE | `emotion_bootstrap` | `main.py:161` | `test_emotion_persistence` |
| 12 | `event_port.py` | `EventGraphPort` | 1 | 1 | COLLAPSE | `event_handler` | `api/dependencies_engines/core.py:97` | `test_event_handler_port`, `test_event_repository` |
| 13 | `proactive_memory_read_port.py` | `ProactiveMemoryReadPort` | 1 | 1 | COLLAPSE | `proactive_engine` | `api/dependencies_engines/tick_slots.py:105` | `test_proactive_memory_read_repository` |
| 14 | `knowledge_port.py` | `KnowledgeGraphPort` | 1 | 1 | COLLAPSE | `knowledge_extraction_engine` | `api/dependencies_stores.py:94` | `test_knowledge_extraction_engine` |
| 15 | `memory_consolidation_port.py` | `MemoryConsolidationGraphPort` | 1 | 1 | COLLAPSE | `memory_consolidation_engine` | `api/dependencies_advanced/progression.py:101` | `test_error_swallowing_sev18`, `test_sev06_semaphore`, `test_memory_consolidation_engine` |
| 16 | `reputation_port.py` | `ReputationGraphPort` | 1 | 1 | COLLAPSE | `reputation_engine`, `reputation_tick_adapter` | `api/dependencies_engines/tick_slots.py:264` | `test_reputation_engine`, `test_reputation_repository` |
| 17 | `gossip_port.py` | `GossipGraphPort` | 1 | 2 | COLLAPSE | `gossip_handler`, `pair_selector` | `api/dependencies_engines/core.py:76` | `test_gossip_determinism`, `test_gossip_emotion_wiring`, `test_gossip_n_plus_one`, `test_gossip_rumor_integration`, `test_pair_selector_coverage` |
| 18 | `scheming_port.py` | `SchemingGraphPort` | 1 | 2 | COLLAPSE | `scheme_advance_tick`, `scheme_detection_tick` | `api/dependencies_engines/tick_slots.py:190,205` | `test_scheme_advance_tick`, `test_scheme_detection_tick` |
| 19 | `planning_port.py` | `PlanningGraphPort` | 1 | 2 | COLLAPSE | `action_selector`, `goal_former` | `api/dependencies_engines/tick_slots.py:234` | `test_action_selector`, `test_goal_former`, `test_planning_repository` |
| 20 | `character_read_port.py` | `CharacterReadPort` | 1 | 2 | COLLAPSE | `goal_former_adapter`, `reputation_tick_adapter` | `api/dependencies_engines/tick_slots.py:238,269` | `test_goal_former_adapter`, `test_reputation_scheduler_wire` |
| 21 | `dialogue_graph_port.py` | `DialogueGraphPort` | 1 | 2 | COLLAPSE | `dialogue_handler`, `relation_mutator` | `api/dependencies_stores.py:120` | `test_dialogue_context_receipt`, `test_dialogue_handler_clock_tick`, `test_dialogue_handler_fallback_v14`, `test_relation_mutator` |
| 22 | `relation_phase_write_port.py` | `RelationPhaseWritePort` | 1 | 2 | COLLAPSE | `dialogue_handler`, `phase_transition_applier` | `api/dependencies_stores.py:124` | `test_phase_transition_applier`, `test_relation_phase_write_repository` |
| 23 | `dialogue_context_port.py` | `DialogueContextPort` | 1* | 1 | COLLAPSE | `dialogue_handler` | `api/dependencies_stores.py:113` | `test_dialogue_context_receipt`, `test_dialogue_handler_clock_tick`, `test_dialogue_handler_fallback_v14` |
| 24 | `trait_read_port.py` | `TraitReadPort` | 0† | 1 | COLLAPSE | `emotion_updater` | none (dead — never wired) | `test_emotion_updater` |

\* `dialogue_context_port`: implementor is `retrieval/dialogue_context/dialogue_context_adapter.py`, not in `graph/repositories/`.

† `trait_read_port` is dead: 0 implementors (the docstring claims one "in slice 2 wiring" that never materialised — DEC-137). T9.1d must also delete `TraitModulatedEmotionModel` and the `trait_reader` branch in `emotion_updater.py:56,76,152–155`.

---

## KEEP rows (rows 25–32)

| # | Port file | Protocol(s) | Impl | Callers | Verdict | Reason | Mock tests |
|---|-----------|-------------|------|---------|---------|--------|------------|
| 25 | `clock_port.py` | `ClockPort` | 1† | 15 | KEEP | 15 callers — crosses API, engines, scheduler | `test_route_clock_tick`, `test_clock_port_conformance`, `test_dialogue_handler_clock_tick` |
| 26 | `intent_port.py` | `IntentGraphPort` | 1 | 3 | KEEP | 3 engine callers | `test_conversation_intent_service`, `test_intent_formation_engine`, `test_proactive_tick_adapter`, `test_intent_repository` |
| 27 | `interaction_port.py` | `InteractionGraphPort` | 1 | 3 | KEEP | 3 callers (2 engines + 1 route) | `test_quest_verifier`, `test_interaction_repository`, `test_quest_phase4` |
| 28 | `player_location_read_port.py` | `PlayerLocationReadPort` | 1 | 5 | KEEP | 5 engine callers | `test_director_tick`, `test_intent_formation_engine`, `test_player_model_tick` |
| 29 | `quest_generation_port.py` | `QuestGenerationGraphPort`, `EventTriggerGraphPort`, `NeedTriggerGraphPort` | 1 | 5 | KEEP | 5 callers across quest-gen sub-engines | `test_quest_generation_engine`, `test_quest_trigger_shared_budget`, `test_event_quest_trigger`, `test_need_quest_trigger`, `test_world_state_quest_trigger` |
| 30 | `quest_port.py` | `QuestLifecycleGraphPort`, `QuestOfferGraphPort`, `QuestRewardGraphPort`, `QuestChainGraphPort` | 1 | 5 | KEEP | 5 callers across quest sub-engines | `test_sev08_quest_reward_atomicity`, `test_quest_chain_offer_adapter`, `test_quest_chain_resolver`, `test_quest_lifecycle_engine`, `test_quest_lifecycle_engine_v14`, `test_quest_reward_routing_v14` |
| 31 | `relation_read_port.py` | `RelationReadPort` | 1 | 5 | KEEP | 5 callers across 4 engines | `test_director_tick`, `test_phase_transition_applier`, `test_reputation_engine`, `test_player_model_tick` |
| 32 | `world_state_port.py` | `WorldStateGraphPort` | 1 | 5 | KEEP | 5 engine callers | `test_sev04_story_pacing_graph_queries`, `test_chapter_engine`, `test_goal_former_adapter`, `test_quest_trigger_shared_budget`, `test_story_pacing_engine`, `test_world_state_quest_trigger` |

† `clock_port`: implementor is `scheduler/game_clock.py::GameClock`, not in `graph/repositories/`.

---

## Summary

| | Count |
|---|---|
| Total ports surveyed | 32 |
| KEEP (impl ≥ 2 or callers ≥ 3) | 8 |
| COLLAPSE (impl < 2 and callers < 3) | 23 |
| DEAD / zero implementors (`trait_read_port`) | 1 |
| **Total to collapse (T9.1b–d)** | **24** |

The 24 collapse rows are the number T10.1's DIP-threshold gate must drive to zero.
