"""
Module: knowledge_repository
Layer: graph
Purpose: Neo4j adapter for the belief/knowledge domain. Opens a session per call from the
         injected GraphDB and delegates to belief_queries.find_conflicting_belief and
         knowledge_writer.write_belief, so engines depend on the KnowledgeGraphPort
         abstraction and hold no session. Swap seam for cache/alternate DB/microservice
         backends (DEC-122 / SEV-24).
Does NOT: validate facts, contain engine logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies.get_knowledge_extraction_engine).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.belief_queries import find_conflicting_belief
from npc_engine.graph.db import GraphDB
from npc_engine.graph.knowledge_writer import write_belief


class Neo4jKnowledgeRepository:
    """Session-per-call Neo4j adapter for the belief domain (KnowledgeGraphPort).

    Holds the long-lived GraphDB driver holder and opens one session per operation,
    so it is safe to construct once and inject into belief-learning engines.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def find_conflicting_belief(
        self, *, character_id: str, content: str
    ) -> dict[str, Any] | None:
        """Open a session and return an existing duplicate belief, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await find_conflicting_belief(
                session, character_id=character_id, content=content
            )

    async def write_belief(
        self,
        *,
        npc_id: str,
        content: str,
        confidence: int,
        source_character_id: str,
        learned_at_tick: int,
        game_time_str: str,
        is_deception: bool = False,
        deception_goal_id: str | None = None,
    ) -> str:
        """Open a session and merge a belief node + BELIEVES edge; return the belief id."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await write_belief(
                session,
                npc_id=npc_id,
                content=content,
                confidence=confidence,
                source_character_id=source_character_id,
                learned_at_tick=learned_at_tick,
                game_time_str=game_time_str,
                is_deception=is_deception,
                deception_goal_id=deception_goal_id,
            )
