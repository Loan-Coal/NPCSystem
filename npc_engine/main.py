"""
main.py - FastAPI app entry point and route registration.

Does NOT: implement engine business logic.

Dependencies injected: Settings, ApiKeyMiddleware.
"""

import asyncio
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
from api.routes.system import router as system_router
from auth.middleware import ApiKeyMiddleware
from api.dependencies import get_embedding_index, get_game_schema, get_graph_db
from config import get_settings
from retrieval.embedding_reconciler import EmbeddingReconciler
from scheduler.tick_lease import TickLeaseRepository
from utils.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    graph_db = get_graph_db()
    settings = get_settings()
    reconciler_task: asyncio.Task[None] | None = None
    connected = False
    try:
        get_game_schema.cache_clear()
        get_game_schema()
        await graph_db.connect()
        connected = True
        if settings.DISTRIBUTED_TICK_LEASE_ENABLED:
            async with graph_db.get_session() as session:
                lease_repo = TickLeaseRepository(
                    scheduler_id=settings.TICK_SCHEDULER_ID,
                    owner_id=settings.TICK_LEASE_OWNER_ID,
                    lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
                )
                await lease_repo.ensure_constraints(session=session)
        embedding_reconciler = EmbeddingReconciler(
            graph_db=graph_db,
            embedding_index=get_embedding_index(),
            interval_seconds=settings.EMBEDDING_RECONCILE_INTERVAL_SECONDS,
        )
        reconciler_task = asyncio.create_task(embedding_reconciler.run_forever(), name="embedding-reconciler")
        yield
    finally:
        if reconciler_task is not None:
            reconciler_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconciler_task
        if connected:
            await graph_db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)

    app = FastAPI(title="NPC Engine", version="0.1.0", lifespan=lifespan)
    app.add_middleware(ApiKeyMiddleware, settings=settings)
    app.include_router(system_router)
    app.include_router(dialogue_router, prefix=settings.API_V1_PREFIX)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router, prefix=settings.API_V1_PREFIX)
    app.include_router(npc_state_router, prefix=settings.API_V1_PREFIX)
    app.include_router(action_router, prefix=settings.API_V1_PREFIX)
    app.include_router(clock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(batch_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_admin_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
