"""
Package: routes.admin
Layer: api
Purpose: HTTP routers for admin/designer tooling (batch ops, graph admin, system, debug, investigations).
Public surface: batch_router, graph_router, graph_admin_router, system_router, system_admin_router, system_v1_router, debug_retrieval_router, investigations_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .batch import router as batch_router
from .debug_retrieval import router as debug_retrieval_router
from .graph import router as graph_router
from .graph_admin import router as graph_admin_router
from .investigations import router as investigations_router
from .system import admin_router as system_admin_router
from .system import router as system_router
from .system import v1_router as system_v1_router

__all__ = [
    "batch_router",
    "debug_retrieval_router",
    "graph_router",
    "graph_admin_router",
    "investigations_router",
    "system_admin_router",
    "system_router",
    "system_v1_router",
]
