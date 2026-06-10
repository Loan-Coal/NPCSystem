"""
Module: goal_former
Layer: engines
Purpose: Reads NPC Need nodes, identifies the most-decayed need, and forms a Goal node
         with urgency = min(MAX_URGENCY, MAX_URGENCY - need.level). Writes a GOAL_TARGETS
         edge to the first satisfying location found for that need kind.
Dependencies: npc_engine.graph.need_queries, npc_engine.graph.goal_service,
              npc_engine.graph.goal_targets_writer, npc_engine.engines.planning.action_priority,
              npc_engine.utils.logging, npc_engine.world.time_utils
Used by: npc_engine.scheduler.tick_scheduler (slice-2 wiring)
Does NOT: call LLMs, open transactions, run Cypher, or import from api/, services/, or retrieval/.
Dependencies injected: AsyncSession (passed per call).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.engines.planning.action_priority import MAX_URGENCY
from npc_engine.graph.goal_service import create_goal
from npc_engine.graph.goal_targets_writer import create_goal_targets_edge
from npc_engine.graph.need_queries import get_needs_for_character, get_satisfying_location_for_need
from npc_engine.utils.logging import get_logger
from npc_engine.world.time_utils import TimePoint

logger: logging.Logger = get_logger("npc_engine.engines.planning.goal_former")


class GoalFormer:
    """Reads NPC needs and creates a Goal node targeting the most-decayed need.

    For each call to form_goal the engine:
    1. Fetches all needs for the character.
    2. Selects the need with the lowest level (most depleted).
    3. Computes urgency = min(MAX_URGENCY, MAX_URGENCY - need.level).
    4. Creates a Goal node via goal_service.create_goal (MERGE-safe).
    5. If a satisfying location exists, creates a GOAL_TARGETS edge to it.

    No state is stored on the instance; all dependencies are injected per call.
    """

    async def form_goal(
        self,
        session: AsyncSession,
        *,
        character_id: str,
        game_time: TimePoint,
    ) -> str | None:
        """Form a goal for the character's most-decayed need.
        Args:
            session: Active Neo4j async session.
            character_id: ID of the character to plan for.
            game_time: Current game time (stamped onto the goal node).

        Returns:
            The goal node ID if a goal was created, or None if the character
            has no needs.
        """
        needs = await get_needs_for_character(session, character_id)
        if not needs:
            logger.info("goal_former.no_needs", extra={"character_id": character_id})
            return None

        worst_need = min(needs, key=lambda n: n["level"])
        urgency = self._compute_urgency(worst_need["level"])
        goal_id = await create_goal(
            session,
            character_id=character_id,
            description=f"satisfy {worst_need['kind']} need",
            urgency=urgency,
            game_time=game_time,
        )
        logger.info(
            "goal_former.goal_created",
            extra={
                "character_id": character_id,
                "need_kind": worst_need["kind"],
                "need_level": worst_need["level"],
                "urgency": urgency,
                "goal_id": goal_id,
            },
        )
        await self._maybe_write_goal_targets(session, goal_id, worst_need["kind"], urgency)
        return goal_id

    async def _maybe_write_goal_targets(
        self,
        session: AsyncSession,
        goal_id: str,
        need_kind: str,
        urgency: int,
    ) -> None:
        target_location_id = await get_satisfying_location_for_need(session, need_kind)
        if target_location_id is None:
            return
        await create_goal_targets_edge(session, goal_id, target_location_id, urgency)
        logger.info(
            "goal_former.goal_targets_edge_written",
            extra={"goal_id": goal_id, "target_location_id": target_location_id, "priority": urgency},
        )

    @staticmethod
    def _compute_urgency(need_level: int) -> int:
        """Compute urgency from a need level; clamped to [0, MAX_URGENCY].

        Args:
            need_level: Current need level (0–100; 0 is fully depleted).

        Returns:
            Urgency in range [0, MAX_URGENCY].
        """
        return min(MAX_URGENCY, MAX_URGENCY - need_level)
