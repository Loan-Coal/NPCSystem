"""
event_writer.py - Writes Event nodes and participation edges to Neo4j.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: orchestrate event generation logic.

Dependencies injected: AsyncManagedTransaction.
"""
from __future__ import annotations

from typing import Any, Protocol

from neo4j import AsyncTransaction

from npc_engine.graph.json_fields import serialize_provenance_field
from npc_engine.utils.errors import QuestProvenanceError


class _EventNode(Protocol):
    """Structural protocol for any Pydantic event node written via this module."""

    id: str
    producer: str | None
    origin_engine: str | None
    schema_version: str | None
    provenance: dict[str, Any] | None

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]: ...


CYPHER_MERGE_EVENT = """
MERGE (e:Event {id: $id})
SET e += $properties
"""


async def upsert_event(tx: AsyncTransaction, event: _EventNode) -> None:
    """Insert or update an event node idempotently.

    Args:
        tx: Active Neo4j transaction used to run the merge query.
        event: Pydantic model with an ``id`` field and serializable event properties.
    """

    properties = serialize_provenance_field(event.model_dump(mode="json"))

    await tx.run(
        CYPHER_MERGE_EVENT,
        id=event.id,
        properties=properties,
    )


def ensure_quest_event_provenance(*, event: _EventNode) -> None:
    """Ensure quest lifecycle events include required provenance metadata.

    Args:
        event: Pydantic model representing the quest lifecycle event to validate.

    Raises:
        QuestProvenanceError: If any required top-level or provenance fields are absent or blank.
    """

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


async def upsert_quest_lifecycle_event(*, tx: AsyncTransaction, event: _EventNode) -> None:
    """Persist one quest lifecycle event after provenance validation.

    Args:
        tx: Active Neo4j transaction used to run the merge query.
        event: Pydantic model representing the quest lifecycle event to persist.

    Raises:
        QuestProvenanceError: If required provenance metadata is absent or blank.
    """

    ensure_quest_event_provenance(event=event)
    await upsert_event(tx=tx, event=event)
