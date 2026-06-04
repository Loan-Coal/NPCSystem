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

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from npc_engine.api.error_envelope import ErrorBody, ErrorDetail, ErrorEnvelope
from npc_engine.api.rate_limit import RateLimitMiddleware
from npc_engine.api.routes.action import router as action_router
from npc_engine.api.routes.batch import router as batch_router
from npc_engine.api.routes.clock import router as clock_router
from npc_engine.api.routes.dialogue import router as dialogue_router
from npc_engine.api.routes.dialogue_ws import router as dialogue_ws_router
from npc_engine.api.routes.graph import router as graph_router
from npc_engine.api.routes.beliefs import router as beliefs_router
from npc_engine.api.routes.goals import router as goals_router
from npc_engine.api.routes.items import router as items_router
from npc_engine.api.routes.memories import router as memories_router
from npc_engine.api.routes.secrets import router as secrets_router
from npc_engine.api.routes.debts import router as debts_router
from npc_engine.api.routes.factions import router as factions_router
from npc_engine.api.routes.schedules import router as schedules_router
from npc_engine.api.routes.reputation import admin_router as reputation_admin_router
from npc_engine.api.routes.reputation import graph_router as reputation_graph_router
from npc_engine.api.routes.graph_admin import router as graph_admin_router
from npc_engine.api.routes.npc_state import router as npc_state_router
from npc_engine.api.routes.quest import router as quest_router
from npc_engine.api.routes.quest_generation import router as quest_generation_router
from npc_engine.api.routes.economy import router as economy_router
from npc_engine.api.routes.location_history import router as location_history_router
from npc_engine.api.routes.causality import router as causality_router
from npc_engine.api.routes.witnessed import router as witnessed_router
from npc_engine.api.routes.groups import router as groups_router
from npc_engine.api.routes.rumors import router as rumors_router
from npc_engine.api.routes.skills import router as skills_router
from npc_engine.api.routes.traits import router as traits_router
from npc_engine.api.routes.pledges import router as pledges_router
from npc_engine.api.routes.treaties import router as treaties_router
from npc_engine.api.routes.system import admin_router as system_admin_router
from npc_engine.api.routes.system import router as system_router
from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.api.dependency_singletons import (
    close_registered_llm_adapters,
    get_dialogue_engine_model_config,
    get_embedding_index,
    get_faction_politics_engine,
    get_game_schema,
    get_graph_db,
    get_idempotency_service,
    get_llm_config,
    get_clique_formation_engine,
    get_memory_consolidation_engine,
    get_oath_engine,
    get_treaty_engine,
    get_pricing_engine,
    get_skill_progression_engine,
    get_quest_generation_engine,
    get_redis_runtime,
    get_routine_engine,
    get_story_pacing_engine,
    get_trade_engine,
    get_type_registry,
)
from npc_engine.config import get_settings
from npc_engine.engines.contracts.contract_loader import load_engine_contracts
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_config_loader import validate_all_engine_llm_configs
from npc_engine.engines.idempotency.cleanup_scheduler import IdempotencyCleanupScheduler
from npc_engine.retrieval.embedding_reconciler import EmbeddingReconciler
from npc_engine.scheduler.tick_lease import TickLeaseRepository
from npc_engine.utils.logging import configure_logging, get_logger

_logger = logging.getLogger(__name__)
_handler_logger = get_logger(__name__)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI RequestValidationError to a canonical ErrorEnvelope (422).

    Args:
        request: Incoming FastAPI request.
        exc: The validation exception raised by FastAPI.

    Returns:
        JSONResponse with ErrorEnvelope shape and HTTP 422 status.
    """
    details = [
        ErrorDetail(field=".".join(str(s) for s in e["loc"]), reason=e["msg"])
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="validation_error",
                message="request validation failed",
                details=details,
            )
        ).model_dump(),
    )


async def _http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Convert FastAPI HTTPException to a canonical ErrorEnvelope.

    Args:
        request: Incoming FastAPI request.
        exc: The HTTP exception raised by route handlers or middleware.

    Returns:
        JSONResponse with ErrorEnvelope shape and the exception's status code.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorEnvelope(
            error=ErrorBody(
                code=f"http_{exc.status_code}",
                message=str(exc.detail) if exc.detail else "error",
            )
        ).model_dump(),
    )


async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert unhandled exceptions to a canonical ErrorEnvelope (500).

    Never leaks stack traces or internal details to the caller.

    Args:
        request: Incoming FastAPI request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with ErrorEnvelope shape and HTTP 500 status.
    """
    _handler_logger.error("unhandled_exception", extra={"exc": str(exc)})
    return JSONResponse(
        status_code=500,
        content=ErrorEnvelope(
            error=ErrorBody(code="internal_error", message="internal error")
        ).model_dump(),
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    graph_db = get_graph_db()
    redis_runtime = get_redis_runtime()
    settings = get_settings()
    reconciler_task: asyncio.Task[None] | None = None
    idempotency_cleanup_task: asyncio.Task[None] | None = None
    connected = False
    try:
        get_faction_politics_engine.cache_clear()
        get_clique_formation_engine.cache_clear()
        get_skill_progression_engine.cache_clear()
        get_oath_engine.cache_clear()
        get_treaty_engine.cache_clear()
        get_story_pacing_engine.cache_clear()
        get_pricing_engine.cache_clear()
        get_trade_engine.cache_clear()
        get_quest_generation_engine.cache_clear()
        get_routine_engine.cache_clear()
        get_game_schema.cache_clear()
        get_game_schema()
        get_memory_consolidation_engine.cache_clear()
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
        get_faction_politics_engine()
        get_story_pacing_engine()
        get_quest_generation_engine()
        await graph_db.connect()
        connected = True
        await redis_runtime.connect()
        _dialogue_probe_adapter = create_llm_client_for_engine(
            engine_config=dialogue_engine_config, settings=settings
        )
        if not await _dialogue_probe_adapter.health_check():
            _logger.warning("LLM backend health check failed — starting degraded")
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
        await close_registered_llm_adapters()
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

    # Exception handlers — registered before middleware so they apply to all errors.
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)

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
    app.include_router(beliefs_router, prefix=admin_prefix)
    app.include_router(goals_router, prefix=admin_prefix)
    app.include_router(items_router, prefix=admin_prefix)
    app.include_router(memories_router, prefix=admin_prefix)
    app.include_router(secrets_router, prefix=admin_prefix)
    app.include_router(debts_router, prefix=admin_prefix)
    app.include_router(factions_router, prefix=admin_prefix)
    app.include_router(schedules_router, prefix=admin_prefix)
    app.include_router(reputation_admin_router, prefix=admin_prefix)
    app.include_router(quest_generation_router, prefix=admin_prefix)
    app.include_router(economy_router, prefix=admin_prefix)
    app.include_router(location_history_router, prefix=admin_prefix)
    app.include_router(causality_router, prefix=admin_prefix)
    app.include_router(witnessed_router, prefix=admin_prefix)
    app.include_router(groups_router, prefix=admin_prefix)
    app.include_router(rumors_router, prefix=admin_prefix)
    app.include_router(skills_router, prefix=admin_prefix)
    app.include_router(traits_router, prefix=admin_prefix)
    app.include_router(pledges_router, prefix=admin_prefix)
    app.include_router(treaties_router, prefix=admin_prefix)

    return app


app = create_app()
