"""
Module: group_port
Layer: engines
Purpose: Structural Protocol for the group graph domain (read high-affection pairs,
         existing shared groups, and stale cliques; create groups, add members, and
         dissolve groups), so CliqueFormationEngine depends on an abstraction instead
         of importing group_queries/group_service and holding a Neo4j session.
         Implemented in graph/repositories/group_repository.py.
Does NOT: open sessions, run Cypher, contain clique-formation logic, or import graph.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.clique.clique_formation_engine; implemented structurally by
         npc_engine.graph.repositories.group_repository.Neo4jGroupRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class GroupGraphPort(Protocol):
    """Graph operations required by CliqueFormationEngine (group reads + writes)."""

    async def get_high_affection_pairs(self, *, threshold: int) -> list[dict[str, Any]]:
        """Return co-located character pairs whose mutual affection exceeds the threshold."""
        ...

    async def get_existing_shared_group(
        self, *, char_a_id: str, char_b_id: str
    ) -> dict[str, Any] | None:
        """Return the shared active clique group for two characters, or None."""
        ...

    async def get_stale_cliques(self, *, stale_before_tick: int) -> list[str]:
        """Return ids of clique groups formed before the given tick."""
        ...

    async def create_group(
        self,
        *,
        name: str,
        kind: str,
        cohesion: int,
        is_secret: bool,
        formed_at_tick: int,
    ) -> str:
        """Create a Group node and return its id."""
        ...

    async def add_member(
        self,
        *,
        group_id: str,
        character_id: str,
        role: str,
        joined_at_tick: int,
        commitment: int,
    ) -> None:
        """Add or update a character's membership in a group."""
        ...

    async def dissolve_group(self, *, group_id: str, tick: int) -> None:
        """Mark a group as dissolved at the given tick."""
        ...
