"""
dependencies.py - FastAPI dependency composition root for session-scoped and composed services.

Does NOT: define singleton application-level providers.

Dependencies injected: Settings.
"""

from typing import AsyncGenerator

from fastapi import Depends
from neo4j import AsyncSession

from npc_engine.api.dependency_singletons import (
    get_context_cache,
    get_dialogue_engine_model_config,
    get_embedding_index,
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
from npc_engine.config import Settings, get_settings
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.graph.generic_graph_service import GenericGraphService
from npc_engine.graph.graph_admin_service import GraphAdminService
from npc_engine.schema.llm_config_models import LLMConfig
from npc_engine.type_registry.contracts import TypeRegistry


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped Neo4j session for the lifetime of one HTTP request.

    Returns:
        AsyncGenerator yielding an AsyncSession and closing it on exit.
    """
    graph_db = get_graph_db()
    await graph_db.connect()
    async with graph_db.get_session() as session:
        yield session


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
    session: AsyncSession,
    settings: Settings,
    llm_client,
    llm_config: LLMConfig,
    engine_model_config: EngineModelConfig,
) -> DialogueHandler:
    """Construct DialogueHandler with shared dependency wiring.

    Args:
        session: Active Neo4j session for graph access.
        settings: Application settings.
        llm_client: Instantiated LLM client.
        llm_config: Context pipeline config (tier budgets and relevance weights).
        engine_model_config: Per-engine config (model params, timeouts, fallback policy).

    Returns:
        Fully wired DialogueHandler instance.
    """
    return DialogueHandler(
        session=session,
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
        engine_model_config=engine_model_config,
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
    engine_model_config: EngineModelConfig = Depends(get_dialogue_engine_model_config),
) -> DialogueHandler:
    """Build a per-request DialogueHandler via FastAPI dependency injection.

    Args:
        session: Scoped Neo4j session.
        settings: Application settings.
        llm_client: LLM client resolved per request.
        llm_config: Context pipeline config.
        engine_model_config: Dialogue engine per-engine LLM config.

    Returns:
        Fully wired DialogueHandler.
    """
    return build_dialogue_handler(
        session=session,
        settings=settings,
        llm_client=llm_client,
        llm_config=llm_config,
        engine_model_config=engine_model_config,
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
