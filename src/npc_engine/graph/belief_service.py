"""
Module: belief_service
Layer: graph
Purpose: Functions for creating Belief nodes, retrieving them, and updating confidence.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.belief_queries, common.json_utils, world.time_utils
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.beliefs, npc_engine.retrieval.context_builder
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.belief_queries import (
    CYPHER_CREATE_BELIEF,
    CYPHER_UPDATE_CONFIDENCE,
    get_beliefs_for_character,
)
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.world.time_utils import TimePoint


def _game_time_json(game_time: TimePoint) -> str:
    """Serialise a TimePoint to the JSON string expected by Cypher params."""
    return dump_json({
        "year": game_time.year,
        "season": game_time.season,
        "day": game_time.day,
        "time_of_day": game_time.time_of_day,
    })


async def create_belief(
    session: AsyncSession,
    *,
    character_id: str,
    content: str,
    confidence: int,
    game_time: TimePoint,
    node_id: str | None = None,
) -> str:
    """Create a Belief node and link it to a Character via a BELIEVES edge.

    Uses MERGE semantics when node_id is provided; auto-generates a UUID otherwise.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node holding the belief.
        content: Freeform text describing the belief.
        confidence: Initial confidence level (0–100).
        game_time: Game-time snapshot at which the belief was formed.
        node_id: Optional stable ID for idempotent re-seeding.

    Returns:
        The node ID used (either supplied or generated).
    """
    belief_id = node_id if node_id is not None else str(uuid.uuid4())

    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            CYPHER_CREATE_BELIEF,
            belief_id=belief_id,
            content=content,
            confidence=confidence,
            created_at_game_time=_game_time_json(game_time),
            character_id=character_id,
        )

    await run_in_tx(session, _work)
    return belief_id


async def get_beliefs_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Fetch top-k beliefs for a character ordered by confidence descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of beliefs to return.

    Returns:
        List of belief property dicts sorted by confidence descending.
    """
    return await get_beliefs_for_character(session, character_id=character_id, k=k)


async def update_confidence(
    session: AsyncSession,
    *,
    belief_id: str,
    new_confidence: int,
) -> None:
    """Update the confidence level of an existing Belief node.

    Args:
        session: Active Neo4j async session.
        belief_id: ID of the Belief node to update.
        new_confidence: Replacement confidence value (0–100).
    """
    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            CYPHER_UPDATE_CONFIDENCE,
            belief_id=belief_id,
            confidence=new_confidence,
        )

    await run_in_tx(session, _work)


async def delete_belief(
    session: AsyncSession,
    *,
    belief_id: str,
) -> None:
    """Hard-delete a single Belief node and its relationships.

    Args:
        session: Active Neo4j async session.
        belief_id: ID of the Belief node to delete.
    """
    await session.run(
        "MATCH (b:Belief {id: $id}) DETACH DELETE b",
        id=belief_id,
    )
