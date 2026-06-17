"""
Module: goal_former_adapter
Layer: engines
Purpose: Adapts GoalFormer to the BaseEngine protocol — on each tick fetches all
         active NPC ids, reads the current game time from WorldState, calls
         GoalFormer.form_goal for each NPC, then passes each formed goal to
         ActionSelector to optionally dispatch a move.
Dependencies: npc_engine.engines.planning.goal_former,
              npc_engine.engines.planning.action_selector,
              npc_engine.engines.ports.character_read_port (CharacterReadPort),
              npc_engine.engines.ports.world_state_port (WorldStateGraphPort),
              npc_engine.config (get_settings).
Used by: npc_engine.scheduler.tick_scheduler (injected as goal_formation_engine),
         npc_engine.api.dependencies_engines.get_goal_formation_engine.

Does NOT: call LLMs, open transactions, hold a session, or import from api/, services/,
          or the graph layer.
Dependencies injected: goal_former, action_selector, character_reader,
                       world_state_repo (via __init__).
"""

from __future__ import annotations

from typing import Any


from npc_engine.config import get_settings
from npc_engine.engines.planning.action_selector import ActionSelector
from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.engines.ports.character_read_port import CharacterReadPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort
from npc_engine.world.time_utils import TimePoint


class GoalFormerAdapter:
    """Wraps GoalFormer + ActionSelector in the BaseEngine protocol for tick-scheduler integration.

    On each ``run_tick``:
    1. Fetches all active NPC ids from the graph.
    2. Reads current game time from WorldState.
    3. Calls ``GoalFormer.form_goal`` for each NPC.
    4. For each formed goal calls ``ActionSelector.select_action`` which moves the NPC
       if the goal urgency exceeds ROUTINE_PRIORITY.
    5. Returns a summary dict[str, Any] listing all goal node ids created (None omitted).

    Attributes:
        _goal_former: Injected GoalFormer instance.
        _action_selector: Injected ActionSelector instance.
        _character_reader: Injected CharacterReadPort (active NPC ids).
        _world_state_repo: Injected WorldStateGraphPort (current game time).
    """

    def __init__(
        self,
        goal_former: GoalFormer,
        action_selector: ActionSelector,
        character_reader: CharacterReadPort,
        world_state_repo: WorldStateGraphPort,
    ) -> None:
        """Initialise the adapter with injected engines and read ports.

        Args:
            goal_former: GoalFormer instance (injected PlanningGraphPort).
            action_selector: ActionSelector instance (injected PlanningGraphPort).
            character_reader: CharacterReadPort for active NPC ids.
            world_state_repo: WorldStateGraphPort for the current game time.
        """
        self._goal_former = goal_former
        self._action_selector = action_selector
        self._character_reader = character_reader
        self._world_state_repo = world_state_repo

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Run goal formation and action selection for all active NPCs.

        Args:
            tick_id: Current tick ID (passed through to logs; not used for logic).
            **_: Swallows the scheduler's session= kwarg during the SEV-24 migration.

        Returns:
            Dict with ``goal_formations``: list of goal node IDs created this tick
            (NPCs with no needs produce None and are excluded from the list).
        """
        npc_ids = await self._character_reader.get_npc_ids()
        if not npc_ids:
            return {"goal_formations": [], "tick_id": tick_id}

        world_state = await self._world_state_repo.get_world_state(world_id=get_settings().WORLD_ID)
        game_time = TimePoint(
            year=world_state.year,
            season=world_state.season,
            day=world_state.day,
            time_of_day=world_state.time_of_day,
        )

        goal_ids: list[str] = []
        for npc_id in npc_ids:
            result = await self._goal_former.form_goal(character_id=npc_id, game_time=game_time)
            if result is None:
                continue
            goal_id, urgency, target_location_id = result
            goal_ids.append(goal_id)
            await self._action_selector.select_action(
                character_id=npc_id,
                goals=[{"goal_id": goal_id, "urgency": urgency, "status": "active", "target_location_id": target_location_id}],
            )

        return {"goal_formations": goal_ids, "tick_id": tick_id}
