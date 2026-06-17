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
from typing import TYPE_CHECKING

from npc_engine.api.dependencies_stores import get_emotion_store
from npc_engine.config import get_settings

if TYPE_CHECKING:
    from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine
    from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine
    from npc_engine.engines.need.need_decay_engine import NeedDecayEngine
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore


@lru_cache
def get_clique_formation_engine() -> CliqueFormationEngine:
    """Create singleton clique formation engine for auto-detecting high-affection character pairs.

    Wires the Neo4j graph adapter (Neo4jGroupRepository) as the engine's injected
    GroupGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        CliqueFormationEngine configured with CLIQUE_FORMATION_TICK_INTERVAL from settings.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine
    from npc_engine.graph.repositories.group_repository import Neo4jGroupRepository

    settings = get_settings()
    return CliqueFormationEngine(settings=settings, group_repo=Neo4jGroupRepository(get_graph_db()))


@lru_cache
def get_mood_contagion_engine() -> MoodContagionEngine:
    """Create singleton mood contagion engine bound to the shared emotion store.

    Wires the Neo4j graph adapter (Neo4jMoodRepository) as the engine's injected
    MoodGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        MoodContagionEngine wired to the singleton EmotionStore + mood repository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine
    from npc_engine.graph.repositories.mood_repository import Neo4jMoodRepository

    return MoodContagionEngine(
        emotion_store=get_emotion_store(),
        mood_repo=Neo4jMoodRepository(get_graph_db()),
    )


@lru_cache
def get_need_decay_engine() -> NeedDecayEngine:
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
def get_negotiation_store() -> NegotiationStore:
    """Create the singleton in-memory NegotiationStore for trade sessions.

    Returns:
        NegotiationStore instance shared across all interaction requests.
    """
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore

    return NegotiationStore()
