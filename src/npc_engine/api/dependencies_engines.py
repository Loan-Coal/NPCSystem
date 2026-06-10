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
from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick
from npc_engine.engines.agenda.intent_formation_engine import IntentFormationEngine
from npc_engine.engines.planning.goal_former_adapter import GoalFormerAdapter
from npc_engine.graph.player_location_reader import PlayerLocationReader
from npc_engine.graph.proactive_memory_reader import ProactiveMemoryReader
from npc_engine.graph.character_reader import get_npc_ids as _graph_get_npc_ids
from npc_engine.graph.reputation_nudge import apply_trust_nudge
from npc_engine.graph.relation_reader import RelationReader
from npc_engine.scheduler.tick_scheduler import TickScheduler


@lru_cache
def get_gossip_handler() -> GossipHandler:
    """Create singleton gossip handler with shared embedding index.

    Returns:
        GossipHandler wired to the singleton EmbeddingIndex.
    """
    settings = get_settings()
    return GossipHandler(
        settings=settings,
        embedding_index=get_embedding_index(),
        weight_config=load_gossip_config(),
        emotion_updater=get_emotion_updater(),
    )


@lru_cache
def get_event_handler() -> EventHandler:
    """Create singleton event handler with shared embedding index and registry.

    Returns:
        EventHandler wired to the singleton EmbeddingIndex and TypeRegistry.
    """
    settings = get_settings()
    return EventHandler(settings=settings, embedding_index=get_embedding_index(), registry=get_type_registry())


@lru_cache
def get_quest_chain_resolver() -> QuestChainResolver:
    """Create singleton QuestChainResolver wired to the shared QuestOfferService.

    Returns:
        QuestChainResolver with a QuestChainOfferAdapter backed by the singleton QuestOfferService.
    """
    adapter = QuestChainOfferAdapter(offer_service=get_quest_offer_service())
    return QuestChainResolver(offer_service=adapter)


@lru_cache
def get_quest_lifecycle_engine() -> QuestLifecycleEngine:
    """Create singleton quest lifecycle engine with shared type registry and chain resolver.

    Returns:
        QuestLifecycleEngine wired to the singleton TypeRegistry and QuestChainResolver.
    """
    settings = get_settings()
    return QuestLifecycleEngine(
        settings=settings,
        registry=get_type_registry(),
        chain_resolver=get_quest_chain_resolver(),
    )


@lru_cache
def get_quest_offer_service() -> QuestOfferService:
    """Create singleton quest offer service with shared type registry.

    Returns:
        QuestOfferService wired to the singleton TypeRegistry.
    """
    settings = get_settings()
    return QuestOfferService(settings=settings, registry=get_type_registry())


@lru_cache
def get_quest_reward_router() -> QuestRewardRouter:
    """Create singleton quest reward router with shared type registry.

    Returns:
        QuestRewardRouter wired to the singleton TypeRegistry.
    """
    settings = get_settings()
    return QuestRewardRouter(settings=settings, registry=get_type_registry())


@lru_cache
def get_quest_generation_engine() -> QuestGenerationEngine:
    """Create singleton quest generation engine with LLM client and loaded templates.

    Returns:
        QuestGenerationEngine wired to the shared LLM client and bundled templates.
    """
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
    )


@lru_cache
def get_event_quest_trigger() -> EventQuestTrigger:
    """Create singleton EventQuestTrigger wired to the shared quest generation engine.

    Returns:
        EventQuestTrigger instance using default trigger event types and military archetypes.
    """
    return EventQuestTrigger(generation_engine=get_quest_generation_engine())


@lru_cache
def get_need_quest_trigger() -> NeedQuestTrigger:
    """Create singleton NeedQuestTrigger wired to the shared quest generation engine.

    Returns:
        NeedQuestTrigger instance using the default need threshold.
    """
    return NeedQuestTrigger(generation_engine=get_quest_generation_engine())


@lru_cache
def get_world_state_quest_trigger() -> WorldStateQuestTrigger:
    """Create singleton WorldStateQuestTrigger wired to the shared quest generation engine.

    Returns:
        WorldStateQuestTrigger instance using the default max-per-tick of 1.
    """
    return WorldStateQuestTrigger(generation_engine=get_quest_generation_engine())


@lru_cache
def get_pricing_engine() -> PricingEngine:
    """Create singleton pricing engine loaded from pricing_rules.yaml.

    Returns:
        PricingEngine wired to the bundled pricing_rules.yaml.
    """
    rules_path = Path(__file__).resolve().parent.parent / "engines" / "economy" / "pricing_rules.yaml"
    rules = load_pricing_rules(rules_path)
    return PricingEngine(rules=rules)


@lru_cache
def get_trade_engine() -> TradeEngine:
    """Create singleton trade engine wired to the shared pricing engine.

    Returns:
        TradeEngine wired to the singleton PricingEngine.
    """
    return TradeEngine(pricing_engine=get_pricing_engine())


@lru_cache
def get_faction_politics_engine() -> FactionPoliticsEngine:
    """Create singleton faction politics engine loaded from rules.yaml.

    Returns:
        FactionPoliticsEngine wired to the bundled rules.yaml.
    """
    rules_path = Path(__file__).resolve().parent.parent / "engines" / "faction_politics" / "rules.yaml"
    rules = load_rules(rules_path)
    return FactionPoliticsEngine(rules=rules)


@lru_cache
def get_story_pacing_engine() -> StoryPacingEngine:
    """Create singleton story pacing engine loaded from pacing_rules.yaml.

    Returns:
        StoryPacingEngine wired to the bundled pacing_rules.yaml.
    """
    rules_path = Path(__file__).resolve().parent.parent / "engines" / "story_pacing" / "pacing_rules.yaml"
    rules = load_pacing_rules(rules_path)
    return StoryPacingEngine(rules=rules)


@lru_cache
def get_routine_engine() -> RoutineEngine:
    """Create singleton routine engine for tick-driven NPC location updates.

    Returns:
        RoutineEngine instance used by the tick scheduler.
    """
    return RoutineEngine()


@lru_cache
def get_proactive_dialogue_engine() -> ProactiveDialogueTick:
    """Create singleton ProactiveDialogueTick wired to the shared LLM client and graph readers.

    Returns:
        ProactiveDialogueTick adapter ready for the tick scheduler.
    """
    engine_config = get_engine_model_config_for("proactive_dialogue")
    llm_client = _register_adapter(create_llm_client_for_engine(engine_config, get_settings()))
    memory_reader = ProactiveMemoryReader()
    location_reader = PlayerLocationReader()
    engine = ProactiveDialogueEngine(
        llm_client=llm_client,
        memory_service=memory_reader,
        location_service=location_reader,
    )
    return ProactiveDialogueTick(engine=engine, location_reader=location_reader)


@lru_cache
def get_intent_formation_engine() -> IntentFormationEngine:
    """Create singleton IntentFormationEngine wired to the shared location reader.

    Returns:
        IntentFormationEngine ready for the tick scheduler.
    """
    return IntentFormationEngine(location_reader=PlayerLocationReader())


@lru_cache
def get_goal_formation_engine() -> GoalFormerAdapter:
    """Create singleton GoalFormerAdapter for GOAP goal formation each tick.

    Returns:
        GoalFormerAdapter backed by a default GoalFormer instance.
    """
    return GoalFormerAdapter()


class _CharacterReaderWrapper:
    """Module-level adapter exposing get_npc_ids as a method for DI into ReputationTickAdapter.

    Wraps the graph.character_reader.get_npc_ids module function behind the
    _CharacterReaderProtocol interface expected by ReputationTickAdapter.
    """

    async def get_npc_ids(self, session) -> list[str]:
        """Return IDs of all active non-player characters.

        Args:
            session: Active Neo4j async session.

        Returns:
            List of NPC ID strings.
        """
        return await _graph_get_npc_ids(session)


_character_reader_singleton = _CharacterReaderWrapper()


@lru_cache
def get_reputation_engine() -> ReputationTickAdapter:
    """Create singleton ReputationTickAdapter loaded from reputation_rules.yaml.

    Wires RelationReader factory and apply_trust_nudge (graph layer) into
    ReputationEngine via ReputationTickAdapter.  RelationReader is constructed
    fresh each tick via the relation_reader_factory to avoid session leakage.

    Returns:
        ReputationTickAdapter ready for the tick scheduler.
    """
    rules_path = (
        Path(__file__).resolve().parent.parent
        / "engines"
        / "reputation"
        / "reputation_rules.yaml"
    )
    config = load_propagation_config(rules_path)
    reputation_engine = ReputationEngine(
        config=config,
        relation_reader=_character_reader_singleton,  # replaced per-tick by factory
        apply_nudge_fn=apply_trust_nudge,
    )
    settings = get_settings()
    return ReputationTickAdapter(
        engine=reputation_engine,
        character_reader=_character_reader_singleton,
        player_id=settings.WORLD_ID,
        config=config,
        relation_reader_factory=RelationReader,
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
        engine_status_store=get_engine_status_store(),
        gossip_interval=settings.GOSSIP_TICK_INTERVAL,
        event_interval=settings.EVENT_TICK_INTERVAL,
        chapter_interval=settings.CHAPTER_TICK_INTERVAL,
        distributed_lease_enabled=settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        scheduler_id=settings.TICK_SCHEDULER_ID,
        lease_owner_id=settings.TICK_LEASE_OWNER_ID,
        lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
    )
