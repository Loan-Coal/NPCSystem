"""
system.py - System-level API routes such as health and auth smoke probes.

Does NOT: run domain engines or mutate graph state.

Dependencies injected: None.
"""

from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str | int]:
    """Return liveness and basic service status."""

    return {"status": "ok", "tick": 0, "neo4j": "degraded"}


@router.get("/protected")
async def protected_probe() -> dict[str, str]:
    """Simple protected route for auth smoke testing."""

    return {"status": "authorized"}
