"""
Package: routes.world
Layer: api
Purpose: HTTP routers for world time, locations, location history/graph, chapters, schedules, and player events.
Public surface: clock_router, locations_admin_router, locations_read_router, location_history_router, location_graph_router, chapters_router, player_events_router, schedules_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .chapters import router as chapters_router
from .clock import router as clock_router
from .location_graph import router as location_graph_router
from .location_history import router as location_history_router
from .locations import admin_router as locations_admin_router
from .locations import read_router as locations_read_router
from .player_events import router as player_events_router
from .schedules import router as schedules_router

__all__ = [
    "chapters_router",
    "clock_router",
    "location_graph_router",
    "location_history_router",
    "locations_admin_router",
    "locations_read_router",
    "player_events_router",
    "schedules_router",
]
