"""
Module: planning_port
Layer: engines
Purpose: Structural Protocol for the planning graph domain (need reads, goal/goal-target
         writes, and the planning move) so the GOAP planning engines (GoalFormer +
         ActionSelector) depend on one abstraction and hold no Neo4j session
         (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, compute urgency/priority, or import graph functions
          (only the TimePoint domain model for the create_goal stamp).
Dependencies injected: none (pure interface).
Used by: engines/planning/goal_former + engines/planning/action_selector; implemented
         structurally by
         npc_engine.graph.repositories.planning_repository.Neo4jPlanningRepository.
"""

from __future__ import annotations

from typing import Any, Protocol

from npc_engine.world.time_utils import TimePoint


class PlanningGraphPort(Protocol):
    """Graph access for GOAP planning: need reads, goal writes, and the planning move."""

    async def get_needs_for_character(self, *, character_id: str) -> list[dict[str, Any]]:
        """Return all Need nodes for a character."""
        ...

    async def get_satisfying_location_for_need(self, *, need_kind: str) -> str | None:
        """Return a location id that satisfies the need kind, or None."""
        ...

    async def create_goal(
        self,
        *,
        character_id: str,
        description: str,
        urgency: int,
        game_time: TimePoint,
    ) -> str:
        """Create (MERGE-safe) a Goal node for the character and return its id."""
        ...

    async def create_goal_targets_edge(
        self, *, goal_id: str, target_id: str, priority: int
    ) -> None:
        """Write a GOAL_TARGETS edge from the goal to a target location."""
        ...

    async def move_character(self, *, character_id: str, location_id: str) -> None:
        """Move a character's LOCATED_AT edge to a new location (planning override)."""
        ...
