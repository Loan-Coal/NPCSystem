"""
Module: reputation_event_seeder
Layer: graph
Purpose: Creates a reputation-change Event node and seeds KNOWS_ABOUT edges for
         co-located NPCs so the standing change enters the gossip pipeline.
Does NOT: adjust the HAS_REPUTATION_WITH edge itself (that is reputation_writer's job).
Dependencies injected: AsyncTransaction (via caller).
Used by: npc_engine.graph.reputation.reputation_service
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from neo4j import AsyncTransaction


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPUTATION_EVENT_TYPE: str = "reputation_change"
REPUTATION_EVENT_SEVERITY: int = 50
REPUTATION_EVENT_PRODUCER: str = "reputation_engine"


# ---------------------------------------------------------------------------
# Cypher
# ---------------------------------------------------------------------------

CYPHER_CREATE_REPUTATION_EVENT = """
MERGE (e:Event {id: $id})
SET e.summary = $summary,
    e.severity = $severity,
    e.location_id = $location_id,
    e.occurred_at = $occurred_at,
    e.tick_id = $tick_id,
    e.event_type = $event_type,
    e.is_public = $is_public,
    e.src_character_id = $src_character_id,
    e.faction_id = $faction_id,
    e.reputation_delta = $reputation_delta,
    e.producer = $producer,
    e.last_graph_updated_at = $occurred_at
"""

CYPHER_SEED_REPUTATION_AWARENESS = """
MATCH (c:Character)-[:LOCATED_AT]->(:Location {id: $location_id}), (e:Event {id: $event_id})
WHERE c.is_player = false
    AND c.is_active = true
MERGE (c)-[k:KNOWS_ABOUT]->(e)
SET k.knowledge_state = 'knows',
    k.learned_at_tick = $tick_id,
    k.distortion_type = null,
    k.distortion_level = null,
    k.distorted_summary = null,
    k.source_character_id = null
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def _build_summary(character_id: str, faction_id: str, delta: int) -> str:
    direction = "gained standing with" if delta >= 0 else "lost standing with"
    return f"{character_id} {direction} {faction_id} (delta={delta:+d})"


async def create_reputation_event(
    tx: AsyncTransaction,
    *,
    character_id: str,
    faction_id: str,
    delta: int,
    location_id: str,
    tick_id: int,
) -> str:
    """Create an Event node for a character's faction standing change.

    The event is idempotent on the generated UUID (each call produces a new node).
    Returns the new event_id for downstream KNOWS_ABOUT seeding.

    Args:
        tx: Active Neo4j transaction.
        character_id: Character whose standing changed.
        faction_id: Faction whose standing was affected.
        delta: Signed standing delta (positive = gain, negative = loss).
        location_id: Location where the standing change occurred.
        tick_id: Current game tick.

    Returns:
        The newly created event ID (UUID string).
    """
    event_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    summary = _build_summary(character_id, faction_id, delta)

    await tx.run(
        CYPHER_CREATE_REPUTATION_EVENT,
        id=event_id,
        summary=summary,
        severity=REPUTATION_EVENT_SEVERITY,
        location_id=location_id,
        occurred_at=now,
        tick_id=tick_id,
        event_type=REPUTATION_EVENT_TYPE,
        is_public=True,
        src_character_id=character_id,
        faction_id=faction_id,
        reputation_delta=delta,
        producer=REPUTATION_EVENT_PRODUCER,
    )
    return event_id


async def seed_reputation_awareness(
    tx: AsyncTransaction,
    *,
    event_id: str,
    location_id: str,
    tick_id: int,
) -> None:
    """Seed factual KNOWS_ABOUT edges for all active NPCs at location_id.

    Must be called within an open transaction, after create_reputation_event.
    After this call the standard gossip tick can propagate the event onward.

    Args:
        tx: Active Neo4j transaction.
        event_id: Event node ID returned by create_reputation_event.
        location_id: Location scoping which characters are seeded.
        tick_id: Current game tick recorded on each KNOWS_ABOUT edge.
    """
    await tx.run(
        CYPHER_SEED_REPUTATION_AWARENESS,
        event_id=event_id,
        location_id=location_id,
        tick_id=tick_id,
    )
