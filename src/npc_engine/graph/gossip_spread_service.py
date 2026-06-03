"""
Module: gossip_spread_service
Layer: graph
Purpose: Injects a player-planted rumor as a fabricated Event node with a KNOWS_ABOUT
         edge on the target NPC, entering the normal gossip propagation pipeline.
Does NOT: perform distortion or select gossip pairs — that is handled by the gossip engine.
Dependencies injected: AsyncSession (caller-supplied).
Used by: npc_engine.api.routes.gossip_spread
"""

from __future__ import annotations

from neo4j import AsyncSession

_ORIGIN_PLAYER_RUMOR = "player_rumor"
_KNOWLEDGE_STATE_RUMOR = "rumor"
_SOURCE_PLAYER = "player"

CYPHER_INJECT_RUMOR = """
MERGE (e:Event {id: $event_id})
SET e.summary = $rumor_text,
    e.severity = $severity,
    e.occurred_at = $tick_id,
    e.is_canonical = false,
    e.is_fabricated = true,
    e.origin = $origin
WITH e
MATCH (npc:Character {id: $npc_id})
MERGE (npc)-[k:KNOWS_ABOUT]->(e)
SET k.knowledge_state = $knowledge_state,
    k.distortion_type = null,
    k.distortion_level = 0,
    k.distorted_summary = $rumor_text,
    k.learned_at_tick = $tick_id,
    k.source_character_id = $source_character_id
"""


async def inject_rumor_belief(
    session: AsyncSession,
    target_npc_id: str,
    rumor_text: str,
    severity: int,
    tick_id: int,
) -> str:
    """Create a fabricated Event node and seed a KNOWS_ABOUT edge for target_npc_id.

    The event ID is deterministic: ``rumor_plant_{target_npc_id}_{tick_id}``.
    Multiple calls with the same arguments are idempotent (MERGE).

    After this call the NPC immediately believes the planted content
    (knowledge_state='rumor').  On the next clock advance, the gossip engine
    will propagate and distort it to co-located NPCs via the normal pair-selection
    pipeline.

    Args:
        session: Active Neo4j session.
        target_npc_id: NPC that will immediately know the rumor.
        rumor_text: The fabricated belief text.
        severity: How serious the rumor is (0–100); affects distortion probability
            when the gossip engine picks it up.
        tick_id: Current game tick used for occurred_at and learned_at_tick.

    Returns:
        The deterministic event_id string.
    """
    event_id = f"rumor_plant_{target_npc_id}_{tick_id}"
    await session.run(
        CYPHER_INJECT_RUMOR,
        event_id=event_id,
        rumor_text=rumor_text,
        severity=severity,
        tick_id=tick_id,
        origin=_ORIGIN_PLAYER_RUMOR,
        npc_id=target_npc_id,
        knowledge_state=_KNOWLEDGE_STATE_RUMOR,
        source_character_id=_SOURCE_PLAYER,
    )
    return event_id
