"""
Module: secret_service
Layer: graph
Purpose: Functions for creating Secret nodes and retrieving them for a character.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.secret_queries, common.json_utils, world.time_utils
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.secrets, npc_engine.retrieval.context_builder
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json
from npc_engine.graph.secret_queries import (
    CYPHER_CREATE_SECRET_NODE,
    get_secrets_for_character,
)
from npc_engine.world.time_utils import TimePoint


async def create_secret(
    session: AsyncSession,
    *,
    character_id: str,
    content: str,
    severity: int,
    game_time: TimePoint,
) -> str:
    """Create a Secret node and link it to a Character via a KNOWS_SECRET edge.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character who initially knows the secret.
        content: The secret's textual content.
        severity: Integer severity in the range [0, 100].
        game_time: Game-time snapshot at which the secret was learned.

    Returns:
        Generated UUID string for the new secret node.
    """
    secret_id = str(uuid.uuid4())
    created_at = dump_json(
        {
            "year": game_time.year,
            "season": game_time.season,
            "day": game_time.day,
            "time_of_day": game_time.time_of_day,
        }
    )
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            CYPHER_CREATE_SECRET_NODE,
            secret_id=secret_id,
            content=content,
            severity=severity,
            created_at=created_at,
            character_id=character_id,
        )
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
