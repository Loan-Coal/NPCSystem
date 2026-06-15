"""
Module: dependencies_advanced.social
Layer: api
Purpose: Singleton factory providers for social/interaction engines —
         clique formation, mood contagion, need decay, negotiation store.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients.
Dependencies injected: shared EmotionStore singleton (mood contagion).
Dependencies: engines.clique, engines.mood, engines.need, engines.interaction,
              api.dependencies_stores, config.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache

from npc_engine.api.dependencies_stores import get_emotion_store
from npc_engine.config import get_settings


@lru_cache
def get_clique_formation_engine():
    """Create singleton clique formation engine for auto-detecting high-affection character pairs.

    Returns:
        CliqueFormationEngine configured with CLIQUE_FORMATION_TICK_INTERVAL from settings.
    """
    from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine

    settings = get_settings()
    return CliqueFormationEngine(settings=settings)


@lru_cache
def get_mood_contagion_engine():
    """Create singleton mood contagion engine bound to the shared emotion store.

    Returns:
        MoodContagionEngine wired to the singleton EmotionStore.
    """
    from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine

    return MoodContagionEngine(emotion_store=get_emotion_store())


@lru_cache
def get_need_decay_engine():
    """Create singleton need decay engine for per-tick social need updates.

    Wires the Neo4j graph adapter (Neo4jNeedRepository) as the engine's injected
    NeedGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        NeedDecayEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.need.need_decay_engine import NeedDecayEngine
    from npc_engine.graph.repositories.need_repository import Neo4jNeedRepository

    return NeedDecayEngine(need_repo=Neo4jNeedRepository(get_graph_db()))


@lru_cache(maxsize=1)
def get_negotiation_store():
    """Create the singleton in-memory NegotiationStore for trade sessions.

    Returns:
        NegotiationStore instance shared across all interaction requests.
    """
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore

    return NegotiationStore()
