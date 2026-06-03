"""
Module: system
Layer: api
Purpose: System-level API routes — health check, engine-status observability,
         and admin tooling probes.
Does NOT: mutate state or call external services directly.
Dependencies injected: SchemaConfig, TypeRegistry, TickScheduler, AsyncSession.
Used by: main.py (router, admin_router, v1_router)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session, get_game_schema, get_tick_scheduler, get_type_registry
from npc_engine.api.dependency_singletons import _llm_adapters_to_close
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.event_feed_queries import get_recent_event_feed
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.serializer import serialize_registry_snapshot

_DEFAULT_EVENT_LIMIT = 20


router = APIRouter()
admin_router = APIRouter()
v1_router = APIRouter(prefix="/system")


@router.get("/health")
async def health() -> dict:
    """Return liveness and basic service status."""
    return ok_response({"status": "ok", "tick": 0, "neo4j": "degraded"})


@router.get("/readiness")
async def readiness() -> dict:
    """Return readiness including LLM backend reachability."""
    llm_ready = True
    for adapter in _llm_adapters_to_close:
        if hasattr(adapter, "health_check"):
            if not await adapter.health_check():
                llm_ready = False
                break
    status = "ready" if llm_ready else "degraded"
    return ok_response({"status": status, "llm": "ok" if llm_ready else "unreachable"})


@admin_router.get("/protected")
async def protected_probe() -> dict:
    """Simple protected route for auth smoke testing."""
    return ok_response({"status": "authorized"})


@admin_router.get("/schema")
async def schema_snapshot(schema: SchemaConfig = Depends(get_game_schema)) -> dict:
    """Expose loaded game schema for authenticated admin clients."""
    return ok_response(schema.model_dump(mode="json"))


@admin_router.get("/schema/registry")
async def registry_schema_snapshot(registry: TypeRegistry = Depends(get_type_registry)) -> dict:
    """Expose type-registry snapshot for authenticated admin clients."""
    return ok_response(serialize_registry_snapshot(registry=registry))


@v1_router.get("/engines")
async def engine_status(scheduler: TickScheduler = Depends(get_tick_scheduler)) -> dict:
    """Return per-engine last-run tick, last error, and error count.

    Buyer-facing observability surface. Each entry corresponds to one registered
    engine; engines that have never run are absent from the response.

    Returns:
        Dict with ``data`` list of EngineStatusRecord dicts.
    """
    records = [
        record.model_dump()
        for record in scheduler.engine_status.values()
    ]
    return ok_response(records)


@v1_router.get("/events")
async def recent_events(
    limit: int = Query(default=_DEFAULT_EVENT_LIMIT, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return the most recent Event nodes ordered by tick descending.

    Used by the demo WORLD panel to display a live event feed.

    Args:
        limit: Maximum number of events to return (1–100, default 20).
    Returns:
        Dict with ``data`` list of event dicts.
    """
    events = await get_recent_event_feed(session, limit=limit)
    return ok_response(events)
