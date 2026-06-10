"""
Module: action_selector
Layer: engines
Purpose: Given a character's active goals, selects the highest-urgency one and
         dispatches a move action if its urgency exceeds ROUTINE_PRIORITY.
         Goals at or below ROUTINE_PRIORITY are ignored — the routine engine
         has already placed the NPC.
Dependencies: npc_engine.engines.planning.action_priority,
              npc_engine.graph.routine_queries,
              npc_engine.utils.logging
Used by: npc_engine.scheduler.tick_scheduler (slice-2 wiring)
Does NOT: call LLMs, read from Neo4j directly, or import from api/ or services/.
Dependencies injected: AsyncSession (passed per call), goal list (passed per call).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.planning.action_priority import ROUTINE_PRIORITY
from npc_engine.graph.routine_queries import update_character_location
from npc_engine.utils.logging import get_logger

logger: logging.Logger = get_logger("npc_engine.engines.planning.action_selector")


class ActionSelector:
    """Picks the highest-urgency active goal and dispatches a move if warranted.

    The selector compares the top goal's urgency against ROUTINE_PRIORITY (50).
    - urgency > ROUTINE_PRIORITY  → call update_character_location (planning wins)
    - urgency <= ROUTINE_PRIORITY → no-op (routine engine keeps control)

    No state is stored on the instance; all dependencies are injected per call.
    """

    async def select_action(
        self,
        session: AsyncSession,
        *,
        character_id: str,
        goals: list[dict],
    ) -> None:
        """Evaluate goals and dispatch a move action if the top goal overrides routine.

        Args:
            session: Active Neo4j async session.
            character_id: ID of the NPC being evaluated.
            goals: List of active goal dicts with keys: goal_id, urgency,
                   status, target_location_id.  Callers supply pre-fetched goals
                   to keep graph reads in the graph layer.
        """
        if not goals:
            logger.info("action_selector.no_goals", extra={"character_id": character_id})
            return

        top_goal = max(goals, key=lambda g: g["urgency"])
        urgency: int = top_goal["urgency"]
        logger.info(
            "action_selector.top_goal",
            extra={
                "character_id": character_id,
                "goal_id": top_goal["goal_id"],
                "urgency": urgency,
                "routine_priority": ROUTINE_PRIORITY,
            },
        )

        if urgency <= ROUTINE_PRIORITY:
            logger.info("action_selector.deferred_to_routine", extra={"character_id": character_id, "urgency": urgency})
            return

        await self._dispatch_move(session, character_id, top_goal)

    async def _dispatch_move(
        self,
        session: AsyncSession,
        character_id: str,
        goal: dict,
    ) -> None:
        target_location_id: str | None = goal.get("target_location_id")
        if target_location_id is None:
            logger.info(
                "action_selector.no_target_location",
                extra={"character_id": character_id, "goal_id": goal["goal_id"]},
            )
            return
        await update_character_location(session, character_id=character_id, location_id=target_location_id)
        logger.info(
            "action_selector.move_dispatched",
            extra={"character_id": character_id, "location_id": target_location_id, "urgency": goal["urgency"]},
        )
