"""
Module: main
Layer: api
Purpose: FastAPI application entry point — lifespan management and route registration.
Does NOT: implement business logic, call LLMs, or write to the graph directly.
Dependencies injected: all api routes, auth.middleware, api.rate_limit, config, engines,
                       retrieval, scheduler, utils
Used by: uvicorn at process start.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI

from npc_engine.api.rate_limit import RateLimitMiddleware
from npc_engine.api.routes.action import router as action_router
from npc_engine.api.routes.batch import router as batch_router
from npc_engine.api.routes.clock import router as clock_router
from npc_engine.api.routes.dialogue import router as dialogue_router
from npc_engine.api.routes.dialogue_ws import router as dialogue_ws_router
from npc_engine.api.routes.graph import router as graph_router
from npc_engine.api.routes.factions import router as factions_router
from npc_engine.api.routes.schedules import router as schedules_router
from npc_engine.api.routes.reputation import admin_router as reputation_admin_router
from npc_engine.api.routes.reputation import graph_router as reputation_graph_router
from npc_engine.api.routes.graph_admin import router as graph_admin_router
from npc_engine.api.routes.npc_state import router as npc_state_router
from npc_engine.api.routes.quest import router as quest_router
from npc_engine.api.routes.system import admin_router as system_admin_router
from npc_engine.api.routes.system import router as system_router
from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.api.dependency_singletons import (
    get_dialogue_engine_model_config,
    get_embedding_index,
    get_game_schema,
    get_graph_db,
    get_idempotency_service,
    get_llm_config,
    get_redis_runtime,
    get_type_registry,
)
from npc_engine.config import get_settings
from npc_engine.engines.contracts.contract_loader import load_engine_contracts
from npc_engine.engines.llm_config_loader import validate_all_engine_llm_configs
from npc_engine.engines.idempotency.cleanup_scheduler import IdempotencyCleanupScheduler
from npc_engine.retrieval.embedding_reconciler import EmbeddingReconciler
from npc_engine.scheduler.tick_lease import TickLeaseRepository
from npc_engine.utils.logging import configure_logging

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
        _contracts_dir = Path(__file__).resolve().parent / "engines" / "contracts"
        contracts = load_engine_contracts(contracts_dir=_contracts_dir)
        validate_all_engine_llm_configs(contracts=contracts)
        get_dialogue_engine_model_config.cache_clear()
        dialogue_engine_config = get_dialogue_engine_model_config()
        _logger.info(
            "Dialogue engine config: backend=%s model=%s",
            dialogue_engine_config.llm.backend,
            dialogue_engine_config.llm.model,
        )
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
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app with middleware and all routers registered.
    """
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL)

    app = FastAPI(title="NPC Engine", version="0.1.0", lifespan=lifespan)

    # Middleware is applied in reverse registration order (last added = outermost).
    # RateLimitMiddleware is added first so it runs AFTER auth (inner layer).
    # ApiKeyMiddleware is added second so it runs FIRST (outer layer), rejecting
    # unauthenticated requests before they consume a rate-limit token.
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(
        ApiKeyMiddleware,
        settings=settings,
        idempotency_service=get_idempotency_service(),
    )

    admin_prefix = f"{settings.API_V1_PREFIX}/admin"

    # Public system routes (no auth)
    app.include_router(system_router)

    # Game-engine public surface under /v1/
    app.include_router(dialogue_router, prefix=settings.API_V1_PREFIX)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router, prefix=settings.API_V1_PREFIX)
    app.include_router(npc_state_router, prefix=settings.API_V1_PREFIX)
    app.include_router(action_router, prefix=settings.API_V1_PREFIX)
    app.include_router(quest_router, prefix=settings.API_V1_PREFIX)
    app.include_router(clock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(reputation_graph_router, prefix=settings.API_V1_PREFIX)

    # Admin / designer-tooling surface under /v1/admin/
    app.include_router(system_admin_router, prefix=admin_prefix)
    app.include_router(batch_router, prefix=admin_prefix)
    app.include_router(graph_admin_router, prefix=admin_prefix)
    app.include_router(factions_router, prefix=admin_prefix)
    app.include_router(schedules_router, prefix=admin_prefix)
    app.include_router(reputation_admin_router, prefix=admin_prefix)

    return app


app = create_app()
