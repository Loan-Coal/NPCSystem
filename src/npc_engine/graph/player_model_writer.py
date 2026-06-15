"""
Module: player_model_writer
Layer: graph
Purpose: Upserts and reads PlayerModel nodes in Neo4j via MERGE on (npc_id, player_id),
         and maintains the HAS_PLAYER_MODEL edge from the Character node.
Does NOT: derive perceived_trust/intent, call LLMs, import from engine layer,
          or manage transaction lifecycle beyond what callers provide.
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
Used by: (slice 2) engines/player_model tick handler.
"""

from __future__ import annotations

from neo4j import AsyncSession, AsyncTransaction
from pydantic import BaseModel

from npc_engine.graph.transaction_coordinator import run_in_tx

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

_CYPHER_UPSERT_PLAYER_MODEL = """
MERGE (pm:PlayerModel {npc_id: $npc_id, player_id: $player_id})
ON CREATE SET pm.id = $pm_id,
              pm.npc_id = $npc_id,
              pm.player_id = $player_id
SET pm.perceived_trust = $perceived_trust,
    pm.perceived_intent = $perceived_intent,
    pm.last_updated_at = $last_updated_at
WITH pm
MATCH (c:Character {id: $npc_id})
MERGE (c)-[:HAS_PLAYER_MODEL]->(pm)
"""

_CYPHER_GET_PLAYER_MODEL = """
MATCH (c:Character {id: $npc_id})-[:HAS_PLAYER_MODEL]->(pm:PlayerModel {player_id: $player_id})
RETURN pm.id, pm.npc_id, pm.player_id,
       pm.perceived_trust, pm.perceived_intent, pm.last_updated_at
"""


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


class PlayerModelRecord(BaseModel):
    """Graph record returned by get_player_model.

    Attributes:
        id: Stable node ID (npc_id + '__' + player_id).
        npc_id: NPC that owns this model.
        player_id: Player being modelled.
        perceived_trust: NPC's perceived trust in the player (0–100), if set.
        perceived_intent: NPC's perceived intent label, if set.
        last_updated_at: Game tick string when last updated, if set.
    """

    id: str
    npc_id: str
    player_id: str
    perceived_trust: int | None = None
    perceived_intent: str | None = None
    last_updated_at: str | None = None


# ---------------------------------------------------------------------------
# Write function
# ---------------------------------------------------------------------------


async def upsert_player_model(
    session: AsyncSession,
    npc_id: str,
    player_id: str,
    perceived_trust: int,
    perceived_intent: str,
    tick: int,
) -> None:
    """Upsert a PlayerModel node and attach the HAS_PLAYER_MODEL edge.

    Uses MERGE keyed on (npc_id, player_id) so the operation is idempotent.
    The write runs inside a single transaction owned by the graph transaction
    coordinator (``run_in_tx``); callers pass a session, never a transaction.

    Args:
        session: Active Neo4j async session the coordinator opens a transaction on.
        npc_id: NPC that owns this player model.
        player_id: Player being modelled.
        perceived_trust: Derived trust score in range [0, 100].
        perceived_intent: Derived intent classification string.
        tick: Current game tick (stored as string in last_updated_at).

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query execution failure.
    """
    pm_id = f"{npc_id}__{player_id}"

    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            _CYPHER_UPSERT_PLAYER_MODEL,
            pm_id=pm_id,
            npc_id=npc_id,
            player_id=player_id,
            perceived_trust=perceived_trust,
            perceived_intent=perceived_intent,
            last_updated_at=str(tick),
        )

    await run_in_tx(session, _work)


# ---------------------------------------------------------------------------
# Read function
# ---------------------------------------------------------------------------


async def get_player_model(
    session: AsyncSession,
    npc_id: str,
    player_id: str,
) -> PlayerModelRecord | None:
    """Fetch an NPC's PlayerModel for a given player.

    Returns None if no HAS_PLAYER_MODEL edge and PlayerModel node exist.

    Args:
        session: Active Neo4j async session.
        npc_id: NPC whose model to retrieve.
        player_id: Player whose model to retrieve.

    Returns:
        PlayerModelRecord if found, None otherwise.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query execution failure.
    """
    result = await session.run(
        _CYPHER_GET_PLAYER_MODEL,
        npc_id=npc_id,
        player_id=player_id,
    )
    record = await result.single()
    if record is None:
        return None
    data = record.data()
    return PlayerModelRecord(
        id=data["pm.id"],
        npc_id=data["pm.npc_id"],
        player_id=data["pm.player_id"],
        perceived_trust=data.get("pm.perceived_trust"),
        perceived_intent=data.get("pm.perceived_intent"),
        last_updated_at=data.get("pm.last_updated_at"),
    )
