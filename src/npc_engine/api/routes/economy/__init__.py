"""
Package: routes.economy
Layer: api
Purpose: HTTP routers for items, skills, traits, economy, and groups.
Public surface: items_router, skills_router, traits_router, economy_router, groups_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .economy import router as economy_router
from .groups import router as groups_router
from .items import router as items_router
from .skills import router as skills_router
from .traits import router as traits_router

__all__ = [
    "economy_router",
    "groups_router",
    "items_router",
    "skills_router",
    "traits_router",
]
