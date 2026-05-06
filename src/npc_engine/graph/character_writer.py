"""
character_writer.py - Writes Character nodes to Neo4j.

Does NOT: manage transaction lifecycle.

Dependencies injected: AsyncManagedTransaction.
"""

from neo4j import AsyncManagedTransaction
from pydantic import BaseModel


CYPHER_MERGE_CHARACTER = """
MERGE (c:Character {id: $id})
SET c += $properties,
    c.updated_at = datetime()
"""


async def upsert_character(tx: AsyncManagedTransaction, character: BaseModel) -> None:
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
