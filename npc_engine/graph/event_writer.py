"""
event_writer.py - Writes Event nodes and participation edges to Neo4j.

Does NOT: orchestrate event generation logic.

Dependencies injected: AsyncManagedTransaction.
"""

import json

from neo4j import AsyncTransaction

from graph.node_schemas import EventNode
from utils.errors import QuestProvenanceError


CYPHER_MERGE_EVENT = """
MERGE (e:Event {id: $id})
SET e += $properties
"""


async def upsert_event(tx: AsyncTransaction, event: EventNode) -> None:
    """Insert or update an event node idempotently."""

    properties = event.model_dump(mode="json")
    provenance = properties.get("provenance")
    if isinstance(provenance, dict):
        properties["provenance"] = json.dumps(provenance, sort_keys=True)

    await tx.run(
        CYPHER_MERGE_EVENT,
        id=event.id,
        properties=properties,
    )


def ensure_quest_event_provenance(*, event: EventNode) -> None:
    """Ensure quest lifecycle events include required provenance metadata."""

    required_top_level = {
        "producer": event.producer,
        "origin_engine": event.origin_engine,
        "schema_version": event.schema_version,
    }
    missing_top_level = [name for name, value in required_top_level.items() if value is None or value.strip() == ""]

    provenance = event.provenance or {}
    required_provenance_keys = [
        "request_id",
        "idempotency_key",
        "idempotency_request_hash",
        "actor_id",
        "reason",
    ]
    missing_provenance: list[str] = []
    for key in required_provenance_keys:
        value = provenance.get(key)
        if value is None:
            missing_provenance.append(key)
            continue
        if str(value).strip() == "":
            missing_provenance.append(key)

    if missing_top_level or missing_provenance:
        missing = [*missing_top_level, *[f"provenance.{key}" for key in missing_provenance]]
        raise QuestProvenanceError(detail=f"missing quest event provenance fields: {', '.join(missing)}")


async def upsert_quest_lifecycle_event(*, tx: AsyncTransaction, event: EventNode) -> None:
    """Persist one quest lifecycle event after provenance validation."""

    ensure_quest_event_provenance(event=event)
    await upsert_event(tx=tx, event=event)
