"""
Module: emotion_repository
Layer: graph
Purpose: Neo4j adapter for the emotion write-through domain. Opens a session per call
         from the injected GraphDB and delegates to EmotionGraphWriter, so EmotionUpdater
         depends on the EmotionGraphPort abstraction and holds no session. Swap seam for
         cache/alternate DB/microservice backends (DEC-122 / SEV-24).
Does NOT: compute emotion values, contain engine logic, call LLMs, or import engines.
Dependencies injected: GraphDB (Neo4j driver holder).
Used by: api composition root (dependencies_stores.get_emotion_updater).
"""

from __future__ import annotations

from npc_engine.graph.db import GraphDB
from npc_engine.graph.emotion_writer import EmotionGraphWriter


class Neo4jEmotionRepository:
    """Session-per-call Neo4j adapter for emotion write-through (EmotionGraphPort).

    Holds the long-lived GraphDB driver holder and opens one session per write, so it
    is safe to construct once as a process singleton and inject into the singleton
    EmotionUpdater.
    """

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder and a stateless writer.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db
        self._writer = EmotionGraphWriter()

    async def write_emotion(
        self,
        *,
        npc_id: str,
        valence: int,
        arousal: int,
        label: str,
        tick: int,
    ) -> None:
        """Open a session and persist an NPC's emotion scalars to its Character node.

        Args:
            npc_id: Unique identifier of the NPC / Character node.
            valence: Emotion valence in range [-100, 100].
            arousal: Emotion arousal in range [0, 100].
            label: Current mood label string.
            tick: Current world-clock tick at which the update occurred.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await self._writer.write_emotion(
                session=session,
                npc_id=npc_id,
                valence=valence,
                arousal=arousal,
                label=label,
                tick=tick,
            )
