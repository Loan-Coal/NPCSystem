"""
Package: routes.dialogue
Layer: api
Purpose: HTTP routers for player-NPC dialogue, interaction, and NPC state surface.
Public surface: action_router, dialogue_router, dialogue_ws_router, interaction_router, npc_state_router.
Does NOT: define route handlers, middleware, or app lifespan.
Dependencies injected: None (re-export hub).
"""

from __future__ import annotations

from .action import router as action_router
from .dialogue import router as dialogue_router
from .dialogue_ws import router as dialogue_ws_router
from .interaction import router as interaction_router
from .npc_state import router as npc_state_router

__all__ = [
    "action_router",
    "dialogue_router",
    "dialogue_ws_router",
    "interaction_router",
    "npc_state_router",
]
