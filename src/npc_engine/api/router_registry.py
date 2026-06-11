"""
Module: router_registry
Layer: api
Purpose: Register all HTTP route routers (public /v1 + admin /v1/admin) and the dashboard on the app.
Does NOT: define route handlers, middleware, exception handlers, or app lifespan.
Dependencies injected: fastapi, config.Settings, all api.routes.* routers, api.dashboard_static.
Used by: api.main (create_app calls register_routers).
"""

from __future__ import annotations

from fastapi import FastAPI

from npc_engine.config import Settings
from npc_engine.api.dashboard_static import register_dashboard
from npc_engine.api.routes.action import router as action_router
from npc_engine.api.routes.batch import router as batch_router
from npc_engine.api.routes.clock import router as clock_router
from npc_engine.api.routes.dialogue import router as dialogue_router
from npc_engine.api.routes.dialogue_ws import router as dialogue_ws_router
from npc_engine.api.routes.graph import router as graph_router
from npc_engine.api.routes.beliefs import router as beliefs_router
from npc_engine.api.routes.goals import router as goals_router
from npc_engine.api.routes.items import router as items_router
from npc_engine.api.routes.memories import router as memories_router
from npc_engine.api.routes.secrets import router as secrets_router
from npc_engine.api.routes.debts import router as debts_router
from npc_engine.api.routes.factions import router as factions_router
from npc_engine.api.routes.schedules import router as schedules_router
from npc_engine.api.routes.reputation import admin_router as reputation_admin_router
from npc_engine.api.routes.reputation import graph_router as reputation_graph_router
from npc_engine.api.routes.graph_admin import router as graph_admin_router
from npc_engine.api.routes.npc_state import router as npc_state_router
from npc_engine.api.routes.interaction import router as interaction_router
from npc_engine.api.routes.quest import router as quest_router
from npc_engine.api.routes.quest_generation import router as quest_generation_router
from npc_engine.api.routes.economy import router as economy_router
from npc_engine.api.routes.location_history import router as location_history_router
from npc_engine.api.routes.causality import router as causality_router
from npc_engine.api.routes.witnessed import router as witnessed_router
from npc_engine.api.routes.groups import router as groups_router
from npc_engine.api.routes.relationship import router as relationship_router
from npc_engine.api.routes.rumors import router as rumors_router
from npc_engine.api.routes.gossip_spread import router as gossip_spread_router
from npc_engine.api.routes.rumor_trace import router as rumor_trace_router
from npc_engine.api.routes.skills import router as skills_router
from npc_engine.api.routes.traits import router as traits_router
from npc_engine.api.routes.pledges import router as pledges_router
from npc_engine.api.routes.treaties import router as treaties_router
from npc_engine.api.routes.debug_retrieval import router as debug_retrieval_router
from npc_engine.api.routes.locations import admin_router as locations_admin_router
from npc_engine.api.routes.locations import read_router as locations_read_router
from npc_engine.api.routes.player_events import router as player_events_router
from npc_engine.api.routes.system import admin_router as system_admin_router
from npc_engine.api.routes.system import router as system_router
from npc_engine.api.routes.system import v1_router as system_v1_router


def _register_public_routers(app: FastAPI, settings: Settings) -> None:
    """Register the game-engine public surface under /v1/ (plus the auth-free system route).

    Args:
        app: The FastAPI application.
        settings: Runtime settings providing the /v1 prefix and feature flags.
    """
    app.include_router(system_router)  # Public system routes (no auth)
    app.include_router(dialogue_router, prefix=settings.API_V1_PREFIX)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router, prefix=settings.API_V1_PREFIX)
    app.include_router(npc_state_router, prefix=settings.API_V1_PREFIX)
    app.include_router(action_router, prefix=settings.API_V1_PREFIX)
    app.include_router(interaction_router, prefix=settings.API_V1_PREFIX)
    app.include_router(quest_router, prefix=settings.API_V1_PREFIX)
    app.include_router(clock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(system_v1_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(reputation_graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(relationship_router, prefix=settings.API_V1_PREFIX)
    app.include_router(locations_read_router, prefix=settings.API_V1_PREFIX)
    app.include_router(player_events_router, prefix=settings.API_V1_PREFIX)


def _register_admin_routers(app: FastAPI, settings: Settings) -> None:
    """Register the admin / designer-tooling surface under /v1/admin/.

    Args:
        app: The FastAPI application.
        settings: Runtime settings providing the /v1 prefix used to derive the admin prefix.
    """
    admin_prefix = f"{settings.API_V1_PREFIX}/admin"
    app.include_router(system_admin_router, prefix=admin_prefix)
    app.include_router(batch_router, prefix=admin_prefix)
    app.include_router(graph_admin_router, prefix=admin_prefix)
    app.include_router(beliefs_router, prefix=admin_prefix)
    app.include_router(goals_router, prefix=admin_prefix)
    app.include_router(items_router, prefix=admin_prefix)
    app.include_router(memories_router, prefix=admin_prefix)
    app.include_router(secrets_router, prefix=admin_prefix)
    app.include_router(debts_router, prefix=admin_prefix)
    app.include_router(factions_router, prefix=admin_prefix)
    app.include_router(schedules_router, prefix=admin_prefix)
    app.include_router(reputation_admin_router, prefix=admin_prefix)
    app.include_router(quest_generation_router, prefix=admin_prefix)
    app.include_router(economy_router, prefix=admin_prefix)
    app.include_router(location_history_router, prefix=admin_prefix)
    app.include_router(causality_router, prefix=admin_prefix)
    app.include_router(witnessed_router, prefix=admin_prefix)
    app.include_router(groups_router, prefix=admin_prefix)
    app.include_router(rumors_router, prefix=admin_prefix)
    app.include_router(gossip_spread_router, prefix=admin_prefix)
    app.include_router(rumor_trace_router, prefix=admin_prefix)
    app.include_router(skills_router, prefix=admin_prefix)
    app.include_router(traits_router, prefix=admin_prefix)
    app.include_router(pledges_router, prefix=admin_prefix)
    app.include_router(treaties_router, prefix=admin_prefix)
    app.include_router(debug_retrieval_router, prefix=admin_prefix)
    app.include_router(locations_admin_router, prefix=admin_prefix)


def register_routers(app: FastAPI, settings: Settings) -> None:
    """Register all route routers and the designer dashboard on the app.

    Args:
        app: The FastAPI application.
        settings: Runtime settings providing prefixes and feature flags.
    """
    _register_public_routers(app, settings)
    _register_admin_routers(app, settings)
    register_dashboard(app)  # Designer web dashboard (Phase 12) — auth-exempt static assets.
