"""
Module: goal_former_adapter
Layer: engines
Purpose: Adapts GoalFormer to the BaseEngine protocol — on each tick fetches all
         active NPC ids, reads the current game time from WorldState, and calls
         GoalFormer.form_goal for each NPC.
Dependencies: npc_engine.engines.planning.goal_former,
              npc_engine.graph.character_reader (get_npc_ids),
              npc_engine.world.world_reader (get_world_state),
              npc_engine.config (get_settings).
Used by: npc_engine.scheduler.tick_scheduler (injected as goal_formation_engine),
         npc_engine.api.dependencies_engines.get_goal_formation_engine.

Does NOT: call LLMs, open transactions, or import from api/ or services/.
Dependencies injected: goal_former (via __init__).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.config import get_settings
from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.graph.character_reader import get_npc_ids
from npc_engine.world.time_utils import TimePoint
from npc_engine.world.world_reader import get_world_state


class GoalFormerAdapter:
    """Wraps GoalFormer in the BaseEngine protocol for tick-scheduler integration.

    On each ``run_tick``:
    1. Fetches all active NPC ids from the graph.
    2. Reads current game time from WorldState.
    3. Calls ``GoalFormer.form_goal`` for each NPC.
    4. Returns a summary dict listing all goal node ids created (None omitted).

    Attributes:
        _goal_former: Injected GoalFormer instance.
    """

    def __init__(self, goal_former: GoalFormer | None = None) -> None:
        """Initialise the adapter.

        Args:
            goal_former: GoalFormer instance; constructed with defaults when None.
        """
        self._goal_former = goal_former if goal_former is not None else GoalFormer()

    async def run_tick(self, *, session: AsyncSession, tick_id: int, **_: Any) -> dict:
        """Run goal formation for all active NPCs.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick ID (passed through to logs; not used for logic).

        Returns:
            Dict with ``goal_formations``: list of goal node IDs created this tick
            (NPCs with no needs produce None and are excluded from the list).
        """
        npc_ids = await get_npc_ids(session)
        if not npc_ids:
            return {"goal_formations": [], "tick_id": tick_id}

        world_state = await get_world_state(session=session, world_id=get_settings().WORLD_ID)
        game_time = TimePoint(
            year=world_state.year,
            season=world_state.season,
            day=world_state.day,
            time_of_day=world_state.time_of_day,
        )

        goal_ids: list[str] = []
        for npc_id in npc_ids:
            goal_id = await self._goal_former.form_goal(
                session, character_id=npc_id, game_time=game_time
            )
            if goal_id is not None:
                goal_ids.append(goal_id)

        return {"goal_formations": goal_ids, "tick_id": tick_id}
