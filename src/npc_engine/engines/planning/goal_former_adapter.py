"""
Module: goal_former_adapter
Layer: engines
Purpose: Adapts GoalFormer to the BaseEngine protocol — on each tick fetches all
         active NPC ids, reads the current game time from WorldState, calls
         GoalFormer.form_goal for each NPC, then passes each formed goal to
         ActionSelector to optionally dispatch a move.
Dependencies: npc_engine.engines.planning.goal_former,
              npc_engine.engines.planning.action_selector,
              npc_engine.graph.character_reader (get_npc_ids),
              npc_engine.graph.world_state_reader (get_world_state),
              npc_engine.config (get_settings).
Used by: npc_engine.scheduler.tick_scheduler (injected as goal_formation_engine),
         npc_engine.api.dependencies_engines.get_goal_formation_engine.

Does NOT: call LLMs, open transactions, or import from api/ or services/.
Dependencies injected: goal_former, action_selector (via __init__).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.config import get_settings
from npc_engine.engines.planning.action_selector import ActionSelector
from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.graph.character_reader import get_npc_ids
from npc_engine.world.time_utils import TimePoint
from npc_engine.graph.world_state_reader import get_world_state


class GoalFormerAdapter:
    """Wraps GoalFormer + ActionSelector in the BaseEngine protocol for tick-scheduler integration.

    On each ``run_tick``:
    1. Fetches all active NPC ids from the graph.
    2. Reads current game time from WorldState.
    3. Calls ``GoalFormer.form_goal`` for each NPC.
    4. For each formed goal calls ``ActionSelector.select_action`` which moves the NPC
       if the goal urgency exceeds ROUTINE_PRIORITY.
    5. Returns a summary dict listing all goal node ids created (None omitted).

    Attributes:
        _goal_former: Injected GoalFormer instance.
        _action_selector: Injected ActionSelector instance.
    """

    def __init__(
        self,
        goal_former: GoalFormer | None = None,
        action_selector: ActionSelector | None = None,
    ) -> None:
        """Initialise the adapter.

        Args:
            goal_former: GoalFormer instance; constructed with defaults when None.
            action_selector: ActionSelector instance; constructed with defaults when None.
        """
        self._goal_former = goal_former if goal_former is not None else GoalFormer()
        self._action_selector = action_selector if action_selector is not None else ActionSelector()

    async def run_tick(self, *, session: AsyncSession, tick_id: int, **_: Any) -> dict:
        """Run goal formation and action selection for all active NPCs.

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
            result = await self._goal_former.form_goal(
                session, character_id=npc_id, game_time=game_time
            )
            if result is None:
                continue
            goal_id, urgency, target_location_id = result
            goal_ids.append(goal_id)
            await self._action_selector.select_action(
                session,
                character_id=npc_id,
                goals=[{"goal_id": goal_id, "urgency": urgency, "status": "active", "target_location_id": target_location_id}],
            )

        return {"goal_formations": goal_ids, "tick_id": tick_id}
