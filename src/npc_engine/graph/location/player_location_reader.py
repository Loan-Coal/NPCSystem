"""
Module: player_location_reader
Layer: graph
Purpose: Read-only Cypher accessors for player/NPC co-location queries via LOCATED_AT edges.
Does NOT: write to the graph or run non-LOCATED_AT queries.
Dependencies: neo4j.AsyncSession
Dependencies injected: AsyncSession (per call — no constructor args required).
Used by: engines.proactive_dialogue.proactive_tick_adapter
"""

from __future__ import annotations

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

# Returns the tick at which the player arrived at the NPC's location.
# arrived_at_tick is optional on the LOCATED_AT edge (required: false in schema).
CYPHER_PLAYER_ARRIVED_TICK = """
MATCH (player:Character {is_player: true, id: $player_id})-[r:LOCATED_AT]->(loc:Location)
      <-[:LOCATED_AT]-(npc:Character {id: $npc_id})
RETURN coalesce(r.arrived_at_tick, $tick_id) AS arrived_at_tick
LIMIT 1
"""

# Returns all (npc_id, player_id) pairs that share the same location node.
CYPHER_COLLOCATED_PAIRS = """
MATCH (npc:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(player:Character)
WHERE npc.is_player = false
  AND player.is_player = true
  AND npc.is_active = true
RETURN npc.id AS npc_id, player.id AS player_id
"""


class PlayerLocationReader:
    """Read-only graph accessor for player/NPC co-location state.

    Implements LocationServiceProtocol — stateless, no constructor dependencies.
    """

    async def get_player_idle_ticks(
        self,
        session: AsyncSession,
        *,
        npc_id: str,
        player_id: str,
        tick_id: int,
    ) -> int:
        """Return the number of ticks the player has been idle at the NPC's location.

        Computes idle ticks as: tick_id - arrived_at_tick.
        Returns 0 if the player is not co-located with the NPC, or if the
        LOCATED_AT edge has no arrived_at_tick property.

        Args:
            session: Active Neo4j async session.
            npc_id: NPC whose location is the reference point.
            player_id: Player whose arrival tick is checked.
            tick_id: Current game tick.

        Returns:
            Integer idle tick count, minimum 0.
        """
        result = await session.run(
            CYPHER_PLAYER_ARRIVED_TICK,
            player_id=player_id,
            npc_id=npc_id,
            tick_id=tick_id,
        )
        try:
            record = await result.single()
        finally:
            await result.consume()

        if record is None:
            return 0
        arrived_at: int = int(record["arrived_at_tick"])
        return max(0, tick_id - arrived_at)

    async def get_collocated_pairs(
        self,
        session: AsyncSession,
    ) -> list[tuple[str, str]]:
        """Return all (npc_id, player_id) pairs currently at the same location.

        Args:
            session: Active Neo4j async session.

        Returns:
            List of (npc_id, player_id) tuples for all co-located NPC/player pairs.
        """
        result = await session.run(CYPHER_COLLOCATED_PAIRS)
        try:
            pairs: list[tuple[str, str]] = [
                (record["npc_id"], record["player_id"])
                async for record in result
            ]
        finally:
            await result.consume()
        return pairs
