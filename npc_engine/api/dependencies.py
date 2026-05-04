"""
dependencies.py - FastAPI dependency composition root for session-scoped and composed services.

Does NOT: define singleton application-level providers.

Dependencies injected: Settings.
"""

from typing import AsyncGenerator

from fastapi import Depends
from neo4j import AsyncSession

from api.dependency_singletons import (
    get_context_cache,
    get_embedding_index,
    get_emotion_store,
    get_emotion_updater,
    get_event_handler,
    get_game_clock,
    get_game_schema,
    get_gossip_handler,
    get_graph_db,
    get_idempotency_service,
    get_idempotency_store,
    get_llm_config,
    get_quest_lifecycle_engine,
    get_redis_runtime,
    get_reindex_job_service,
    get_session_store,
    get_tick_scheduler,
    get_type_registry,
)
from config import Settings, get_settings
from engines.dialogue.dialogue_handler import DialogueHandler
from engines.llm.factory import create_llm_client
from graph.generic_graph_service import GenericGraphService
from graph.graph_admin_service import GraphAdminService
from schema.llm_config_models import LLMConfig
from type_registry.contracts import TypeRegistry


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped Neo4j session for the lifetime of one HTTP request.

    Returns:
        AsyncGenerator yielding an AsyncSession and closing it on exit.
    """
    graph_db = get_graph_db()
    await graph_db.connect()
    async with graph_db.get_session() as session:
        yield session


def get_llm_client(settings: Settings = Depends(get_settings)):
    """Create an LLM client bound to current request settings.

    Args:
        settings: Application settings resolved via dependency injection.

    Returns:
        LLM client instance for the current request.
    """
    return create_llm_client(settings=settings)


def build_dialogue_handler(
    *,
    session: AsyncSession,
    settings: Settings,
    llm_client,
    llm_config: LLMConfig,
) -> DialogueHandler:
    """Construct DialogueHandler with shared dependency wiring.

    Args:
        session: Active Neo4j session for graph access.
        settings: Application settings.
        llm_client: Instantiated LLM client.
        llm_config: Typed LLM configuration.

    Returns:
        Fully wired DialogueHandler instance.
    """
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
    """Build a per-request DialogueHandler via FastAPI dependency injection.

    Args:
        session: Scoped Neo4j session.
        settings: Application settings.
        llm_client: LLM client resolved per request.
        llm_config: Typed LLM configuration.

    Returns:
        Fully wired DialogueHandler.
    """
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
    """Build generic graph service bound to current request session and registry.

    Args:
        session: Scoped Neo4j session.
        registry: Immutable type registry singleton.

    Returns:
        GenericGraphService for the current request.
    """
    return GenericGraphService(session=session, registry=registry)


def get_graph_admin_service(session: AsyncSession = Depends(get_db_session)) -> GraphAdminService:
    """Build admin graph service bound to current request session.

    Args:
        session: Scoped Neo4j session.

    Returns:
        GraphAdminService for the current request.
    """
    return GraphAdminService(session=session)
