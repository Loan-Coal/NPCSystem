"""
Package: routes.quest
Layer: api
Purpose: HTTP routers for quest lifecycle and quest generation.
Public surface: quest_router, quest_generation_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .quest import router as quest_router
from .quest_generation import router as quest_generation_router

__all__ = [
    "quest_router",
    "quest_generation_router",
]
