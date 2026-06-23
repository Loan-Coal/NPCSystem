"""
Module: emotion_bootstrap_repository
Layer: graph
Purpose: Neo4j adapter for the EmotionBootstrapGraphPort. Opens a session per call
         from the injected GraphDB and delegates to graph/emotion_reader.get_emotion_fields,
         so EmotionBootstrapper holds no AsyncSession at startup (DEC-122 / SEV-24).
Does NOT: compute emotion arithmetic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: main.py lifespan (startup wiring).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.db import GraphDB
from npc_engine.graph.emotion.emotion_reader import get_emotion_fields


class Neo4jEmotionBootstrapRepository:
    """Session-per-call Neo4j adapter for reading emotion fields at startup."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Initialise with a GraphDB holder.

        Args:
            graph_db: Connected (or connectable) Neo4j driver holder.
        """
        self._graph_db = graph_db

    async def get_emotion_fields(self, npc_id: str) -> dict[str, Any] | None:
        """Return the emotion fields stored on the character node, or None.

        Args:
            npc_id: NPC character ID.

        Returns:
            Dict with emotion field keys (values may be None), or None when the
            character node does not exist.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_emotion_fields(session, npc_id)
