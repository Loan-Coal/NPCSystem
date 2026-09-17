"""
Module: dependencies_advanced.social
Layer: api
Purpose: Singleton factory providers for social/interaction engines —
         need decay, negotiation store.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients.
Dependencies injected: none (factory functions only; infra singletons injected lazily).
Dependencies: engines.need, engines.interaction.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc_engine.engines.need.need_decay_engine import NeedDecayEngine
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore


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
