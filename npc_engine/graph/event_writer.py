"""
event_writer.py - Writes Event nodes and participation edges to Neo4j.

Does NOT: orchestrate event generation logic.

Dependencies injected: AsyncManagedTransaction.
"""

from neo4j import AsyncTransaction

from graph.node_schemas import EventNode


CYPHER_MERGE_EVENT = """
MERGE (e:Event {id: $id})
SET e += $properties
"""


async def upsert_event(tx: AsyncTransaction, event: EventNode) -> None:
    """Insert or update an event node idempotently."""

    await tx.run(
        CYPHER_MERGE_EVENT,
        id=event.id,
        properties=event.model_dump(mode="json"),
    )
