"""
Module: group_repository
Layer: graph
Purpose: Neo4j adapter for the group graph domain. Opens a session per operation from
         the injected GraphDB and delegates to group_queries/group_service, so
         CliqueFormationEngine depends on the abstraction and holds no session. Swap
         seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: contain clique-formation logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.social.get_clique_formation_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.group_queries import (
    get_existing_shared_group,
    get_high_affection_pairs,
    get_stale_cliques,
)
from npc_engine.graph.group_service import add_member, create_group, dissolve_group


class Neo4jGroupRepository:
    """Session-per-call Neo4j adapter for the group domain (GroupGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_high_affection_pairs(self, *, threshold: int) -> list[dict[str, Any]]:
        """Open a session and return co-located high-affection character pairs."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_high_affection_pairs(session, threshold=threshold)

    async def get_existing_shared_group(
        self, *, char_a_id: str, char_b_id: str
    ) -> dict[str, Any] | None:
        """Open a session and return the shared active clique group, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_existing_shared_group(
                session, char_a_id=char_a_id, char_b_id=char_b_id
            )

    async def get_stale_cliques(self, *, stale_before_tick: int) -> list[str]:
        """Open a session and return ids of clique groups formed before the given tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_stale_cliques(session, stale_before_tick=stale_before_tick)

    async def create_group(
        self,
        *,
        name: str,
        kind: str,
        cohesion: int,
        is_secret: bool,
        formed_at_tick: int,
    ) -> str:
        """Open a session, create a Group node, and return its id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await create_group(
                session,
                name=name,
                kind=kind,
                cohesion=cohesion,
                is_secret=is_secret,
                formed_at_tick=formed_at_tick,
            )

    async def add_member(
        self,
        *,
        group_id: str,
        character_id: str,
        role: str,
        joined_at_tick: int,
        commitment: int,
    ) -> None:
        """Open a session and add or update a character's group membership."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await add_member(
                session,
                group_id=group_id,
                character_id=character_id,
                role=role,
                joined_at_tick=joined_at_tick,
                commitment=commitment,
            )

    async def dissolve_group(self, *, group_id: str, tick: int) -> None:
        """Open a session and mark a group as dissolved at the given tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await dissolve_group(session, group_id=group_id, tick=tick)
