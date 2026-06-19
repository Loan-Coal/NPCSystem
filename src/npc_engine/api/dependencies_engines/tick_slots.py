"""
Module: dependencies_engines.tick_slots
Layer: api
Purpose: Singleton factory providers for tick-scheduler slot adapters —
         proactive dialogue, intent formation, player model, director, scheming,
         memory decay, goal formation, and reputation; plus the shared queue/readers.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: infra singletons + core submodule (get_event_handler, get_memory_engine).
Used by: api.dependencies_engines (package __init__).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )

from npc_engine.api.dependencies_engines.core import get_event_handler, get_memory_engine
from npc_engine.api.dependencies_infra import _register_adapter, get_type_registry
from npc_engine.config import get_settings
from npc_engine.engines.agenda.intent_formation_engine import IntentFormationEngine
from npc_engine.engines.director.director_beat_log import DirectorBeatLog
from npc_engine.engines.director.director_tick import DirectorTick
from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_runtime_config import get_config as get_engine_model_config_for
from npc_engine.engines.memory.memory_decay_tick import MemoryDecayTick
from npc_engine.engines.planning.action_selector import ActionSelector
from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.engines.planning.goal_former_adapter import GoalFormerAdapter
from npc_engine.engines.player_model.player_model_engine import PlayerModelEngine
from npc_engine.engines.player_model.player_model_tick import PlayerModelTick
from npc_engine.engines.proactive_dialogue.proactive_engine import ProactiveDialogueEngine
from npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue
from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick
from npc_engine.engines.reputation.propagation_config import load_propagation_config
from npc_engine.engines.reputation.reputation_engine import ReputationEngine
from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter
from npc_engine.engines.scheming.scheme_advance_tick import SchemeAdvanceTick
from npc_engine.graph.repositories.character_read_repository import Neo4jCharacterReadRepository
from npc_engine.graph.repositories.relation_read_repository import Neo4jRelationReadRepository
from npc_engine.graph.repositories.reputation_repository import Neo4jReputationRepository
from npc_engine.graph.repositories.scheming_repository import Neo4jSchemingRepository


@lru_cache
def get_proactive_queue() -> ProactiveQueue:
    """Return the shared ProactiveQueue singleton (DEC-098 / F1.2).

    Returns:
        ProactiveQueue singleton used across the full proactive-dialogue path.
    """
    return ProactiveQueue()


@lru_cache
def get_player_location_reader() -> Neo4jPlayerLocationReadRepository:
    """Return the shared Neo4jPlayerLocationReadRepository singleton (ISSUE-098).

    Returns:
        Neo4jPlayerLocationReadRepository wired to the shared graph driver.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )

    return Neo4jPlayerLocationReadRepository(get_graph_db())


@lru_cache
def get_relation_reader() -> Neo4jRelationReadRepository:
    """Return the shared Neo4jRelationReadRepository singleton (ISSUE-098).

    Returns:
        Neo4jRelationReadRepository wired to the shared graph driver.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return Neo4jRelationReadRepository(get_graph_db())


@lru_cache
def get_proactive_dialogue_engine() -> ProactiveDialogueTick:
    """Create singleton ProactiveDialogueTick wired to the shared LLM client and graph ports.

    Returns:
        ProactiveDialogueTick adapter ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.proactive_memory_read_repository import (
        Neo4jProactiveMemoryReadRepository,
    )

    engine_config = get_engine_model_config_for("proactive_dialogue")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, get_settings()))
    graph_db = get_graph_db()
    location_reader = get_player_location_reader()
    engine = ProactiveDialogueEngine(
        llm_client=llm_client,
        memory_service=Neo4jProactiveMemoryReadRepository(graph_db),
        location_service=location_reader,
    )
    return ProactiveDialogueTick(
        engine=engine,
        location_reader=location_reader,
        proactive_queue=get_proactive_queue(),
    )


@lru_cache
def get_intent_formation_engine() -> IntentFormationEngine:
    """Create singleton IntentFormationEngine wired to the shared graph ports.

    Returns:
        IntentFormationEngine ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.intent_repository import Neo4jIntentRepository

    graph_db = get_graph_db()
    return IntentFormationEngine(
        location_reader=get_player_location_reader(),
        intent_repo=Neo4jIntentRepository(graph_db),
    )


@lru_cache
def get_player_model_tick() -> PlayerModelTick:
    """Create singleton PlayerModelTick adapter for the tick scheduler (F1.4).

    Returns:
        PlayerModelTick wired to a pure PlayerModelEngine and the injected graph ports.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.player_model_repository import (
        Neo4jPlayerModelRepository,
    )

    graph_db = get_graph_db()
    return PlayerModelTick(
        engine=PlayerModelEngine(),
        location_reader=get_player_location_reader(),
        relation_reader=get_relation_reader(),
        model_repo=Neo4jPlayerModelRepository(graph_db),
    )


@lru_cache
def get_director_beat_log() -> DirectorBeatLog:
    """Return the shared DirectorBeatLog singleton (F2.4).

    Returns:
        DirectorBeatLog shared across the director tick and the API read route.
    """
    return DirectorBeatLog()


@lru_cache
def get_director_tick() -> DirectorTick:
    """Create singleton DirectorTick adapter for the tick scheduler (F1.5).

    Returns:
        DirectorTick wired to the injected read ports and the singleton EventHandler.
    """
    return DirectorTick(
        location_reader=get_player_location_reader(),
        relation_reader=get_relation_reader(),
        event_handler=get_event_handler(),
        beat_log=get_director_beat_log(),
    )


@lru_cache
def get_scheme_advance_tick() -> SchemeAdvanceTick:
    """Create singleton SchemeAdvanceTick adapter for the tick scheduler (F1.6 / DEC-107 A).

    Returns:
        SchemeAdvanceTick wired to settings + the singleton TypeRegistry.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return SchemeAdvanceTick(
        settings=get_settings(),
        registry=get_type_registry(),
        scheming_repo=Neo4jSchemingRepository(graph_db=get_graph_db()),
    )


@lru_cache
def get_scheme_detection_tick() -> SchemeDetectionTick:
    """Create singleton SchemeDetectionTick adapter for the tick scheduler (F1.6).

    Returns:
        SchemeDetectionTick wired to settings + Neo4jSchemingRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return SchemeDetectionTick(
        settings=get_settings(),
        scheming_repo=Neo4jSchemingRepository(graph_db=get_graph_db()),
    )


@lru_cache
def get_memory_decay_tick() -> MemoryDecayTick:
    """Create singleton MemoryDecayTick adapter for scheduled forgetting-decay (F1.7).

    Returns:
        MemoryDecayTick wired to a MemoryEngine and the configured decay interval.
    """
    return MemoryDecayTick(
        memory_engine=get_memory_engine(),
        interval=get_settings().MEMORY_DECAY_TICK_INTERVAL,
    )


@lru_cache
def get_goal_formation_engine() -> GoalFormerAdapter:
    """Create singleton GoalFormerAdapter for GOAP goal formation each tick.

    Returns:
        GoalFormerAdapter backed by the injected planning + shared read ports.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.planning_repository import Neo4jPlanningRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    graph_db = get_graph_db()
    planning_repo = Neo4jPlanningRepository(graph_db)
    return GoalFormerAdapter(
        goal_former=GoalFormer(planning_repo=planning_repo),
        action_selector=ActionSelector(planning_repo=planning_repo),
        character_reader=Neo4jCharacterReadRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
    )


@lru_cache
def get_reputation_engine() -> ReputationTickAdapter:
    """Create singleton ReputationTickAdapter loaded from reputation_rules.yaml.

    Returns:
        ReputationTickAdapter ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from pathlib import Path

    rules_path = (
        Path(__file__).resolve().parent.parent.parent
        / "engines"
        / "reputation"
        / "reputation_rules.yaml"
    )
    config = load_propagation_config(rules_path)
    graph_db = get_graph_db()
    reputation_engine = ReputationEngine(
        config=config,
        relation_reader=get_relation_reader(),
        reputation_repo=Neo4jReputationRepository(graph_db),
    )
    settings = get_settings()
    return ReputationTickAdapter(
        engine=reputation_engine,
        character_reader=Neo4jCharacterReadRepository(graph_db),
        player_id=settings.WORLD_ID,
        config=config,
    )
