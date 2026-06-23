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
from npc_engine.api.dashboard import register_dashboard
from npc_engine.api.routes.admin import (
    batch_router,
    debug_retrieval_router,
    graph_admin_router,
    graph_router,
    investigations_router,
    system_admin_router,
    system_router,
    system_v1_router,
)
from npc_engine.api.routes.dialogue import (
    action_router,
    dialogue_router,
    dialogue_ws_router,
    interaction_router,
    npc_state_router,
)
from npc_engine.api.routes.economy import (
    economy_router,
    groups_router,
    items_router,
    skills_router,
    traits_router,
)
from npc_engine.api.routes.faction_politics import (
    factions_router,
    pledges_router,
    schemes_router,
    treaties_router,
)
from npc_engine.api.routes.knowledge import (
    beliefs_router,
    causality_router,
    debts_router,
    goals_router,
    gossip_spread_router,
    memories_router,
    rumor_trace_router,
    rumors_router,
    secrets_router,
    witnessed_router,
)
from npc_engine.api.routes.quest import quest_generation_router, quest_router
from npc_engine.api.routes.social import (
    player_model_router,
    relationship_router,
    reputation_admin_router,
    reputation_graph_router,
)
from npc_engine.api.routes.setup import setup_router
from npc_engine.api.routes.world import (
    chapters_router,
    clock_router,
    location_history_router,
    locations_admin_router,
    locations_read_router,
    player_events_router,
    schedules_router,
)


def _register_public_routers(app: FastAPI, settings: Settings) -> None:
    """Register the game-engine public surface under /v1/ (plus the auth-free system route).

    Args:
        app: The FastAPI application.
        settings: Runtime settings providing the /v1 prefix and feature flags.
    """
    app.include_router(setup_router)   # Auth-exempt setup routes (DEC-131, INTEG-01..03)
    app.include_router(system_router)  # Public system routes (no auth)
    app.include_router(dialogue_router, prefix=settings.API_V1_PREFIX)
    if settings.DIALOGUE_STREAM_ENABLED:
        app.include_router(dialogue_ws_router, prefix=settings.API_V1_PREFIX)
    app.include_router(npc_state_router, prefix=settings.API_V1_PREFIX)
    app.include_router(action_router, prefix=settings.API_V1_PREFIX)
    app.include_router(interaction_router, prefix=settings.API_V1_PREFIX)
    app.include_router(quest_router, prefix=settings.API_V1_PREFIX)
    app.include_router(clock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(reputation_graph_router, prefix=settings.API_V1_PREFIX)
    app.include_router(relationship_router, prefix=settings.API_V1_PREFIX)
    app.include_router(player_model_router, prefix=settings.API_V1_PREFIX)
    app.include_router(schemes_router, prefix=settings.API_V1_PREFIX)
    app.include_router(locations_read_router, prefix=settings.API_V1_PREFIX)
    app.include_router(player_events_router, prefix=settings.API_V1_PREFIX)
    app.include_router(investigations_router, prefix=settings.API_V1_PREFIX)
    app.include_router(chapters_router, prefix=settings.API_V1_PREFIX)


def _register_admin_routers(app: FastAPI, settings: Settings) -> None:
    """Register the admin / designer-tooling surface under /v1/admin/.

    Args:
        app: The FastAPI application.
        settings: Runtime settings providing the /v1 prefix used to derive the admin prefix.
    """
    admin_prefix = f"{settings.API_V1_PREFIX}/admin"
    app.include_router(system_admin_router, prefix=admin_prefix)
    # SEV-14 (DEC-112): system observability moved here from the bare /v1 prefix
    # → /v1/admin/system/* (now admin-scoped). v1_router carries its own /system prefix.
    app.include_router(system_v1_router, prefix=admin_prefix)
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
