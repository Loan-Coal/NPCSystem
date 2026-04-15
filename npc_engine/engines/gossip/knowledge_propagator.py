"""
knowledge_propagator.py - Writes gossip knowledge propagation edges.

Does NOT: choose which pairs gossip.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession

from graph.edge_schemas import GossipDistortion


CYPHER_PROPAGATE_KNOWLEDGE = """
MATCH (receiver:Character {id: $receiver_id}), (event:Event {id: $event_id})
MERGE (receiver)-[k:KNOWS_ABOUT]->(event)
SET k.knowledge_state = $knowledge_state,
    k.distortion_type = $distortion_type,
    k.distortion_level = $distortion_level,
    k.distorted_summary = $distorted_summary,
    k.learned_at_tick = $tick_id,
    k.source_character_id = $source_character_id
"""


async def propagate(
    session: AsyncSession,
    receiver_id: str,
    source_character_id: str,
    event_id: str,
    tick_id: int,
    distortion: GossipDistortion,
) -> None:
    """Propagate one event summary to receiver as rumor/knowledge edge."""

    knowledge_state = "knows" if distortion.distortion_type is None else "rumor"
    await session.run(
        CYPHER_PROPAGATE_KNOWLEDGE,
        receiver_id=receiver_id,
        event_id=event_id,
        knowledge_state=knowledge_state,
        distortion_type=distortion.distortion_type,
        distortion_level=distortion.distortion_level,
        distorted_summary=distortion.summary,
        tick_id=tick_id,
        source_character_id=source_character_id,
    )
