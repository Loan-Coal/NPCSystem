"""
Module: engine_slots
Layer: api
Purpose: Types every TickScheduler engine slot by the protocol that slot must satisfy,
         so mypy checks the concrete engine against its contract at the wiring site.
Dependencies: npc_engine.engines.base_engine
Used by: npc_engine.api.dependencies_engines
"""
from __future__ import annotations

from typing import TypedDict

from npc_engine.engines.base_engine import ConsolidationTickEngine, RoutineTickEngine, TickEngine


class CoreEngineSlots(TypedDict):
    """The engine slots filled by ``_core_engine_kwargs``.

    Annotating the builder with this makes the dict literal a checked assignment
    site. Without it the composition root hands TickScheduler a ``dict[str, Any]``
    and mypy accepts an engine whose ``run_tick`` takes entirely different
    parameters — measured at R3.5, where tightening the protocol alone changed
    nothing (DEC-252).
    """

    gossip_handler: TickEngine
    event_handler: TickEngine
    routine_engine: RoutineTickEngine
    faction_politics_engine: TickEngine
    story_pacing_engine: TickEngine
    event_quest_trigger: TickEngine
    need_quest_trigger: TickEngine
    world_state_quest_trigger: TickEngine
    proactive_dialogue_engine: TickEngine
    reputation_engine: TickEngine
    intent_formation_engine: TickEngine
    goal_formation_engine: TickEngine
    player_model_engine: TickEngine
    director_engine: TickEngine
    memory_decay_engine: TickEngine
    scheme_advance_engine: TickEngine
    scheme_detection_engine: TickEngine


class AdvancedEngineSlots(TypedDict):
    """The engine slots filled by ``_advanced_engine_kwargs``; see ``CoreEngineSlots``."""

    clique_formation_engine: TickEngine
    skill_progression_engine: TickEngine
    oath_engine: TickEngine
    treaty_engine: TickEngine
    memory_consolidation_engine: ConsolidationTickEngine
    mood_contagion_engine: TickEngine
    chapter_engine: TickEngine
    succession_engine: TickEngine
    agenda_engine: TickEngine
    need_decay_engine: TickEngine
    military_engine: TickEngine
