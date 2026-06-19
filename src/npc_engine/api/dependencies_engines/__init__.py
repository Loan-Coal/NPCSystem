"""
Package: dependencies_engines
Layer: api
Purpose: Per-engine-family singleton factory providers for core domain engines,
         split from the monolithic dependencies_engines.py into cohesive submodules
         (core, quest, tick_slots) by ISSUE-105. get_tick_scheduler is defined here
         because it assembles all submodule singletons.
Does NOT: define factories in this file other than get_tick_scheduler — delegates to submodules.
Dependencies injected: none (re-exporter); get_tick_scheduler assembles the full scheduler.
Public surface: all get_* names from core, quest, tick_slots, plus get_tick_scheduler.
Used by: api.dependency_singletons, api.routes.quest, api.routes.dialogue,
         api.routes.dialogue_ws, api.dependencies, api.dependencies_stores.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from npc_engine.api.dependencies_engines.core import (
    get_event_handler,
    get_faction_politics_engine,
    get_gossip_handler,
    get_memory_engine,
    get_pricing_engine,
    get_routine_engine,
    get_story_pacing_engine,
    get_trade_engine,
)
from npc_engine.api.dependencies_engines.quest import (
    get_event_quest_trigger,
    get_interaction_graph_repo,
    get_need_quest_trigger,
    get_quest_chain_resolver,
    get_quest_generation_engine,
    get_quest_lifecycle_engine,
    get_quest_offer_service,
    get_quest_reward_router,
    get_world_state_quest_trigger,
)
from npc_engine.api.dependencies_engines.tick_slots import (
    get_director_beat_log,
    get_director_tick,
    get_goal_formation_engine,
    get_intent_formation_engine,
    get_memory_decay_tick,
    get_player_location_reader,
    get_player_model_tick,
    get_proactive_dialogue_engine,
    get_proactive_queue,
    get_relation_reader,
    get_reputation_engine,
    get_scheme_advance_tick,
    get_scheme_detection_tick,
)
from npc_engine.api.dependencies_stores import get_engine_status_store, get_game_clock
from npc_engine.config import get_settings
from npc_engine.scheduler.tick_scheduler import TickScheduler

__all__ = [
    "get_director_beat_log",
    "get_director_tick",
    "get_event_handler",
    "get_event_quest_trigger",
    "get_faction_politics_engine",
    "get_goal_formation_engine",
    "get_gossip_handler",
    "get_intent_formation_engine",
    "get_interaction_graph_repo",
    "get_memory_decay_tick",
    "get_memory_engine",
    "get_need_quest_trigger",
    "get_player_location_reader",
    "get_player_model_tick",
    "get_pricing_engine",
    "get_proactive_dialogue_engine",
    "get_proactive_queue",
    "get_quest_chain_resolver",
    "get_quest_generation_engine",
    "get_quest_lifecycle_engine",
    "get_quest_offer_service",
    "get_quest_reward_router",
    "get_relation_reader",
    "get_reputation_engine",
    "get_routine_engine",
    "get_scheme_advance_tick",
    "get_scheme_detection_tick",
    "get_story_pacing_engine",
    "get_tick_scheduler",
    "get_trade_engine",
    "get_world_state_quest_trigger",
]


def _advanced_engine_kwargs() -> dict[str, Any]:
    """Return advanced-engine singletons as kwargs for TickScheduler assembly."""
    from npc_engine.api.dependencies_advanced import (
        get_agenda_engine,
        get_chapter_engine,
        get_clique_formation_engine,
        get_military_engine,
        get_mood_contagion_engine,
        get_need_decay_engine,
        get_oath_engine,
        get_skill_progression_engine,
        get_succession_engine,
        get_treaty_engine,
    )

    return {
        "clique_formation_engine": get_clique_formation_engine(),
        "skill_progression_engine": get_skill_progression_engine(),
        "oath_engine": get_oath_engine(),
        "treaty_engine": get_treaty_engine(),
        "mood_contagion_engine": get_mood_contagion_engine(),
        "chapter_engine": get_chapter_engine(),
        "succession_engine": get_succession_engine(),
        "agenda_engine": get_agenda_engine(),
        "need_decay_engine": get_need_decay_engine(),
        "military_engine": get_military_engine(),
    }


def _scheduler_config_kwargs(settings: Any) -> dict[str, Any]:
    """Return scheduler interval/lease config as kwargs for TickScheduler assembly."""
    return {
        "gossip_interval": settings.GOSSIP_TICK_INTERVAL,
        "event_interval": settings.EVENT_TICK_INTERVAL,
        "chapter_interval": settings.CHAPTER_TICK_INTERVAL,
        "distributed_lease_enabled": settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        "scheduler_id": settings.TICK_SCHEDULER_ID,
        "lease_owner_id": settings.TICK_LEASE_OWNER_ID,
        "lease_ttl_seconds": settings.TICK_LEASE_TTL_SECONDS,
    }


@lru_cache
def get_tick_scheduler() -> TickScheduler:
    """Return the singleton TickScheduler wired to all shared engine singletons."""
    settings = get_settings()
    return TickScheduler(
        clock=get_game_clock(),
        gossip_handler=get_gossip_handler(),
        event_handler=get_event_handler(),
        routine_engine=get_routine_engine(),
        faction_politics_engine=get_faction_politics_engine(),
        story_pacing_engine=get_story_pacing_engine(),
        event_quest_trigger=get_event_quest_trigger(),
        need_quest_trigger=get_need_quest_trigger(),
        world_state_quest_trigger=get_world_state_quest_trigger(),
        proactive_dialogue_engine=get_proactive_dialogue_engine(),
        reputation_engine=get_reputation_engine(),
        intent_formation_engine=get_intent_formation_engine(),
        goal_formation_engine=get_goal_formation_engine(),
        player_model_engine=get_player_model_tick(),
        director_engine=get_director_tick(),
        memory_decay_engine=get_memory_decay_tick(),
        scheme_advance_engine=get_scheme_advance_tick(),
        scheme_detection_engine=get_scheme_detection_tick(),
        engine_status_store=get_engine_status_store(),
        **_advanced_engine_kwargs(),
        **_scheduler_config_kwargs(settings),
    )
