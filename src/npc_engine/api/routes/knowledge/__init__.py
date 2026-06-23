"""
Package: routes.knowledge
Layer: api
Purpose: HTTP routers for NPC knowledge graph reads/writes (beliefs, memories, goals, secrets, debts, rumors, gossip, causality, witnessing).
Public surface: beliefs_router, memories_router, goals_router, secrets_router, debts_router, rumors_router, gossip_spread_router, rumor_trace_router, causality_router, witnessed_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .beliefs import router as beliefs_router
from .causality import router as causality_router
from .debts import router as debts_router
from .goals import router as goals_router
from .gossip_spread import router as gossip_spread_router
from .memories import router as memories_router
from .rumor_trace import router as rumor_trace_router
from .rumors import router as rumors_router
from .secrets import router as secrets_router
from .witnessed import router as witnessed_router

__all__ = [
    "beliefs_router",
    "causality_router",
    "debts_router",
    "goals_router",
    "gossip_spread_router",
    "memories_router",
    "rumor_trace_router",
    "rumors_router",
    "secrets_router",
    "witnessed_router",
]
