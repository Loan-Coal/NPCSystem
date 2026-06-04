"""
Module: dependencies_advanced
Layer: api
Purpose: Singleton factory providers for optional/advanced engines —
         clique, treaty, oath, skill, chapter, mood, succession, agenda,
         investigation, military, need-decay, memory-consolidation, negotiation.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: infra + store singletons.
Used by: api.dependency_singletons (re-exporter), api.dependencies_engines (tick scheduler)
"""

from __future__ import annotations

from functools import lru_cache

from npc_engine.api.dependencies_infra import _register_adapter
from npc_engine.api.dependencies_stores import get_emotion_store, get_graph_db, get_session_store
from npc_engine.config import get_settings
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_runtime_config import get_config as get_engine_model_config_for


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
def get_treaty_engine():
    """Create singleton treaty engine for treaty lifecycle management.

    Returns:
        TreatyEngine instance.
    """
    from npc_engine.engines.treaty.treaty_engine import TreatyEngine

    return TreatyEngine()


@lru_cache
def get_oath_engine():
    """Create singleton oath engine for pledge lifecycle management.

    Returns:
        OathEngine instance.
    """
    from npc_engine.engines.oath.oath_engine import OathEngine

    return OathEngine()


@lru_cache
def get_skill_progression_engine():
    """Create singleton skill progression engine for XP awards on quest completion.

    Returns:
        SkillProgressionEngine instance.
    """
    from npc_engine.engines.skill.skill_progression_engine import SkillProgressionEngine

    return SkillProgressionEngine()


@lru_cache
def get_chapter_engine():
    """Create singleton chapter engine with its own LLM client.

    Returns:
        ChapterEngine configured from engines/chapter/llm_config.yaml.
    """
    from npc_engine.engines.chapter.chapter_engine import ChapterEngine

    settings = get_settings()
    engine_config = get_engine_model_config_for("chapter")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, settings))
    return ChapterEngine(
        llm_client=llm_client,
        max_tokens=engine_config.llm.max_tokens,
        temperature=engine_config.llm.temperature,
    )


@lru_cache
def get_mood_contagion_engine():
    """Create singleton mood contagion engine bound to the shared emotion store.

    Returns:
        MoodContagionEngine wired to the singleton EmotionStore.
    """
    from npc_engine.engines.mood.mood_contagion_engine import MoodContagionEngine

    return MoodContagionEngine(emotion_store=get_emotion_store())


@lru_cache
def get_succession_engine():
    """Create singleton succession engine for political title inheritance.

    Returns:
        SuccessionEngine instance.
    """
    from npc_engine.engines.succession.succession_engine import SuccessionEngine

    return SuccessionEngine()


@lru_cache
def get_agenda_engine():
    """Create singleton agenda engine for political vote resolution.

    Returns:
        AgendaEngine instance.
    """
    from npc_engine.engines.agenda.agenda_engine import AgendaEngine

    return AgendaEngine()


@lru_cache
def get_investigation_engine():
    """Create singleton investigation engine for Detective/Mystery queries.

    Returns:
        InvestigationEngine instance (stateless, no LLM).
    """
    from npc_engine.engines.investigation.investigation_engine import InvestigationEngine

    return InvestigationEngine()


@lru_cache
def get_military_engine():
    """Create singleton military engine (stub) for Strategy/4X tick processing.

    Returns:
        MilitaryEngine instance (no-op stub — see ISSUES.md ISSUE-001).
    """
    from npc_engine.engines.military.military_engine import MilitaryEngine

    return MilitaryEngine()


@lru_cache
def get_need_decay_engine():
    """Create singleton need decay engine for per-tick social need updates.

    Returns:
        NeedDecayEngine instance.
    """
    from npc_engine.engines.need.need_decay_engine import NeedDecayEngine

    return NeedDecayEngine()


@lru_cache
def get_memory_consolidation_engine():
    """Create singleton for the memory consolidation engine using its own LLM config.

    Returns:
        MemoryConsolidationEngine configured from engines/memory_consolidation/llm_config.yaml.
    """
    from npc_engine.engines.memory_consolidation.memory_consolidation_engine import MemoryConsolidationEngine

    settings = get_settings()
    engine_config = get_engine_model_config_for("memory_consolidation")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, settings))
    return MemoryConsolidationEngine(
        session_store=get_session_store(),
        llm_client=llm_client,
        graph_db=get_graph_db(),
        settings=settings,
        turn_threshold=5,
        clear_turns_after=False,
        max_tokens=engine_config.llm.max_tokens,
        temperature=engine_config.llm.temperature,
    )


@lru_cache(maxsize=1)
def get_negotiation_store():
    """Create the singleton in-memory NegotiationStore for trade sessions.

    Returns:
        NegotiationStore instance shared across all interaction requests.
    """
    from npc_engine.engines.interaction.negotiation_store import NegotiationStore
    return NegotiationStore()
