"""
Module: secret_service
Layer: graph
Purpose: Functions for creating Secret nodes and retrieving them for a character.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.secret_queries, common.json_utils, world.time_utils
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.secrets, npc_engine.retrieval.context.context_builder
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.secret_queries import (
    CYPHER_CREATE_SECRET_NODE,
    get_secrets_for_character,
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


async def create_secret(
    session: AsyncSession,
    *,
    character_id: str,
    content: str,
    severity: int,
    game_time: TimePoint,
    node_id: str | None = None,
) -> str:
    """Create a Secret node and link it to a Character via a KNOWS_SECRET edge.

    Uses MERGE semantics when node_id is provided; auto-generates a UUID otherwise.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character who initially knows the secret.
        content: The secret's textual content.
        severity: Integer severity in the range [0, 100].
        game_time: Game-time snapshot at which the secret was learned.
        node_id: Optional stable ID for idempotent re-seeding.

    Returns:
        The node ID used (either supplied or generated).
    """
    secret_id = node_id if node_id is not None else str(uuid.uuid4())

    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            CYPHER_CREATE_SECRET_NODE,
            secret_id=secret_id,
            content=content,
            severity=severity,
            created_at=_game_time_json(game_time),
            character_id=character_id,
        )

    await run_in_tx(session, _work)
    return secret_id


async def get_secrets_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Fetch the top-k secrets known by a character, ordered by severity descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of secrets to return.

    Returns:
        List of secret property dicts ordered by severity descending.
    """
    return await get_secrets_for_character(session, character_id=character_id, k=k)


async def delete_secret(
    session: AsyncSession,
    *,
    secret_id: str,
) -> None:
    """Hard-delete a single Secret node and its relationships.

    Args:
        session: Active Neo4j async session.
        secret_id: ID of the Secret node to delete.
    """
    await session.run(
        "MATCH (s:Secret {id: $id}) DETACH DELETE s",
        id=secret_id,
    )
