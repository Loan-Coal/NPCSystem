"""
dependency_singletons.py - Singleton factory providers for long-lived application services.

Does NOT: create session-scoped or per-request dependencies.

Dependencies injected: Settings.
"""

from functools import lru_cache
from pathlib import Path

from npc_engine.cache.redis_runtime import RedisRuntime
from npc_engine.config import Settings, get_settings
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.gossip.gossip_config import load_gossip_config
from npc_engine.engines.gossip.gossip_handler import GossipHandler
from npc_engine.engines.idempotency.neo4j_store import Neo4jIdempotencyStore
from npc_engine.engines.idempotency.service import IdempotencyService
from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.economy.pricing_rules_loader import load_pricing_rules
from npc_engine.engines.economy.trade_engine import TradeEngine
from npc_engine.engines.faction_politics.faction_politics_engine import FactionPoliticsEngine
from npc_engine.engines.faction_politics.rules_loader import load_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.engines.story_pacing.pacing_rules_loader import load_pacing_rules
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.engines.quest_generation.template_loader import load_templates
from npc_engine.engines.routine.routine_engine import RoutineEngine
from npc_engine.graph.db import GraphDB
from npc_engine.graph.reindex_job_service import ReindexJobService
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache
from npc_engine.retrieval.embedding_index import EmbeddingIndex
from npc_engine.retrieval.vector_store_factory import create_vector_store
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.engines.llm_config_loader import get_config as get_engine_model_config_for
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.schema.llm_config_loader import load_llm_config
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.registry import build_type_registry
from npc_engine.engines.llm.factory import create_llm_client_for_engine


REGISTRY_SOURCES_SEPARATOR = ","

# LLM adapters registered here are closed on application shutdown via close_registered_llm_adapters().
_llm_adapters_to_close: list = []


def _register_adapter(adapter: object) -> object:
    """Register an LLM adapter for teardown and return it unchanged."""
    _llm_adapters_to_close.append(adapter)
    return adapter


async def close_registered_llm_adapters() -> None:
    """Close all registered LLM adapters; called from lifespan teardown."""
    for adapter in _llm_adapters_to_close:
        if hasattr(adapter, "close"):
            await adapter.close()
    _llm_adapters_to_close.clear()


@lru_cache
def get_graph_db() -> GraphDB:
    """Create singleton GraphDB connection manager.

    Returns:
        GraphDB instance configured from application settings.
    """
    settings = get_settings()
    return GraphDB(settings=settings)


@lru_cache
def get_session_store() -> SessionStore:
    """Create singleton dialogue session store.

    Returns:
        SessionStore configured with TTL and max-turns from application settings.
    """
    settings = get_settings()
    return SessionStore(ttl_seconds=settings.DIALOGUE_SESSION_TTL, max_turns=settings.DIALOGUE_SESSION_TURNS)


@lru_cache
def get_emotion_store() -> EmotionStore:
    """Create singleton in-memory emotion store.

    Returns:
        EmotionStore instance.
    """
    return EmotionStore()


@lru_cache
def get_emotion_updater() -> EmotionUpdater:
    """Create singleton emotion updater bound to the shared emotion store.

    Returns:
        EmotionUpdater wired to the singleton EmotionStore.
    """
    return EmotionUpdater(emotion_store=get_emotion_store())


@lru_cache
def get_embedding_index() -> EmbeddingIndex:
    """Create singleton embedding index backed by the configured vector store.

    Returns:
        EmbeddingIndex wrapping the configured VectorStore implementation.
    """
    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    return EmbeddingIndex(vector_store=vector_store)


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
def get_quest_lifecycle_engine() -> QuestLifecycleEngine:
    """Create singleton quest lifecycle engine with shared type registry.

    Returns:
        QuestLifecycleEngine wired to the singleton TypeRegistry.
    """
    settings = get_settings()
    return QuestLifecycleEngine(settings=settings, registry=get_type_registry())


@lru_cache
def get_game_clock() -> GameClock:
    """Create singleton game clock.

    Returns:
        GameClock configured with the application clock mode.
    """
    settings = get_settings()
    return GameClock(mode=settings.CLOCK_MODE)


@lru_cache
def get_faction_politics_engine() -> FactionPoliticsEngine:
    """Create singleton faction politics engine loaded from rules.yaml.

    Returns:
        FactionPoliticsEngine wired to the bundled rules.yaml.
    """
    from pathlib import Path
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
def get_routine_engine() -> RoutineEngine:
    """Create singleton routine engine for tick-driven NPC location updates.

    Returns:
        RoutineEngine instance used by the tick scheduler.
    """
    return RoutineEngine()


@lru_cache
def get_tick_scheduler() -> TickScheduler:
    """Create singleton tick scheduler with shared gossip, event, and routine handlers.

    Returns:
        TickScheduler wired to shared clock, gossip, event, and routine singletons.
    """
    settings = get_settings()
    return TickScheduler(
        clock=get_game_clock(),
        gossip_handler=get_gossip_handler(),
        event_handler=get_event_handler(),
        routine_engine=get_routine_engine(),
        faction_politics_engine=get_faction_politics_engine(),
        story_pacing_engine=get_story_pacing_engine(),
        gossip_interval=settings.GOSSIP_TICK_INTERVAL,
        event_interval=settings.EVENT_TICK_INTERVAL,
        distributed_lease_enabled=settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        scheduler_id=settings.TICK_SCHEDULER_ID,
        lease_owner_id=settings.TICK_LEASE_OWNER_ID,
        lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
    )


@lru_cache
def get_redis_runtime() -> RedisRuntime:
    """Create optional Redis runtime manager for non-idempotency caches.

    Returns:
        RedisRuntime instance; connection is deferred until connect() is called.
    """
    return RedisRuntime(settings=get_settings())


@lru_cache
def get_game_schema() -> SchemaConfig:
    """Load singleton game schema from configured path.

    Returns:
        Parsed SchemaConfig loaded from the GAME_SCHEMA_PATH setting.
    """
    settings = get_settings()
    return load_game_schema(schema_path=settings.GAME_SCHEMA_PATH)


def _resolve_registry_extension_sources(*, settings: Settings) -> tuple[str, ...]:
    """Resolve comma-delimited registry extension source values relative to project root.

    Args:
        settings: Application settings.

    Returns:
        Tuple of resolved absolute path strings for each extension source.
    """
    configured_sources = settings.TYPE_REGISTRY_EXTENSION_SOURCES
    if not configured_sources:
        return tuple()

    project_root = Path(__file__).resolve().parent.parent
    resolved_sources: list[str] = []
    for source in configured_sources.split(REGISTRY_SOURCES_SEPARATOR):
        source_value = source.strip()
        if not source_value:
            continue
        source_path = Path(source_value)
        if source_path.is_absolute():
            resolved_sources.append(str(source_path))
            continue
        resolved_sources.append(str((project_root / source_path).resolve(strict=False)))
    return tuple(resolved_sources)


@lru_cache
def get_type_registry() -> TypeRegistry:
    """Build immutable type registry singleton from base schema and extension sources.

    Returns:
        Fully resolved TypeRegistry singleton.
    """
    settings = get_settings()
    return build_type_registry(
        base_schema=get_game_schema(),
        extension_sources=_resolve_registry_extension_sources(settings=settings),
    )


@lru_cache
def get_llm_config() -> LLMConfig:
    """Load typed LLM configuration for prompt policy settings.

    Returns:
        LLMConfig loaded from the LLM_CONFIG_PATH setting.
    """
    settings = get_settings()
    return load_llm_config(config_path=settings.LLM_CONFIG_PATH)


@lru_cache
def get_dialogue_engine_model_config() -> EngineModelConfig:
    """Load the per-engine LLM config for the dialogue engine.

    Returns:
        EngineModelConfig from engines/dialogue/llm_config.yaml.
    """
    return get_engine_model_config_for("dialogue")


@lru_cache
def get_idempotency_store() -> Neo4jIdempotencyStore:
    """Create singleton idempotency persistence backend.

    Returns:
        Neo4jIdempotencyStore instance.
    """
    return Neo4jIdempotencyStore()


@lru_cache
def get_idempotency_service() -> IdempotencyService:
    """Create singleton idempotency service for middleware preflight and finalization.

    Returns:
        IdempotencyService wired to the singleton GraphDB and idempotency store.
    """
    return IdempotencyService(
        settings=get_settings(),
        graph_db=get_graph_db(),
        store=get_idempotency_store(),
    )


@lru_cache
def get_reindex_job_service() -> ReindexJobService:
    """Create singleton reindex job lifecycle manager.

    Returns:
        ReindexJobService instance.
    """
    return ReindexJobService()


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
def get_context_cache() -> DialogueContextCache:
    """Create singleton dialogue context cache.

    Returns:
        DialogueContextCache configured with the session TTL from application settings.
    """
    settings = get_settings()
    return DialogueContextCache(ttl_seconds=settings.DIALOGUE_SESSION_TTL)


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
        turn_threshold=5,
        clear_turns_after=False,
        max_tokens=engine_config.llm.max_tokens,
        temperature=engine_config.llm.temperature,
    )
