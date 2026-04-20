"""
system.py - System-level API routes such as health and auth smoke probes.

Does NOT: run domain engines or mutate graph state.

Dependencies injected: None.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_game_schema, get_type_registry
from api.route_helpers import ok_response
from schema.schema_models import SchemaConfig
from type_registry.contracts import TypeRegistry
from type_registry.serializer import serialize_registry_snapshot


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str | int]:
    """Return liveness and basic service status."""

    return ok_response({"status": "ok", "tick": 0, "neo4j": "degraded"})


@router.get("/v1/protected")
async def protected_probe() -> dict[str, str]:
    """Simple protected route for auth smoke testing."""

    return ok_response({"status": "authorized"})


@router.get("/v1/schema")
async def schema_snapshot(schema: SchemaConfig = Depends(get_game_schema)) -> dict:
    """Expose loaded game schema for authenticated clients."""

    return ok_response(schema.model_dump(mode="json"))


@router.get("/v1/schema/registry")
async def registry_schema_snapshot(registry: TypeRegistry = Depends(get_type_registry)) -> dict:
    """Expose type-registry snapshot for authenticated clients."""

    return ok_response(serialize_registry_snapshot(registry=registry))
