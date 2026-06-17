"""
dependencies.py - FastAPI dependency composition root for session-scoped and composed services.
Layer: api
Purpose: Per-request dependency wiring and singleton trade-handler wiring for dispatch.

Does NOT: define the main lifespan. Singleton lifecycle is managed in main.py.

Dependencies injected: Settings, NegotiationStore, PricingEngine, NegotiationBackedSyncTradeHandler.
"""
from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from neo4j import AsyncSession

from npc_engine.api.dependencies_engines import get_pricing_engine
from npc_engine.engines.interaction.dispatch import set_trade_handler
from npc_engine.api.dependency_singletons import (
    get_context_cache,
    get_dialogue_engine_model_config,
    get_dialogue_graph_ports,
    get_embedding_index,  # noqa: F401  re-exported for api.routes.graph_admin + debug_retrieval
    get_emotion_store,  # noqa: F401  re-exported for api.routes.npc_state
    get_emotion_updater,
    get_event_handler,  # noqa: F401  re-exported for api.routes.batch
    get_game_schema,  # noqa: F401  re-exported for api.routes.system
    get_gossip_handler,  # noqa: F401  re-exported for api.routes.batch
    get_graph_db,
    get_llm_config,
    get_quest_lifecycle_engine,  # noqa: F401  re-exported for api.routes.quest
    get_reindex_job_service,  # noqa: F401  re-exported for api.routes.graph_admin
    get_session_store,
    get_tick_scheduler,  # noqa: F401  re-exported for api.routes.clock
    get_type_registry,
)
from npc_engine.engines.interaction.negotiation_store import NegotiationStore
from npc_engine.engines.interaction.trade_handler_sync import NegotiationBackedSyncTradeHandler
from npc_engine.config import Settings, get_settings
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.services.content_rating_resolver import ContentRatingResolver
from npc_engine.services.input_moderation import InputModerationService, build_input_moderation_service
from npc_engine.services.output_moderation import OutputModerationService, build_output_moderation_service
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.engines.tts.mock_adapter import MockTTSAdapter
from npc_engine.engines.tts.piper_adapter import PiperAdapter
from npc_engine.engines.tts.protocols import TTSClientProtocol
from npc_engine.graph.faction_service import FactionService
from npc_engine.graph.reputation_service import ReputationService
from npc_engine.graph.schedule_service import ScheduleService
from npc_engine.graph.generic_graph_service import GenericGraphService
from npc_engine.graph.graph_admin_service import GraphAdminService
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.type_registry.contracts import TypeRegistry


@lru_cache
def get_negotiation_store() -> NegotiationStore:
    """Return the singleton NegotiationStore for the lifetime of the process.

    Returns:
        Shared NegotiationStore instance (one active session per player).
    """
    return NegotiationStore()


@lru_cache
def get_sync_trade_handler() -> NegotiationBackedSyncTradeHandler:
    """Return the singleton NegotiationBackedSyncTradeHandler and wire it into dispatch.

    Side-effect: calls set_trade_handler so dispatch_interaction immediately routes
    propose_trade through NegotiationBackedSyncTradeHandler without requiring a
    separate lifespan call. Idempotent — lru_cache ensures one construction.

    Returns:
        Handler wired with the shared NegotiationStore and PricingEngine.
    """
    handler = NegotiationBackedSyncTradeHandler(
        store=get_negotiation_store(),
        pricing_engine=get_pricing_engine(),
    )
    set_trade_handler(handler)
    return handler


@lru_cache
def get_input_moderation_service() -> InputModerationService:
    """Return the singleton InputModerationService for the process lifetime.

    Returns:
        InputModerationService wired to the global content rating ceiling.
    """
    return build_input_moderation_service(get_settings().CONTENT_RATING)


@lru_cache
def get_output_moderation_service() -> OutputModerationService:
    """Return the singleton OutputModerationService for the process lifetime.

    Returns:
        OutputModerationService wired to the global content rating ceiling.
    """
    return build_output_moderation_service(get_settings().CONTENT_RATING)


@lru_cache
def get_content_rating_resolver() -> ContentRatingResolver:
    """Return the singleton ContentRatingResolver for the process lifetime.

    Returns:
        ContentRatingResolver seeded from Settings.CONTENT_RATING.
    """
    return ContentRatingResolver(default_rating=get_settings().CONTENT_RATING)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped Neo4j session for the lifetime of one HTTP request.

    Returns:
        AsyncGenerator yielding an AsyncSession and closing it on exit.
    """
    graph_db = get_graph_db()
    await graph_db.connect()
    async with graph_db.get_session() as session:
        yield session


def get_tts_client(
    settings: Settings = Depends(get_settings),
) -> TTSClientProtocol | None:
    """Construct a TTS adapter when TTS_ENABLED is True, else return None.

    Args:
        settings: Application settings providing TTS_BACKEND, PIPER_BASE_URL, etc.

    Returns:
        Configured TTSClientProtocol adapter, or None if TTS_ENABLED is False.
    """
    if not settings.TTS_ENABLED:
        return None
    if settings.TTS_BACKEND == "piper":
        return PiperAdapter(
            base_url=settings.PIPER_BASE_URL,
            timeout_seconds=settings.TTS_TIMEOUT_SECONDS,
        )
    return MockTTSAdapter()


def get_llm_client(
    settings: Settings = Depends(get_settings),
    engine_model_config: EngineModelConfig = Depends(get_dialogue_engine_model_config),
):
    """Create an LLM client from the dialogue engine's per-engine config.

    Args:
        settings: Application settings providing backend URLs and timeout.
        engine_model_config: Dialogue engine LLM config declaring backend and model.

    Returns:
        LLM client instance for the dialogue engine.
    """
    return create_llm_client_for_engine(engine_config=engine_model_config, settings=settings)


def build_dialogue_handler(
    *,
    settings: Settings,
    llm_client,
    llm_config: LLMConfig,
    engine_model_config: EngineModelConfig,
    tts_client: TTSClientProtocol | None = None,
) -> DialogueHandler:
    """Construct DialogueHandler with shared dependency wiring.

    DialogueHandler is session-free (SEV-24 dialogue migration) — graph and retrieval
    I/O are delegated to the injected ports from get_dialogue_graph_ports().

    Args:
        settings: Application settings.
        llm_client: Instantiated LLM client.
        llm_config: Context pipeline config (tier budgets and relevance weights).
        engine_model_config: Per-engine config (model params, timeouts, fallback policy).
        tts_client: Optional TTS adapter; passed through when TTS_ENABLED is True.

    Returns:
        Fully wired DialogueHandler instance.
    """
    return DialogueHandler(
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
        engine_model_config=engine_model_config,
        session_store=get_session_store(),
        emotion_updater=get_emotion_updater(),
        input_moderation=get_input_moderation_service(),
        output_moderation=get_output_moderation_service(),
        effective_rating=get_settings().CONTENT_RATING,
        context_cache=get_context_cache(),
        tts_client=tts_client,
        negotiation_store=get_negotiation_store(),
        **get_dialogue_graph_ports(),
    )


def get_dialogue_handler(
    settings: Settings = Depends(get_settings),
    llm_client=Depends(get_llm_client),
    llm_config: LLMConfig = Depends(get_llm_config),
    engine_model_config: EngineModelConfig = Depends(get_dialogue_engine_model_config),
    tts_client: TTSClientProtocol | None = Depends(get_tts_client),
) -> DialogueHandler:
    """Build a per-request DialogueHandler via FastAPI dependency injection.

    Session-free (SEV-24): no longer takes Depends(get_db_session).

    Args:
        settings: Application settings.
        llm_client: LLM client resolved per request.
        llm_config: Context pipeline config.
        engine_model_config: Dialogue engine per-engine LLM config.
        tts_client: Optional TTS adapter resolved from settings.

    Returns:
        Fully wired DialogueHandler.
    """
    return build_dialogue_handler(
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
        engine_model_config=engine_model_config,
        tts_client=tts_client,
    )


def get_generic_graph_service(
    session: AsyncSession = Depends(get_db_session),
    registry: TypeRegistry = Depends(get_type_registry),
) -> GenericGraphService:
    """Build generic graph service bound to current request session and registry.

    Args:
        session: Scoped Neo4j session.
        registry: Immutable type registry singleton.

    Returns:
        GenericGraphService for the current request.
    """
    return GenericGraphService(session=session, registry=registry)


def get_faction_service(session: AsyncSession = Depends(get_db_session)) -> FactionService:
    """Build faction service bound to current request session.

    Args:
        session: Scoped Neo4j session.

    Returns:
        FactionService for the current request.
    """
    return FactionService(session=session)


def get_schedule_service(session: AsyncSession = Depends(get_db_session)) -> ScheduleService:
    """Build schedule service bound to current request session.

    Args:
        session: Scoped Neo4j session.

    Returns:
        ScheduleService for the current request.
    """
    return ScheduleService(session=session)


def get_reputation_service(session: AsyncSession = Depends(get_db_session)) -> ReputationService:
    """Build reputation service bound to current request session.

    Args:
        session: Scoped Neo4j session.

    Returns:
        ReputationService for the current request.
    """
    return ReputationService(session=session)


def get_graph_admin_service(session: AsyncSession = Depends(get_db_session)) -> GraphAdminService:
    """Build admin graph service bound to current request session.

    Args:
        session: Scoped Neo4j session.

    Returns:
        GraphAdminService for the current request.
    """
    return GraphAdminService(session=session)
