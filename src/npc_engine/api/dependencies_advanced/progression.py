"""
Module: dependencies_advanced.progression
Layer: api
Purpose: Singleton factory providers for progression/knowledge engines —
         skill progression, chapter, investigation, memory consolidation.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: LLM clients (chapter, memory consolidation) + store singletons.
Dependencies: engines.skill, engines.chapter, engines.investigation,
              engines.memory_consolidation, api.dependencies_infra,
              api.dependencies_stores, engines.llm, config.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache

from npc_engine.api.dependencies_infra import _register_adapter
from npc_engine.api.dependencies_stores import get_graph_db, get_session_store
from npc_engine.config import get_settings
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_runtime_config import get_config as get_engine_model_config_for


@lru_cache
def get_skill_progression_engine():
    """Create singleton skill progression engine for XP awards on quest completion.

    Wires the Neo4j graph adapter (Neo4jSkillRepository) as the engine's injected
    SkillGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        SkillProgressionEngine instance.
    """
    from npc_engine.engines.skill.skill_progression_engine import SkillProgressionEngine
    from npc_engine.graph.repositories.skill_repository import Neo4jSkillRepository

    return SkillProgressionEngine(skill_repo=Neo4jSkillRepository(get_graph_db()))


@lru_cache
def get_chapter_engine():
    """Create singleton chapter engine with its own LLM client.

    Wires the Neo4j graph adapters (Neo4jChapterRepository + Neo4jWorldStateRepository)
    as the engine's injected ChapterGraphPort / WorldStateGraphPort (DEC-122 / SEV-24)
    so the engine holds no Neo4j session.

    Returns:
        ChapterEngine configured from engines/chapter/llm_config.yaml.
    """
    from npc_engine.engines.chapter.chapter_engine import ChapterEngine
    from npc_engine.graph.repositories.chapter_repository import Neo4jChapterRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    engine_config = get_engine_model_config_for("chapter")
    settings = get_settings()
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, settings))
    graph_db = get_graph_db()
    return ChapterEngine(
        llm_client=llm_client,
        chapter_repo=Neo4jChapterRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
        max_tokens=engine_config.llm.max_tokens,
        temperature=engine_config.llm.temperature,
    )


@lru_cache
def get_investigation_engine():
    """Create singleton investigation engine for Detective/Mystery queries.

    Wires the Neo4jInvestigationRepository (read-only) as the engine-layer Port
    (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        InvestigationEngine instance (query-only, no LLM).
    """
    from npc_engine.engines.investigation.investigation_engine import InvestigationEngine
    from npc_engine.graph.repositories.investigation_repository import (
        Neo4jInvestigationRepository,
    )

    return InvestigationEngine(investigation_repo=Neo4jInvestigationRepository(get_graph_db()))


@lru_cache
def get_memory_consolidation_engine():
    """Create singleton for the memory consolidation engine using its own LLM config.

    Wires the Neo4j graph adapter (Neo4jMemoryConsolidationRepository) as the engine's
    injected MemoryConsolidationGraphPort (DEC-122 / SEV-24) so the engine holds no session.

    Returns:
        MemoryConsolidationEngine configured from engines/memory_consolidation/llm_config.yaml.
    """
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
        MemoryConsolidationEngine,
    )
    from npc_engine.graph.repositories.memory_consolidation_repository import (
        Neo4jMemoryConsolidationRepository,
    )

    engine_config = get_engine_model_config_for("memory_consolidation")
    settings = get_settings()
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, settings))
    return MemoryConsolidationEngine(
        session_store=get_session_store(),
        llm_client=llm_client,
        memory_repo=Neo4jMemoryConsolidationRepository(get_graph_db()),
        settings=settings,
        turn_threshold=5,
        clear_turns_after=False,
        max_tokens=engine_config.llm.max_tokens,
        temperature=engine_config.llm.temperature,
    )
