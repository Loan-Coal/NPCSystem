"""
Module: dependencies_engines.core
Layer: api
Purpose: Singleton factory providers for core simulation engines —
         gossip, event, memory, economy (pricing/trade), faction politics,
         story pacing, and routine.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients directly.
Dependencies injected: infra + store singletons from dependencies_infra / dependencies_stores.
Used by: api.dependencies_engines (package __init__ and tick_slots / quest submodules).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from npc_engine.api.dependencies_infra import get_type_registry
from npc_engine.api.dependencies_stores import get_embedding_index, get_emotion_updater
from npc_engine.config import get_settings
from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.pricing_rules_loader import load_pricing_rules
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.faction_politics.faction_politics_engine import FactionPoliticsEngine
from npc_engine.engines.faction_politics.rules_loader import load_rules
from npc_engine.engines.gossip.gossip_config import load_gossip_config
from npc_engine.engines.gossip.gossip_handler import GossipHandler
from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.engines.routine.routine_engine import RoutineEngine
from npc_engine.engines.story_pacing.pacing_rules_loader import load_pacing_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine


@lru_cache
def get_gossip_handler() -> GossipHandler:
    """Create singleton gossip handler with shared embedding index and graph port.

    Returns:
        GossipHandler wired to the singleton EmbeddingIndex and Neo4jGossipRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.gossip_repository import Neo4jGossipRepository

    settings = get_settings()
    return GossipHandler(
        settings=settings,
        embedding_index=get_embedding_index(),
        weight_config=load_gossip_config(),
        emotion_updater=get_emotion_updater(),
        gossip_repo=Neo4jGossipRepository(get_graph_db()),
    )


@lru_cache
def get_event_handler() -> EventHandler:
    """Create singleton event handler with shared embedding index and registry.

    Returns:
        EventHandler wired to the singleton EmbeddingIndex and TypeRegistry.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.event_repository import Neo4jEventRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    settings = get_settings()
    graph_db = get_graph_db()
    return EventHandler(
        settings=settings,
        embedding_index=get_embedding_index(),
        event_repo=Neo4jEventRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
        registry=get_type_registry(),
    )


@lru_cache
def get_memory_engine() -> MemoryEngine:
    """Return the shared MemoryEngine singleton wired to the Neo4j memory adapter.

    Returns:
        MemoryEngine injected with a Neo4jMemoryRepository over the singleton GraphDB.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.memory_repository import Neo4jMemoryRepository

    return MemoryEngine(memory_repo=Neo4jMemoryRepository(get_graph_db()))


@lru_cache
def get_pricing_engine() -> PricingEngine:
    """Create singleton pricing engine loaded from pricing_rules.yaml.

    Returns:
        PricingEngine wired to the bundled pricing_rules.yaml.
    """
    rules_path = Path(__file__).resolve().parent.parent.parent / "engines" / "economy" / "pricing_rules.yaml"
    rules = load_pricing_rules(rules_path)
    return PricingEngine(rules=rules)


def get_trade_engine() -> TradeEngine:
    """Create a per-request trade engine wired to the shared pricing engine + economy port.

    Not a singleton: built fresh per request as the route's Depends factory.

    Returns:
        TradeEngine wired to the singleton PricingEngine and a Neo4jEconomyRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.economy_repository import Neo4jEconomyRepository

    return TradeEngine(
        pricing_engine=get_pricing_engine(),
        economy_repo=Neo4jEconomyRepository(get_graph_db()),
    )


@lru_cache
def get_faction_politics_engine() -> FactionPoliticsEngine:
    """Create singleton faction politics engine loaded from rules.yaml.

    Returns:
        FactionPoliticsEngine wired to the bundled rules.yaml and a Neo4j repository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.faction_politics_repository import (
        Neo4jFactionPoliticsRepository,
    )

    rules_path = Path(__file__).resolve().parent.parent.parent / "engines" / "faction_politics" / "rules.yaml"
    rules = load_rules(rules_path)
    return FactionPoliticsEngine(rules=rules, repo=Neo4jFactionPoliticsRepository(get_graph_db()))


@lru_cache
def get_story_pacing_engine() -> StoryPacingEngine:
    """Create singleton story pacing engine loaded from pacing_rules.yaml.

    Returns:
        StoryPacingEngine wired to the bundled pacing_rules.yaml.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.story_pacing_repository import Neo4jStoryPacingRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    rules_path = Path(__file__).resolve().parent.parent.parent / "engines" / "story_pacing" / "pacing_rules.yaml"
    rules = load_pacing_rules(rules_path)
    graph_db = get_graph_db()
    return StoryPacingEngine(
        rules=rules,
        story_pacing_repo=Neo4jStoryPacingRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
    )


@lru_cache
def get_routine_engine() -> RoutineEngine:
    """Create singleton routine engine for tick-driven NPC location updates.

    Returns:
        RoutineEngine instance used by the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.routine_repository import Neo4jRoutineRepository

    return RoutineEngine(routine_repo=Neo4jRoutineRepository(get_graph_db()))
