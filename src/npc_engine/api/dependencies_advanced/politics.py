"""
Module: dependencies_advanced.politics
Layer: api
Purpose: Singleton factory providers for political/faction engines —
         treaty, oath, succession, agenda, military.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients.
Dependencies injected: per-engine Neo4j graph repositories (political/treaty/pledge/military).
Dependencies: engines.treaty, engines.oath, engines.succession, engines.agenda, engines.military.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache
def get_treaty_engine():
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
def get_oath_engine():
    """Create singleton oath engine for pledge lifecycle management.

    Wires the Neo4j graph adapter (Neo4jPledgeRepository) as the engine's injected
    PledgeGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        OathEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.oath.oath_engine import OathEngine
    from npc_engine.graph.repositories.pledge_repository import Neo4jPledgeRepository

    return OathEngine(pledge_repo=Neo4jPledgeRepository(get_graph_db()))


@lru_cache
def get_succession_engine():
    """Create singleton succession engine for political title inheritance.

    Wires the Neo4j graph adapter (Neo4jPoliticalRepository) as the engine's injected
    PoliticalGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        SuccessionEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.succession.succession_engine import SuccessionEngine
    from npc_engine.graph.repositories.political_repository import Neo4jPoliticalRepository

    return SuccessionEngine(political_repo=Neo4jPoliticalRepository(get_graph_db()))


@lru_cache
def get_agenda_engine():
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


@lru_cache
def get_military_engine():
    """Create singleton military engine for Strategy/4X tick processing.

    Wires the Neo4j graph adapter (Neo4jMilitaryRepository) as the engine's injected
    MilitaryGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        MilitaryEngine instance.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.engines.military.military_engine import MilitaryEngine
    from npc_engine.graph.repositories.military_repository import Neo4jMilitaryRepository

    return MilitaryEngine(military_repo=Neo4jMilitaryRepository(get_graph_db()))
