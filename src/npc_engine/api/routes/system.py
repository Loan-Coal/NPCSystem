"""
Module: system
Layer: api
Purpose: System-level API routes — health check and admin tooling probes.
Does NOT: mutate state or call external services directly.
Dependencies injected: SchemaConfig and TypeRegistry via FastAPI Depends().
Used by: main.py (both router and admin_router)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from npc_engine.api.dependencies import get_game_schema, get_type_registry
from npc_engine.api.route_helpers import ok_response
from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.serializer import serialize_registry_snapshot


router = APIRouter()
admin_router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Return liveness and basic service status."""
    return ok_response({"status": "ok", "tick": 0, "neo4j": "degraded"})


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
