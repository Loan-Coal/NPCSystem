"""
Package: routes.social
Layer: api
Purpose: HTTP routers for relationships, reputation, and player-model reads.
Public surface: relationship_router, reputation_admin_router, reputation_graph_router, player_model_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .player_model import router as player_model_router
from .relationship import router as relationship_router
from .reputation import admin_router as reputation_admin_router
from .reputation import graph_router as reputation_graph_router

__all__ = [
    "player_model_router",
    "relationship_router",
    "reputation_admin_router",
    "reputation_graph_router",
]
