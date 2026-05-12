"""
knowledge_propagator.py - Writes gossip knowledge propagation edges.

Does NOT: choose which pairs gossip.

Dependencies injected: AsyncSession.
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.gossip.gossip_distort import GossipDistortion


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
    """Propagate one event to a receiver by merging a KNOWS_ABOUT edge.

    Sets ``knowledge_state`` to ``"knows"`` when no distortion occurred, or
    ``"rumor"`` when a distortion type is present.

    Args:
        session: Active Neo4j async session.
        receiver_id: Character node ID receiving the knowledge.
        source_character_id: Character node ID sharing the knowledge.
        event_id: Event node ID being propagated.
        tick_id: Current game tick recorded on the edge.
        distortion: Distortion payload determining knowledge state and summary.
    """

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


CYPHER_PROPAGATE_SECRET = """
MATCH (receiver:Character {id: $receiver_id}), (secret:Secret {id: $secret_id})
MERGE (receiver)-[k:KNOWS_SECRET]->(secret)
SET k.knowledge_state = $knowledge_state,
    k.learned_at_tick = $tick_id,
    k.source_character_id = $source_character_id
"""

# Secrets propagate with lower base probability and higher distortion chance
# than standard events. These constants are used by gossip_handler.
SECRET_BASE_PROBABILITY: float = 0.2
SECRET_DISTORTION_CHANCE: float = 0.5


async def propagate_secret(
    session: AsyncSession,
    receiver_id: str,
    secret_id: str,
    source_character_id: str,
    tick_id: int,
    distorted: bool = False,
) -> None:
    """Propagate a secret to a receiver by merging a KNOWS_SECRET edge.

    Sets ``knowledge_state`` to ``"knows"`` or ``"rumor"`` based on distortion.
    Secrets are more sensitive than events: use SECRET_BASE_PROBABILITY and
    SECRET_DISTORTION_CHANCE from this module when deciding whether to call this.

    Args:
        session: Active Neo4j async session.
        receiver_id: Character node ID receiving the secret.
        secret_id: Secret node ID being propagated.
        source_character_id: Character node ID sharing the secret.
        tick_id: Current game tick recorded on the edge.
        distorted: When True the edge is marked as a rumor rather than direct knowledge.
    """
    knowledge_state = "rumor" if distorted else "knows"
    await session.run(
        CYPHER_PROPAGATE_SECRET,
        receiver_id=receiver_id,
        secret_id=secret_id,
        knowledge_state=knowledge_state,
        tick_id=tick_id,
        source_character_id=source_character_id,
    )
