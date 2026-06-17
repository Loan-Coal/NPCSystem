"""
Module: dependencies_engines
Layer: api
Purpose: Singleton factory providers for core domain engines —
         gossip, events, quest, quest-generation, economy, faction, pacing, routine, scheduler,
         proactive dialogue (EXP-10 s2), reputation propagation (EXP-52 s2).
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: infra + store singletons from dependencies_infra / dependencies_stores.
Used by: api.dependency_singletons (re-exporter)

Line-count note: this file is the sole composition root for all engine singletons.
Splitting into sub-modules would fragment a cohesive wiring responsibility that has no
natural seam. See DECISIONS.md (DEC-042 rationale applies equally here).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from npc_engine.api.dependencies_infra import (
    _register_adapter,
    get_type_registry,
)
from npc_engine.config import get_settings
from npc_engine.api.dependencies_stores import (
    get_embedding_index,
    get_emotion_updater,
    get_engine_status_store,
    get_game_clock,
)
from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.pricing_rules_loader import load_pricing_rules
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.faction_politics.faction_politics_engine import FactionPoliticsEngine
from npc_engine.engines.faction_politics.rules_loader import load_rules
from npc_engine.engines.gossip.gossip_config import load_gossip_config
from npc_engine.engines.gossip.gossip_handler import GossipHandler
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
from npc_engine.engines.quest_generation.world_state_quest_trigger import WorldStateQuestTrigger
from npc_engine.engines.quest_generation.template_loader import load_templates
from npc_engine.engines.reputation.propagation_config import load_propagation_config
from npc_engine.engines.reputation.reputation_engine import ReputationEngine
from npc_engine.engines.reputation.reputation_tick_adapter import ReputationTickAdapter
from npc_engine.engines.routine.routine_engine import RoutineEngine
from npc_engine.engines.story_pacing.pacing_rules_loader import load_pacing_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.engines.proactive_dialogue.proactive_engine import ProactiveDialogueEngine
from npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue
from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick
from npc_engine.engines.player_model.player_model_engine import PlayerModelEngine
from npc_engine.engines.player_model.player_model_tick import PlayerModelTick
from npc_engine.engines.director.director_tick import DirectorTick
from npc_engine.engines.director.director_beat_log import DirectorBeatLog
from npc_engine.engines.scheming.scheme_advance_tick import SchemeAdvanceTick
from npc_engine.graph.repositories.scheming_repository import Neo4jSchemingRepository
from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick
from npc_engine.engines.memory.memory_engine import MemoryEngine
from npc_engine.engines.memory.memory_decay_tick import MemoryDecayTick
from npc_engine.engines.agenda.intent_formation_engine import IntentFormationEngine
from npc_engine.engines.planning.action_selector import ActionSelector
from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.engines.planning.goal_former_adapter import GoalFormerAdapter
from npc_engine.graph.repositories.character_read_repository import (
    Neo4jCharacterReadRepository,
)
from npc_engine.graph.repositories.interaction_repository import (
    Neo4jInteractionRepository,
)
from npc_engine.graph.repositories.relation_read_repository import (
    Neo4jRelationReadRepository,
)
from npc_engine.graph.repositories.reputation_repository import Neo4jReputationRepository
from npc_engine.scheduler.tick_scheduler import TickScheduler


@lru_cache
def get_gossip_handler() -> GossipHandler:
    """Create singleton gossip handler with shared embedding index and graph port.

    Returns:
        GossipHandler wired to the singleton EmbeddingIndex and Neo4jGossipRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.gossip_repository import Neo4jGossipRepository

    settings = get_settings()
    return GossipHandler(
        settings=settings,
        embedding_index=get_embedding_index(),
        weight_config=load_gossip_config(),
        emotion_updater=get_emotion_updater(),
        gossip_repo=Neo4jGossipRepository(get_graph_db()),
    )


@lru_cache
def get_event_handler() -> EventHandler:
    """Create singleton event handler with shared embedding index and registry.

    Returns:
        EventHandler wired to the singleton EmbeddingIndex and TypeRegistry.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.event_repository import Neo4jEventRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    settings = get_settings()
    graph_db = get_graph_db()
    return EventHandler(
        settings=settings,
        embedding_index=get_embedding_index(),
        event_repo=Neo4jEventRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
        registry=get_type_registry(),
    )


@lru_cache
def get_quest_chain_resolver() -> QuestChainResolver:
    """Create singleton QuestChainResolver wired to the shared QuestOfferService and chain repo.

    Returns:
        QuestChainResolver with a QuestChainOfferAdapter backed by the singleton QuestOfferService
        and a Neo4jQuestChainRepository for UNLOCKS graph reads.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_repository import Neo4jQuestChainRepository

    chain_repo = Neo4jQuestChainRepository(get_graph_db())
    adapter = QuestChainOfferAdapter(offer_service=get_quest_offer_service(), chain_repo=chain_repo)
    return QuestChainResolver(offer_service=adapter, chain_repo=chain_repo)


@lru_cache
def get_memory_engine() -> MemoryEngine:
    """Return the shared MemoryEngine singleton wired to the Neo4j memory adapter.

    Single source for the MemoryEngine across the clock/memories routes, dialogue,
    quest lifecycle, and decay tick — depends on the MemoryGraphPort abstraction so
    the engine holds no Neo4j session (DEC-122 / SEV-24).

    Returns:
        MemoryEngine injected with a Neo4jMemoryRepository over the singleton GraphDB.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.memory_repository import Neo4jMemoryRepository

    return MemoryEngine(memory_repo=Neo4jMemoryRepository(get_graph_db()))


@lru_cache
def get_quest_lifecycle_engine() -> QuestLifecycleEngine:
    """Create singleton quest lifecycle engine with shared type registry and chain resolver.

    Returns:
        QuestLifecycleEngine wired to the singleton TypeRegistry, QuestChainResolver,
        the shared MemoryEngine, and a Neo4jQuestLifecycleRepository (DEC-122 / SEV-24).
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
    """Create the interaction graph read adapter (InteractionGraphPort) (SEV-24).

    Returns:
        Neo4jInteractionRepository wrapping the singleton GraphDB; interaction
        quest handlers use this port for reads while QuestLifecycleEngine is sessionless.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return Neo4jInteractionRepository(get_graph_db())


@lru_cache
def get_quest_offer_service() -> QuestOfferService:
    """Create singleton quest offer service with shared type registry and offer repo.

    Returns:
        QuestOfferService wired to the singleton TypeRegistry and Neo4jQuestOfferRepository
        (DEC-122 / SEV-24).
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
        QuestRewardRouter wired to the singleton TypeRegistry and Neo4jQuestRewardRepository
        (DEC-122 / SEV-24).
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
        Neo4jQuestGenerationRepository (DEC-122 / SEV-24).
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jQuestGenerationRepository

    engine_config = get_engine_model_config_for("quest_generation")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, get_settings()))
    prompts_dir = Path(__file__).resolve().parent.parent / "prompts" / "quest_generation"
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
    """Create singleton EventQuestTrigger wired to the shared quest generation engine and trigger repo.

    Returns:
        EventQuestTrigger instance using default trigger event types and military archetypes.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.quest_generation_repository import Neo4jEventTriggerRepository

    return EventQuestTrigger(
        generation_engine=get_quest_generation_engine(),
        trigger_repo=Neo4jEventTriggerRepository(get_graph_db()),
    )


@lru_cache
def get_need_quest_trigger() -> NeedQuestTrigger:
    """Create singleton NeedQuestTrigger wired to the shared quest generation engine and need repo.

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
    """Create singleton WorldStateQuestTrigger wired to the shared quest generation engine and repos.

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


@lru_cache
def get_pricing_engine() -> PricingEngine:
    """Create singleton pricing engine loaded from pricing_rules.yaml.

    Returns:
        PricingEngine wired to the bundled pricing_rules.yaml.
    """
    rules_path = Path(__file__).resolve().parent.parent / "engines" / "economy" / "pricing_rules.yaml"
    rules = load_pricing_rules(rules_path)
    return PricingEngine(rules=rules)


def get_trade_engine() -> TradeEngine:
    """Create a per-request trade engine wired to the shared pricing engine + economy port.

    Not a singleton: built fresh per request as the route's Depends factory, injecting the
    Neo4jEconomyRepository (EconomyGraphPort) so the engine holds no session (DEC-122 / SEV-24).

    Returns:
        TradeEngine wired to the singleton PricingEngine and a Neo4jEconomyRepository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.economy_repository import Neo4jEconomyRepository

    return TradeEngine(
        pricing_engine=get_pricing_engine(),
        economy_repo=Neo4jEconomyRepository(get_graph_db()),
    )


@lru_cache
def get_faction_politics_engine() -> FactionPoliticsEngine:
    """Create singleton faction politics engine loaded from rules.yaml.

    Depends on the FactionPoliticsGraphPort abstraction so the engine holds no Neo4j
    session (DEC-122 / SEV-24).

    Returns:
        FactionPoliticsEngine wired to the bundled rules.yaml and a Neo4j repository.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.faction_politics_repository import (
        Neo4jFactionPoliticsRepository,
    )

    rules_path = Path(__file__).resolve().parent.parent / "engines" / "faction_politics" / "rules.yaml"
    rules = load_rules(rules_path)
    return FactionPoliticsEngine(rules=rules, repo=Neo4jFactionPoliticsRepository(get_graph_db()))


@lru_cache
def get_story_pacing_engine() -> StoryPacingEngine:
    """Create singleton story pacing engine loaded from pacing_rules.yaml.

    Wires the Neo4j graph adapters (Neo4jStoryPacingRepository + the shared
    Neo4jWorldStateRepository) as the engine's injected ports (DEC-122 / SEV-24) so the
    engine holds no Neo4j session.

    Returns:
        StoryPacingEngine wired to the bundled pacing_rules.yaml.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.story_pacing_repository import Neo4jStoryPacingRepository
    from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

    rules_path = Path(__file__).resolve().parent.parent / "engines" / "story_pacing" / "pacing_rules.yaml"
    rules = load_pacing_rules(rules_path)
    graph_db = get_graph_db()
    return StoryPacingEngine(
        rules=rules,
        story_pacing_repo=Neo4jStoryPacingRepository(graph_db),
        world_state_repo=Neo4jWorldStateRepository(graph_db),
    )


@lru_cache
def get_routine_engine() -> RoutineEngine:
    """Create singleton routine engine for tick-driven NPC location updates.

    Wires the Neo4j graph adapter (Neo4jRoutineRepository) as the engine's injected
    RoutineGraphPort (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        RoutineEngine instance used by the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.routine_repository import Neo4jRoutineRepository

    return RoutineEngine(routine_repo=Neo4jRoutineRepository(get_graph_db()))


@lru_cache
def get_proactive_queue() -> ProactiveQueue:
    """Return the shared ProactiveQueue singleton (DEC-098 / F1.2).

    The tick adapter enqueues routed proactive lines here; the WS drain loop
    reads from it.  A single lru_cache instance ensures both sides share state.

    Returns:
        ProactiveQueue singleton used across the full proactive-dialogue path.
    """
    return ProactiveQueue()


@lru_cache
def get_proactive_dialogue_engine() -> ProactiveDialogueTick:
    """Create singleton ProactiveDialogueTick wired to the shared LLM client and graph ports.

    Wires the Neo4jProactiveMemoryReadRepository (unshared-memory reads) and the shared
    Neo4jPlayerLocationReadRepository (idle ticks + co-located pairs) as engine-layer Ports
    (DEC-122 / SEV-24) so neither the engine nor the tick adapter holds a Neo4j session.

    Returns:
        ProactiveDialogueTick adapter ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )
    from npc_engine.graph.repositories.proactive_memory_read_repository import (
        Neo4jProactiveMemoryReadRepository,
    )

    engine_config = get_engine_model_config_for("proactive_dialogue")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, get_settings()))
    graph_db = get_graph_db()
    location_reader = Neo4jPlayerLocationReadRepository(graph_db)
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

    Wires the shared Neo4jPlayerLocationReadRepository (co-located pairs) and the
    Neo4jIntentRepository (trigger reads + queue writes) as engine-layer Ports
    (DEC-122 / SEV-24) so the engine holds no Neo4j session.

    Returns:
        IntentFormationEngine ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.intent_repository import Neo4jIntentRepository
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )

    graph_db = get_graph_db()
    return IntentFormationEngine(
        location_reader=Neo4jPlayerLocationReadRepository(graph_db),
        intent_repo=Neo4jIntentRepository(graph_db),
    )


@lru_cache
def get_player_model_tick() -> PlayerModelTick:
    """Create singleton PlayerModelTick adapter for the tick scheduler (F1.4).

    Wires the shared Neo4j read adapters (Neo4jPlayerLocationReadRepository +
    Neo4jRelationReadRepository) and the Neo4jPlayerModelRepository write adapter as the
    engine-layer Ports (DEC-122 / SEV-24) so the adapter holds no Neo4j session.

    Returns:
        PlayerModelTick wired to a pure PlayerModelEngine and the injected graph ports.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )
    from npc_engine.graph.repositories.player_model_repository import (
        Neo4jPlayerModelRepository,
    )

    graph_db = get_graph_db()
    return PlayerModelTick(
        engine=PlayerModelEngine(),
        location_reader=Neo4jPlayerLocationReadRepository(graph_db),
        relation_reader=Neo4jRelationReadRepository(graph_db),
        model_repo=Neo4jPlayerModelRepository(graph_db),
    )


@lru_cache
def get_director_tick() -> DirectorTick:
    """Create singleton DirectorTick adapter for the tick scheduler (F1.5).

    Wires the shared Neo4j read adapters (Neo4jPlayerLocationReadRepository +
    Neo4jRelationReadRepository) as the engine-layer read Ports (DEC-122 / SEV-24); the
    director still forwards the scheduler session to the EventHandler until events migrates.

    Returns:
        DirectorTick wired to the injected read ports and the singleton EventHandler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db
    from npc_engine.graph.repositories.player_location_read_repository import (
        Neo4jPlayerLocationReadRepository,
    )

    graph_db = get_graph_db()
    return DirectorTick(
        location_reader=Neo4jPlayerLocationReadRepository(graph_db),
        relation_reader=Neo4jRelationReadRepository(graph_db),
        event_handler=get_event_handler(),
        beat_log=get_director_beat_log(),
    )


@lru_cache
def get_scheme_advance_tick() -> SchemeAdvanceTick:
    """Create singleton SchemeAdvanceTick adapter for the tick scheduler (F1.6 / DEC-107 A).

    Returns:
        SchemeAdvanceTick wired to settings + the singleton TypeRegistry (validated
        covert-event creation).
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
        SchemeDetectionTick wired to settings + Neo4jSchemingRepository (DEC-122).
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    return SchemeDetectionTick(
        settings=get_settings(),
        scheming_repo=Neo4jSchemingRepository(graph_db=get_graph_db()),
    )


@lru_cache
def get_director_beat_log() -> DirectorBeatLog:
    """Return the shared DirectorBeatLog singleton (F2.4).

    The director tick records fired beats here; the dialogue route reads recent beats.

    Returns:
        DirectorBeatLog shared across the director tick and the API read route.
    """
    return DirectorBeatLog()


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

    Wires the new Neo4jPlanningRepository (PlanningGraphPort) into GoalFormer +
    ActionSelector and the shared Neo4jCharacterReadRepository / Neo4jWorldStateRepository
    read ports into the adapter (DEC-122 / SEV-24) so no planning engine holds a session.

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

    Wires the Neo4j read/write adapters (Neo4jRelationReadRepository +
    Neo4jReputationRepository into the engine, Neo4jCharacterReadRepository into the
    tick adapter) as the engine-layer Ports (DEC-122 / SEV-24) so neither the engine
    nor the adapter holds a Neo4j session.

    Returns:
        ReputationTickAdapter ready for the tick scheduler.
    """
    from npc_engine.api.dependencies_infra import get_graph_db

    rules_path = (
        Path(__file__).resolve().parent.parent
        / "engines"
        / "reputation"
        / "reputation_rules.yaml"
    )
    config = load_propagation_config(rules_path)
    graph_db = get_graph_db()
    reputation_engine = ReputationEngine(
        config=config,
        relation_reader=Neo4jRelationReadRepository(graph_db),
        reputation_repo=Neo4jReputationRepository(graph_db),
    )
    settings = get_settings()
    return ReputationTickAdapter(
        engine=reputation_engine,
        character_reader=Neo4jCharacterReadRepository(graph_db),
        player_id=settings.WORLD_ID,
        config=config,
    )


@lru_cache
def get_tick_scheduler() -> TickScheduler:
    """Create singleton tick scheduler with shared gossip, event, and routine handlers.

    Returns:
        TickScheduler wired to shared clock, gossip, event, and routine singletons.
    """
    from npc_engine.api.dependencies_advanced import (
        get_agenda_engine,
        get_chapter_engine,
        get_clique_formation_engine,
        get_military_engine,
        get_mood_contagion_engine,
        get_need_decay_engine,
        get_oath_engine,
        get_skill_progression_engine,
        get_succession_engine,
        get_treaty_engine,
    )

    settings = get_settings()
    return TickScheduler(
        clock=get_game_clock(),
        gossip_handler=get_gossip_handler(),
        event_handler=get_event_handler(),
        routine_engine=get_routine_engine(),
        faction_politics_engine=get_faction_politics_engine(),
        story_pacing_engine=get_story_pacing_engine(),
        clique_formation_engine=get_clique_formation_engine(),
        skill_progression_engine=get_skill_progression_engine(),
        oath_engine=get_oath_engine(),
        treaty_engine=get_treaty_engine(),
        mood_contagion_engine=get_mood_contagion_engine(),
        chapter_engine=get_chapter_engine(),
        succession_engine=get_succession_engine(),
        agenda_engine=get_agenda_engine(),
        need_decay_engine=get_need_decay_engine(),
        military_engine=get_military_engine(),
        event_quest_trigger=get_event_quest_trigger(),
        need_quest_trigger=get_need_quest_trigger(),
        world_state_quest_trigger=get_world_state_quest_trigger(),
        proactive_dialogue_engine=get_proactive_dialogue_engine(),
        reputation_engine=get_reputation_engine(),
        intent_formation_engine=get_intent_formation_engine(),
        goal_formation_engine=get_goal_formation_engine(),
        player_model_engine=get_player_model_tick(),
        director_engine=get_director_tick(),
        memory_decay_engine=get_memory_decay_tick(),
        scheme_advance_engine=get_scheme_advance_tick(),
        scheme_detection_engine=get_scheme_detection_tick(),
        engine_status_store=get_engine_status_store(),
        gossip_interval=settings.GOSSIP_TICK_INTERVAL,
        event_interval=settings.EVENT_TICK_INTERVAL,
        chapter_interval=settings.CHAPTER_TICK_INTERVAL,
        distributed_lease_enabled=settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        scheduler_id=settings.TICK_SCHEDULER_ID,
        lease_owner_id=settings.TICK_LEASE_OWNER_ID,
        lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
    )
