"""
main.py - FastAPI app entry point and route registration.

Does NOT: implement engine business logic.

Dependencies injected: Settings, ApiKeyMiddleware.
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from api.routes.action import router as action_router
from api.routes.batch import router as batch_router
from api.routes.clock import router as clock_router
from api.routes.dialogue import router as dialogue_router
from api.routes.dialogue_ws import router as dialogue_ws_router
from api.routes.npc_state import router as npc_state_router
from api.routes.system import router as system_router
from auth.middleware import ApiKeyMiddleware
from api.dependencies import get_graph_db
from config import get_settings
from scheduler.tick_lease import TickLeaseRepository
from utils.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    graph_db = get_graph_db()
    settings = get_settings()
    await graph_db.connect()
    if settings.DISTRIBUTED_TICK_LEASE_ENABLED:
        async with graph_db.get_session() as session:
            lease_repo = TickLeaseRepository(
                scheduler_id=settings.TICK_SCHEDULER_ID,
                owner_id=settings.TICK_LEASE_OWNER_ID,
                lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
            )
            await lease_repo.ensure_constraints(session=session)
    try:
        yield
    finally:
        await graph_db.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)

    app = FastAPI(title="NPC Engine", version="0.1.0", lifespan=lifespan)
    app.add_middleware(ApiKeyMiddleware, settings=settings)
    app.include_router(system_router)
    app.include_router(dialogue_router)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router)
    app.include_router(npc_state_router)
    app.include_router(action_router)
    app.include_router(clock_router)
    app.include_router(batch_router)

    return app


app = create_app()
