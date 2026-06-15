"""
Module: political_repository
Layer: graph
Purpose: Neo4j adapter for the political graph domain. Opens a session per operation
         from the injected GraphDB and delegates to political_queries and the political
         writers, so the political engines depend on the abstraction and hold no session.
         Swap seam for cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: decide succession/agendas, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_advanced.politics.get_succession_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.political_queries import (
    get_heirs_for_character,
    get_vacant_inheritable_titles,
)
from npc_engine.graph.political_title_writer import grant_title


class Neo4jPoliticalRepository:
    """Session-per-call Neo4j adapter for the political domain (PoliticalGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_vacant_inheritable_titles(self) -> list[dict[str, Any]]:
        """Open a session and return inheritable titles with no current holder."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_vacant_inheritable_titles(session)

    async def get_heirs_for_character(self, *, character_id: str) -> list[dict[str, Any]]:
        """Open a session and return ordered heirs for a character."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_heirs_for_character(session, character_id=character_id)

    async def grant_title(self, *, character_id: str, title_id: str, tick: int) -> None:
        """Open a session and grant a title to a character at the given tick."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await grant_title(session, character_id=character_id, title_id=title_id, tick=tick)
