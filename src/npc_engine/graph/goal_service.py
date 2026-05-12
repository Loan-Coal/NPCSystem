"""
Module: goal_service
Layer: graph
Purpose: Functions for creating Goal nodes, retrieving them, and updating status.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.goal_queries, common.json_utils, world.time_utils
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.goals, npc_engine.retrieval.context_builder,
         npc_engine.engines.gossip.pair_selector
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.goal_queries import (
    CYPHER_CREATE_GOAL,
    CYPHER_UPDATE_GOAL_STATUS,
    get_goals_for_character,
)
from npc_engine.world.time_utils import TimePoint


async def create_goal(
    session: AsyncSession,
    *,
    character_id: str,
    description: str,
    urgency: int,
    game_time: TimePoint,
    target_id: str | None = None,
) -> str:
    """Create a Goal node and link it to a Character via a PURSUES edge.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node pursuing the goal.
        description: Freeform text describing the goal.
        urgency: Urgency level (0–100).
        game_time: Game-time snapshot at which the goal was formed.
        target_id: Optional ID of another node this goal targets.

    Returns:
        Generated UUID string for the new goal node.
    """
    goal_id = str(uuid.uuid4())
    game_time_json = dump_json(
        {
            "year": game_time.year,
            "season": game_time.season,
            "day": game_time.day,
            "time_of_day": game_time.time_of_day,
        }
    )
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_CREATE_GOAL,
            goal_id=goal_id,
            description=description,
            urgency=urgency,
            status="active",
            created_at_game_time=game_time_json,
            target_id=target_id or "",
            character_id=character_id,
        )
    return goal_id


async def get_goals_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 3,
    status_filter: str = "active",
) -> list[dict[str, Any]]:
    """Fetch top-k goals for a character ordered by urgency descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of goals to return.
        status_filter: Filter by goal status; empty string returns all statuses.

    Returns:
        List of goal property dicts sorted by urgency descending.
    """
    return await get_goals_for_character(
        session, character_id=character_id, k=k, status_filter=status_filter
    )


async def update_goal_status(
    session: AsyncSession,
    *,
    goal_id: str,
    new_status: str,
) -> None:
    """Update the status of an existing Goal node.

    Args:
        session: Active Neo4j async session.
        goal_id: ID of the Goal node to update.
        new_status: Replacement status value (active, achieved, or abandoned).
    """
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_UPDATE_GOAL_STATUS,
            goal_id=goal_id,
            status=new_status,
        )
