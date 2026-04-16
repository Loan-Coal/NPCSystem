"""
system.py - System-level API routes such as health and auth smoke probes.

Does NOT: run domain engines or mutate graph state.

Dependencies injected: None.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_game_schema
from schema.schema_models import SchemaConfig


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str | int]:
    """Return liveness and basic service status."""

    return {"status": "ok", "tick": 0, "neo4j": "degraded"}


@router.get("/v1/protected")
async def protected_probe() -> dict[str, str]:
    """Simple protected route for auth smoke testing."""

    return {"status": "authorized"}


@router.get("/v1/schema")
async def schema_snapshot(schema: SchemaConfig = Depends(get_game_schema)) -> dict:
    """Expose loaded game schema for authenticated clients."""

    return schema.model_dump(mode="json")
