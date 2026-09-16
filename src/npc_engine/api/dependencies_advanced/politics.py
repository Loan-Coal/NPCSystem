"""
Module: dependencies_advanced.politics
Layer: api
Purpose: Singleton factory providers for political/faction engines — treaty, agenda.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients.
Dependencies injected: per-engine Neo4j graph repositories (political/treaty).
Dependencies: engines.treaty, engines.agenda.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc_engine.engines.treaty.treaty_engine import TreatyEngine
    from npc_engine.engines.agenda.agenda_engine import AgendaEngine


@lru_cache
def get_treaty_engine() -> TreatyEngine:
    """Create singleton treaty engine for treaty lifecycle management.

    Wires the Neo4j graph adapter (Neo4jTreatyRepository) as the engine's injected
    TreatyGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        TreatyEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.treaty.treaty_engine import TreatyEngine
    from npc_engine.graph.repositories.treaty_repository import Neo4jTreatyRepository

    return TreatyEngine(treaty_repo=Neo4jTreatyRepository(get_graph_db()))


@lru_cache
def get_agenda_engine() -> AgendaEngine:
    """Create singleton agenda engine for political vote resolution.

    Shares the Neo4j political adapter (Neo4jPoliticalRepository) as the engine's
    injected PoliticalGraphPort (DEC-122 / SEV-24) so the engine holds no session.

    Returns:
        AgendaEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.agenda.agenda_engine import AgendaEngine
    from npc_engine.graph.repositories.political_repository import Neo4jPoliticalRepository

    return AgendaEngine(political_repo=Neo4jPoliticalRepository(get_graph_db()))


