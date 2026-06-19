"""
Module: dependencies_engines.quest
Layer: api
Purpose: Singleton factory providers for quest-family engines —
         quest lifecycle, chain resolver, offer service, reward router,
         quest generation, and generation triggers.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: infra singletons + get_memory_engine from core submodule.
Used by: api.dependencies_engines (package __init__).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from npc_engine.api.dependencies_engines.core import get_memory_engine
from npc_engine.api.dependencies_infra import _register_adapter, get_type_registry
from npc_engine.config import get_settings
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_runtime_config import get_config as get_engine_model_config_for
from npc_engine.engines.quest.quest_chain_offer_adapter import QuestChainOfferAdapter
from npc_engine.engines.quest.quest_chain_resolver import QuestChainResolver
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.engines.quest.quest_offer_service import QuestOfferService
from npc_engine.engines.quest.quest_reward_router import QuestRewardRouter
from npc_engine.engines.quest_generation.event_quest_trigger import EventQuestTrigger
from npc_engine.engines.quest_generation.need_quest_trigger import NeedQuestTrigger
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.engines.quest_generation.template_loader import load_templates
from npc_engine.engines.quest_generation.world_state_quest_trigger import WorldStateQuestTrigger
from npc_engine.graph.repositories.interaction_repository import Neo4jInteractionRepository


@lru_cache
def get_quest_chain_resolver() -> QuestChainResolver:
    """Create singleton QuestChainResolver wired to the shared QuestOfferService and chain repo.

    Returns:
        QuestChainResolver with QuestChainOfferAdapter backed by QuestOfferService
        and Neo4jQuestChainRepository for UNLOCKS graph reads.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_repository import Neo4jQuestChainRepository

    chain_repo = Neo4jQuestChainRepository(get_graph_db())
    adapter = QuestChainOfferAdapter(offer_service=get_quest_offer_service(), chain_repo=chain_repo)
    return QuestChainResolver(offer_service=adapter, chain_repo=chain_repo)


@lru_cache
def get_quest_lifecycle_engine() -> QuestLifecycleEngine:
    """Create singleton quest lifecycle engine with shared type registry and chain resolver.

    Returns:
        QuestLifecycleEngine wired to the singleton TypeRegistry, QuestChainResolver,
        the shared MemoryEngine, and a Neo4jQuestLifecycleRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_repository import Neo4jQuestLifecycleRepository

    settings = get_settings()
    return QuestLifecycleEngine(
        settings=settings,
        registry=get_type_registry(),
        chain_resolver=get_quest_chain_resolver(),
        memory_engine=get_memory_engine(),
        quest_repo=Neo4jQuestLifecycleRepository(get_graph_db()),
    )


@lru_cache
def get_interaction_graph_repo() -> Neo4jInteractionRepository:
    """Create the interaction graph read adapter (InteractionGraphPort).

    Returns:
        Neo4jInteractionRepository wrapping the singleton GraphDB.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return Neo4jInteractionRepository(get_graph_db())


@lru_cache
def get_quest_offer_service() -> QuestOfferService:
    """Create singleton quest offer service with shared type registry and offer repo.

    Returns:
        QuestOfferService wired to the singleton TypeRegistry and Neo4jQuestOfferRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_repository import Neo4jQuestOfferRepository

    settings = get_settings()
    return QuestOfferService(
        settings=settings,
        registry=get_type_registry(),
        quest_offer_repo=Neo4jQuestOfferRepository(get_graph_db()),
    )


@lru_cache
def get_quest_reward_router() -> QuestRewardRouter:
    """Create singleton quest reward router with shared type registry and reward repo.

    Returns:
        QuestRewardRouter wired to the singleton TypeRegistry and Neo4jQuestRewardRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_reward_repository import Neo4jQuestRewardRepository

    settings = get_settings()
    return QuestRewardRouter(
        settings=settings,
        registry=get_type_registry(),
        quest_reward_repo=Neo4jQuestRewardRepository(get_graph_db()),
    )


@lru_cache
def get_quest_generation_engine() -> QuestGenerationEngine:
    """Create singleton quest generation engine with LLM client, templates, and gen repo.

    Returns:
        QuestGenerationEngine wired to the shared LLM client, bundled templates, and
        Neo4jQuestGenerationRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jQuestGenerationRepository

    engine_config = get_engine_model_config_for("quest_generation")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, get_settings()))
    prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts" / "quest_generation"
    templates_dir = prompts_dir / "templates"
    templates = load_templates(templates_dir)
    return QuestGenerationEngine(
        llm_client=llm_client,
        templates=templates,
        prompts_dir=prompts_dir,
        max_tokens=engine_config.llm.max_tokens,
        quest_gen_repo=Neo4jQuestGenerationRepository(get_graph_db()),
    )


@lru_cache
def get_event_quest_trigger() -> EventQuestTrigger:
    """Create singleton EventQuestTrigger wired to the shared quest generation engine.

    Returns:
        EventQuestTrigger using default trigger event types and military archetypes.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jEventTriggerRepository

    return EventQuestTrigger(
        generation_engine=get_quest_generation_engine(),
        trigger_repo=Neo4jEventTriggerRepository(get_graph_db()),
    )


@lru_cache
def get_need_quest_trigger() -> NeedQuestTrigger:
    """Create singleton NeedQuestTrigger wired to the shared quest generation engine.

    Returns:
        NeedQuestTrigger instance using the default need threshold.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jNeedTriggerRepository

    return NeedQuestTrigger(
        generation_engine=get_quest_generation_engine(),
        need_trigger_repo=Neo4jNeedTriggerRepository(get_graph_db()),
    )


@lru_cache
def get_world_state_quest_trigger() -> WorldStateQuestTrigger:
    """Create singleton WorldStateQuestTrigger wired to the shared quest generation engine.

    Returns:
        WorldStateQuestTrigger instance using the default max-per-tick of 1.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jEventTriggerRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    graph_db = get_graph_db()
    return WorldStateQuestTrigger(
        generation_engine=get_quest_generation_engine(),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
        trigger_repo=Neo4jEventTriggerRepository(graph_db),
    )
