"""
dependencies.py - FastAPI dependency composition root for runtime services.

Does NOT: execute route business logic.

Dependencies injected: Settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends
from neo4j import AsyncSession

from cache.redis_runtime import RedisRuntime
from config import Settings, get_settings
from engines.dialogue.dialogue_handler import DialogueHandler
from engines.dialogue.session_store import SessionStore
from engines.emotion.emotion_store import EmotionStore
from engines.emotion.emotion_updater import EmotionUpdater
from engines.events.event_handler import EventHandler
from engines.gossip.gossip_handler import GossipHandler
from engines.idempotency.neo4j_store import Neo4jIdempotencyStore
from engines.idempotency.service import IdempotencyService
from engines.llm.factory import create_llm_client
from engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from graph.db import GraphDB
from graph.generic_graph_service import GenericGraphService
from graph.graph_admin_service import GraphAdminService
from graph.reindex_job_service import ReindexJobService
from retrieval.dialogue_context_cache import DialogueContextCache
from retrieval.embedding_index import EmbeddingIndex
from retrieval.vector_store_factory import create_vector_store
from scheduler.game_clock import GameClock
from scheduler.tick_scheduler import TickScheduler
from schema.schema_loader import load_game_schema
from schema.schema_models import SchemaConfig
from schema.llm_config_loader import load_llm_config
from schema.llm_config_models import LLMConfig
from type_registry.registry import build_type_registry
from type_registry.contracts import TypeRegistry


REGISTRY_SOURCES_SEPARATOR = ","


@lru_cache
def get_graph_db() -> GraphDB:
    settings = get_settings()
    return GraphDB(settings=settings)


@lru_cache
def get_session_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(ttl_seconds=settings.DIALOGUE_SESSION_TTL, max_turns=settings.DIALOGUE_SESSION_TURNS)


@lru_cache
def get_emotion_store() -> EmotionStore:
    return EmotionStore()


@lru_cache
def get_emotion_updater() -> EmotionUpdater:
    return EmotionUpdater(emotion_store=get_emotion_store())


@lru_cache
def get_embedding_index() -> EmbeddingIndex:
    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    return EmbeddingIndex(vector_store=vector_store)


@lru_cache
def get_gossip_handler() -> GossipHandler:
    settings = get_settings()
    return GossipHandler(settings=settings, embedding_index=get_embedding_index())


@lru_cache
def get_event_handler() -> EventHandler:
    settings = get_settings()
    return EventHandler(settings=settings, embedding_index=get_embedding_index(), registry=get_type_registry())


@lru_cache
def get_quest_lifecycle_engine() -> QuestLifecycleEngine:
    settings = get_settings()
    return QuestLifecycleEngine(settings=settings, registry=get_type_registry())


@lru_cache
def get_game_clock() -> GameClock:
    settings = get_settings()
    return GameClock(mode=settings.CLOCK_MODE)


@lru_cache
def get_tick_scheduler() -> TickScheduler:
    settings = get_settings()
    return TickScheduler(
        clock=get_game_clock(),
        gossip_handler=get_gossip_handler(),
        event_handler=get_event_handler(),
        gossip_interval=settings.GOSSIP_TICK_INTERVAL,
        event_interval=settings.EVENT_TICK_INTERVAL,
        distributed_lease_enabled=settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        scheduler_id=settings.TICK_SCHEDULER_ID,
        lease_owner_id=settings.TICK_LEASE_OWNER_ID,
        lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
    )


@lru_cache
def get_redis_runtime() -> RedisRuntime:
    """Create optional Redis runtime manager for non-idempotency caches."""

    return RedisRuntime(settings=get_settings())


@lru_cache
def get_game_schema() -> SchemaConfig:
    settings = get_settings()
    return load_game_schema(schema_path=settings.GAME_SCHEMA_PATH)


@lru_cache
def get_type_registry() -> TypeRegistry:
    """Build immutable type registry singleton from base schema and extension sources."""

    settings = get_settings()
    return build_type_registry(
        base_schema=get_game_schema(),
        extension_sources=_resolve_registry_extension_sources(settings=settings),
    )


@lru_cache
def get_llm_config() -> LLMConfig:
    """Load typed llm configuration for v1.4 prompt policy settings."""

    settings = get_settings()
    return load_llm_config(config_path=settings.LLM_CONFIG_PATH)


@lru_cache
def get_idempotency_store() -> Neo4jIdempotencyStore:
    """Create idempotency persistence backend."""

    return Neo4jIdempotencyStore()


def _resolve_registry_extension_sources(*, settings: Settings) -> tuple[str, ...]:
    """Resolve comma-delimited registry extension source values relative to project root."""

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
def get_idempotency_service() -> IdempotencyService:
    """Create idempotency service for middleware preflight and finalization."""

    return IdempotencyService(
        settings=get_settings(),
        graph_db=get_graph_db(),
        store=get_idempotency_store(),
    )


@lru_cache
def get_reindex_job_service() -> ReindexJobService:
    """Create singleton reindex job lifecycle manager."""

    return ReindexJobService()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    graph_db = get_graph_db()
    await graph_db.connect()
    async with graph_db.get_session() as session:
        yield session


def get_llm_client(settings: Settings = Depends(get_settings)):
    return create_llm_client(settings=settings)


@lru_cache
def get_context_cache() -> DialogueContextCache:
    settings = get_settings()
    return DialogueContextCache(ttl_seconds=settings.DIALOGUE_SESSION_TTL)


def build_dialogue_handler(
    *,
    session: AsyncSession,
    settings: Settings,
    llm_client,
    llm_config: LLMConfig,
) -> DialogueHandler:
    """Construct DialogueHandler with shared dependency wiring."""

    return DialogueHandler(
        session=session,
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
        session_store=get_session_store(),
        emotion_updater=get_emotion_updater(),
        embedding_index=get_embedding_index(),
        context_cache=get_context_cache(),
    )


def get_dialogue_handler(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    llm_client=Depends(get_llm_client),
    llm_config: LLMConfig = Depends(get_llm_config),
) -> DialogueHandler:
    return build_dialogue_handler(
        session=session,
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
    )


def get_generic_graph_service(
    session: AsyncSession = Depends(get_db_session),
    registry: TypeRegistry = Depends(get_type_registry),
) -> GenericGraphService:
    """Build generic graph service bound to current request session and registry."""

    return GenericGraphService(session=session, registry=registry)


def get_graph_admin_service(session: AsyncSession = Depends(get_db_session)) -> GraphAdminService:
    """Build admin graph service bound to current request session."""

    return GraphAdminService(session=session)
