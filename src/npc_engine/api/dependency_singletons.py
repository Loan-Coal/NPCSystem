"""
Module: dependency_singletons
Layer: api
Purpose: Thin re-exporter that preserves all existing import paths after the SEV-23 split.
         Actual implementations live in dependencies_infra, dependencies_stores,
         dependencies_engines, and dependencies_advanced.
Does NOT: define any factory functions — re-exports only.
Dependencies injected: none (re-exporter only).
Dependencies: api.dependencies_infra, api.dependencies_stores, api.dependencies_engines,
              api.dependencies_advanced
Used by: all api routes and dependencies that import singleton factories.
"""

from __future__ import annotations

from npc_engine.api.dependencies_infra import (
    REGISTRY_SOURCES_SEPARATOR,
    _llm_adapters_to_close,
    _register_adapter,
    close_registered_llm_adapters,
    get_dialogue_engine_model_config,
    get_game_schema,
    get_graph_db,
    get_llm_config,
    get_redis_runtime,
    get_type_registry,
)
from npc_engine.api.dependencies_stores import (
    get_context_cache,
    get_dialogue_graph_ports,
    get_embedding_index,
    get_emotion_store,
    get_emotion_updater,
    get_engine_status_store,
    get_game_clock,
    get_idempotency_service,
    get_idempotency_store,
    get_knowledge_extraction_engine,
    get_reindex_job_service,
    get_session_store,
)
from npc_engine.api.dependencies_engines import (
    get_event_handler,
    get_event_quest_trigger,
    get_faction_politics_engine,
    get_gossip_handler,
    get_interaction_graph_repo,
    get_need_quest_trigger,
    get_pricing_engine,
    get_quest_generation_engine,
    get_quest_lifecycle_engine,
    get_routine_engine,
    get_story_pacing_engine,
    get_tick_scheduler,
    get_trade_engine,
)
from npc_engine.api.dependencies_advanced import (
    get_agenda_engine,
    get_chapter_engine,
    get_clique_formation_engine,
    get_investigation_engine,
    get_memory_consolidation_engine,
    get_military_engine,
    get_mood_contagion_engine,
    get_need_decay_engine,
    get_negotiation_store,
    get_oath_engine,
    get_skill_progression_engine,
    get_succession_engine,
    get_treaty_engine,
)

__all__ = [
    "REGISTRY_SOURCES_SEPARATOR",
    "_llm_adapters_to_close",
    "_register_adapter",
    "close_registered_llm_adapters",
    "get_agenda_engine",
    "get_chapter_engine",
    "get_clique_formation_engine",
    "get_context_cache",
    "get_dialogue_engine_model_config",
    "get_dialogue_graph_ports",
    "get_embedding_index",
    "get_emotion_store",
    "get_emotion_updater",
    "get_engine_status_store",
    "get_event_handler",
    "get_event_quest_trigger",
    "get_faction_politics_engine",
    "get_game_clock",
    "get_game_schema",
    "get_gossip_handler",
    "get_graph_db",
    "get_idempotency_service",
    "get_idempotency_store",
    "get_interaction_graph_repo",
    "get_investigation_engine",
    "get_knowledge_extraction_engine",
    "get_llm_config",
    "get_memory_consolidation_engine",
    "get_military_engine",
    "get_mood_contagion_engine",
    "get_need_decay_engine",
    "get_need_quest_trigger",
    "get_negotiation_store",
    "get_oath_engine",
    "get_pricing_engine",
    "get_quest_generation_engine",
    "get_quest_lifecycle_engine",
    "get_redis_runtime",
    "get_reindex_job_service",
    "get_routine_engine",
    "get_session_store",
    "get_skill_progression_engine",
    "get_story_pacing_engine",
    "get_succession_engine",
    "get_tick_scheduler",
    "get_trade_engine",
    "get_treaty_engine",
    "get_type_registry",
]
