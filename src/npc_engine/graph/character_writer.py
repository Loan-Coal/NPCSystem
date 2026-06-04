"""
character_writer.py - Writes Character nodes to Neo4j.

Does NOT: manage transaction lifecycle.

Dependencies injected: AsyncManagedTransaction.
"""

from typing import Any, Protocol

from neo4j import AsyncManagedTransaction


class _CharacterNode(Protocol):
    """Structural protocol for any node that can be written as a Character."""

    id: str

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]: ...


CYPHER_MERGE_CHARACTER = """
MERGE (c:Character {id: $id})
SET c += $properties,
    c.updated_at = datetime()
"""


async def upsert_character(tx: AsyncManagedTransaction, character: _CharacterNode) -> None:
    """Insert or update a character node idempotently.

    Args:
        tx: Active Neo4j managed transaction used to run the merge query.
        character: Pydantic model with an ``id`` field and serializable character properties.
    """

    await tx.run(
        CYPHER_MERGE_CHARACTER,
        id=character.id,
        properties=character.model_dump(mode="json"),
    )
