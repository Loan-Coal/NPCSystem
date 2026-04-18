"""
awareness_seeder.py - Seeds factual KNOWS_ABOUT edges for affected NPCs.

Does NOT: choose event templates.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncTransaction


CYPHER_SEED_AWARENESS = """
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
async def seed_awareness_tx(tx: AsyncTransaction, event_id: str, location_id: str, tick_id: int) -> None:
    """Mark all NPCs at location as knowing the event within a transaction."""

    await tx.run(CYPHER_SEED_AWARENESS, event_id=event_id, location_id=location_id, tick_id=tick_id)
