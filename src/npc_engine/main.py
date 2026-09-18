"""
Module: main
Layer: api
Purpose: FastAPI application entry point — lifespan management and app assembly.
Does NOT: implement business logic, call LLMs, or write to the graph directly.
Dependencies injected: api.router_registry, api.exception_handlers, auth.middleware,
                       api.rate_limit, config, engines, retrieval, scheduler, utils
Used by: uvicorn at process start.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI

from npc_engine.api.errors import register_exception_handlers
from npc_engine.api.rate_limit import RateLimitMiddleware
from npc_engine.api.router_registry import register_routers
from npc_engine.auth.middleware import ApiKeyMiddleware
from npc_engine.api.dependency_singletons import (
    close_registered_llm_adapters,
    get_dialogue_engine_model_config,
    get_embedding_index,
    get_emotion_store,
    get_game_clock,
    get_game_schema,
    get_graph_db,
    get_idempotency_service,
    get_llm_config,
    get_memory_consolidation_engine,
    get_pricing_engine,
    get_session_store,
    get_quest_generation_engine,
    get_redis_runtime,
    get_routine_engine,
    get_story_pacing_engine,
    get_tick_budget_guard,
    get_tick_scheduler,
    get_type_registry,
)
from npc_engine.engines.emotion.emotion_bootstrap import EmotionBootstrapper
from npc_engine.graph.character.character_reader import get_npc_ids
from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.graph.repositories.emotion_bootstrap_repository import Neo4jEmotionBootstrapRepository
from npc_engine.api.dependencies import get_sync_trade_handler
from npc_engine.engines.interaction.dispatch import set_trade_handler
from npc_engine.config import get_settings
from npc_engine.setup.llm_warmup import warm_up_llm
from npc_engine.retrieval.embedding.sentence_encoder import warm_up_encoder
from npc_engine.engines.contracts.contract_loader import load_engine_contracts
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_runtime_config import validate_all_engine_llm_configs
from npc_engine.engines.idempotency.cleanup_scheduler import IdempotencyCleanupScheduler
from npc_engine.retrieval.embedding import EmbeddingReconciler
from npc_engine.graph.infra.schema_bootstrap import ensure_core_constraints
from npc_engine.scheduler.tick_autopilot import TickAutopilot
from npc_engine.scheduler.tick_lease import TickLeaseRepository
from npc_engine.utils.logging import configure_logging

_logger = logging.getLogger(__name__)



async def _hydrate_vector_store(*, reconciler: EmbeddingReconciler) -> None:
    """Populate the vector store synchronously before the app starts serving.

    A latency optimisation, not a correctness requirement: POST
    /v1/admin/vector-store/rehydrate does the same work on demand, which is what makes
    VECTOR_STORE_HYDRATE_ON_STARTUP=false a legitimate posture instead of a silently
    broken one (DEC-208 Decision 3).

    Fails LOUD, at ERROR, when it reads nothing (DEC-208 Decision 4). For an instrument a
    silent item_count of 0 costs a night of generation and then reads afterwards as a
    null result rather than as a fault. It does NOT abort boot: the engine serves
    dialogue perfectly well with an empty tier B, and refusing to start would turn a
    degraded retrieval tier into a total outage.

    Args:
        reconciler: The reconciler whose ensure_corpus sweep populates the store.
    """
    report = await reconciler.ensure_corpus_once()
    if report.nodes_read == 0:
        _logger.error(
            "vector_store.boot_hydration_read_nothing missing_embedding=%s passes=%s "
            "— tier B will carry zero items this run",
            report.missing_embedding,
            report.reconcile_passes,
        )
        return
    _logger.info(
        "vector_store.boot_hydrated nodes_read=%s item_count=%s model=%s dim=%s corpus_sha=%s",
        report.nodes_read,
        report.fingerprint.item_count,
        report.fingerprint.embedding_model,
        report.fingerprint.embedding_dim,
        report.fingerprint.corpus_sha,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    graph_db = get_graph_db()
    redis_runtime = get_redis_runtime()
    settings = get_settings()
    reconciler_task: asyncio.Task[None] | None = None
    idempotency_cleanup_task: asyncio.Task[None] | None = None
    autopilot_task: asyncio.Task[None] | None = None
    connected = False
    try:
        # Clock before scheduler: get_tick_scheduler captures the clock singleton.
        get_game_clock.cache_clear()
        get_tick_scheduler.cache_clear()
        get_story_pacing_engine.cache_clear()
        get_pricing_engine.cache_clear()
        # get_trade_engine is per-request (not lru_cache) since SEV-24 — no cache to clear.
        set_trade_handler(get_sync_trade_handler())
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
        get_story_pacing_engine()
        get_quest_generation_engine()
        await graph_db.connect()
        connected = True
        async with graph_db.get_session() as session:
            await ensure_core_constraints(session=session)
        async with graph_db.get_session() as session:
            npc_ids = await get_npc_ids(session)
            await EmotionBootstrapper().load_from_graph(
                port=Neo4jEmotionBootstrapRepository(graph_db=graph_db),
                store=get_emotion_store(),
                npc_ids=npc_ids,
            )
            await get_session_store().load_from_graph(session=session)
            _logger.info("session_store.loaded_from_graph")
            persisted_world = await get_world_state(session=session, world_id=settings.WORLD_ID)
        # Hydrate the game clock before any engine or the autopilot can read it (ISSUE-165).
        clock_state = await get_game_clock().restore(
            tick_id=persisted_world.tick_id,
            game_time_seconds=persisted_world.game_time_seconds,
        )
        _logger.info("game_clock.hydrated tick_id=%s", clock_state.tick_id)
        await redis_runtime.connect()
        _dialogue_probe_adapter = create_llm_client_for_engine(
            engine_config=dialogue_engine_config, settings=settings
        )
        if not await _dialogue_probe_adapter.health_check():
            _logger.warning("LLM backend health check failed — starting degraded")
        await warm_up_llm(_dialogue_probe_adapter, enabled=settings.LLM_WARMUP_ON_STARTUP)
        await asyncio.to_thread(
            warm_up_encoder, settings.EMBEDDING_MODEL, enabled=settings.EMBEDDING_WARMUP_ON_STARTUP
        )
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
            batch_size=settings.VECTOR_STORE_CORPUS_BATCH_SIZE,
        )
        if settings.VECTOR_STORE_HYDRATE_ON_STARTUP:
            await _hydrate_vector_store(reconciler=embedding_reconciler)
        reconciler_task = asyncio.create_task(embedding_reconciler.run_forever(), name="embedding-reconciler")
        cleanup_scheduler = IdempotencyCleanupScheduler(
            service=idempotency_service,
            interval_seconds=settings.IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS,
        )
        idempotency_cleanup_task = asyncio.create_task(
            cleanup_scheduler.run_forever(),
            name="idempotency-cleanup",
        )
        if settings.TICK_AUTOPILOT_ENABLED:
            autopilot = TickAutopilot(
                graph_db=graph_db,
                tick_scheduler=get_tick_scheduler(),
                interval_seconds=settings.TICK_INTERVAL_SECONDS,
                game_seconds_per_tick=settings.TICK_GAME_SECONDS_PER_TICK,
                budget_guard=get_tick_budget_guard(),
            )
            autopilot_task = asyncio.create_task(autopilot.run_forever(), name="tick-autopilot")
        yield
    finally:
        if autopilot_task is not None:
            autopilot_task.cancel()
            with suppress(asyncio.CancelledError):
                await autopilot_task
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
            try:
                settings = get_settings()
                async with graph_db.get_session() as session:
                    await get_session_store().save_to_graph(
                        session=session,
                        max_persisted_turns=settings.MAX_PERSISTED_SESSION_TURNS,
                    )
                _logger.info("session_store.saved_to_graph")
            except Exception as exc:  # noqa: BLE001
                _logger.warning("session_store.save_on_shutdown_failed", extra={"error": str(exc)})
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
    register_exception_handlers(app)

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

    register_routers(app, settings)

    return app


app = create_app()
