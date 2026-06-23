"""
Package: routes.faction_politics
Layer: api
Purpose: HTTP routers for factions, schemes, pledges, and treaties.
Public surface: factions_router, schemes_router, pledges_router, treaties_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .factions import router as factions_router
from .pledges import router as pledges_router
from .schemes import router as schemes_router
from .treaties import router as treaties_router

__all__ = [
    "factions_router",
    "pledges_router",
    "schemes_router",
    "treaties_router",
]
