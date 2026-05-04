"""
main.py - FastAPI app entry point and route registration.

Does NOT: implement engine business logic.

Dependencies injected: Settings, ApiKeyMiddleware.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from api.routes.action import router as action_router
from api.routes.batch import router as batch_router
from api.routes.clock import router as clock_router
from api.routes.dialogue import router as dialogue_router
from api.routes.dialogue_ws import router as dialogue_ws_router
from api.routes.graph import router as graph_router
from api.routes.graph_admin import router as graph_admin_router
from api.routes.npc_state import router as npc_state_router
from api.routes.quest import router as quest_router
from api.routes.system import router as system_router
from auth.middleware import ApiKeyMiddleware
from api.dependency_singletons import (
    get_embedding_index,
    get_game_schema,
    get_graph_db,
    get_idempotency_service,
    get_llm_config,
    get_redis_runtime,
    get_type_registry,
)
from config import get_settings
from engines.idempotency.cleanup_scheduler import IdempotencyCleanupScheduler
from retrieval.embedding_reconciler import EmbeddingReconciler
from scheduler.tick_lease import TickLeaseRepository
from utils.logging import configure_logging

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    graph_db = get_graph_db()
    redis_runtime = get_redis_runtime()
    settings = get_settings()
    reconciler_task: asyncio.Task[None] | None = None
    idempotency_cleanup_task: asyncio.Task[None] | None = None
    connected = False
    try:
        get_game_schema.cache_clear()
        get_game_schema()
        get_type_registry.cache_clear()
        type_registry = get_type_registry()
        if type_registry.custom_node_types:
            _logger.warning(
                "WARN: custom_node_types declared (%s) but not consumed by current engines.",
                list(type_registry.custom_node_types.keys()),
            )
        if type_registry.custom_edge_types:
            _logger.warning(
                "WARN: custom_edge_types declared (%s) but not consumed by current engines.",
                list(type_registry.custom_edge_types.keys()),
            )
        get_llm_config.cache_clear()
        llm_config = get_llm_config()
        _logger.info("Active relevance weights: %s", llm_config.relevance_weights)
        await graph_db.connect()
        connected = True
        await redis_runtime.connect()
        if settings.DISTRIBUTED_TICK_LEASE_ENABLED:
            async with graph_db.get_session() as session:
                lease_repo = TickLeaseRepository(
                    scheduler_id=settings.TICK_SCHEDULER_ID,
                    owner_id=settings.TICK_LEASE_OWNER_ID,
                    lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
                )
                await lease_repo.ensure_constraints(session=session)
        idempotency_service = get_idempotency_service()
        await idempotency_service.ensure_constraints()
        embedding_reconciler = EmbeddingReconciler(
            graph_db=graph_db,
            embedding_index=get_embedding_index(),
            interval_seconds=settings.EMBEDDING_RECONCILE_INTERVAL_SECONDS,
        )
        reconciler_task = asyncio.create_task(embedding_reconciler.run_forever(), name="embedding-reconciler")
        cleanup_scheduler = IdempotencyCleanupScheduler(
            service=idempotency_service,
            interval_seconds=settings.IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS,
        )
        idempotency_cleanup_task = asyncio.create_task(
            cleanup_scheduler.run_forever(),
            name="idempotency-cleanup",
        )
        yield
    finally:
        if idempotency_cleanup_task is not None:
            idempotency_cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await idempotency_cleanup_task
        if reconciler_task is not None:
            reconciler_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconciler_task
        await redis_runtime.close()
        if connected:
            await graph_db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)

    app = FastAPI(title="NPC Engine", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        ApiKeyMiddleware,
        settings=settings,
        idempotency_service=get_idempotency_service(),
    )
    app.include_router(system_router)
    app.include_router(dialogue_router, prefix=settings.API_V1_PREFIX)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router, prefix=settings.API_V1_PREFIX)
    app.include_router(npc_state_router, prefix=settings.API_V1_PREFIX)
    app.include_router(action_router, prefix=settings.API_V1_PREFIX)
    app.include_router(quest_router, prefix=settings.API_V1_PREFIX)
    app.include_router(clock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(batch_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_admin_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
