"""
Module: intent_queries
Layer: graph
Purpose: Cypher queries for intent formation — reads NPC/player locations, unmet
         needs, witnessed events, and unresolved goals for scoring; and all
         PendingIntent queue operations for the intent queue writer/reader.
Does NOT: score or filter intents; does not call LLMs.
Dependencies injected: AsyncSession (caller-managed).
Used by: engines.agenda.conversation_intent_service,
         graph.intent_queue_writer, graph.intent_queue_reader

300-LINE WAIVER: a flat catalog of cohesive Cypher query strings + their thin
runners; splitting fragments the query catalog with no encapsulation gain.
See DEC-140 (ISSUE-053 baseline catalog).
"""
from __future__ import annotations

from typing import Any
from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# S14.1 — location and trigger-source queries
# ---------------------------------------------------------------------------

_CYPHER_NPC_LOCATION = """
MATCH (c:Character {id: $character_id})-[:LOCATED_AT]->(l:Location)
RETURN l.id AS location_id
LIMIT 1
"""

_CYPHER_PLAYER_LOCATION = """
MATCH (c:Character {id: $player_id})-[:LOCATED_AT]->(l:Location)
RETURN l.id AS location_id
LIMIT 1
"""

_CYPHER_UNMET_NEEDS = """
MATCH (c:Character {id: $npc_id})-[:NEEDS]->(n:Need)
RETURN n.id AS id, n.kind AS kind, n.level AS level,
       n.decay_rate AS decay_rate, n.character_id AS character_id
"""

_CYPHER_WITNESSED_EVENTS = """
MATCH (c:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event)
WHERE k.learned_at_tick >= $since_tick
RETURN e.id AS id, e.summary AS summary, k.learned_at_tick AS learned_at_tick
"""

_CYPHER_UNRESOLVED_GOALS = """
MATCH (c:Character {id: $npc_id})-[:PURSUES]->(g:Goal)
WHERE g.status <> 'complete'
RETURN g.id AS id, g.description AS description, g.urgency AS urgency, g.status AS status
"""

# ---------------------------------------------------------------------------
# S14.2 — PendingIntent queue operations (added in S14.2 implementation step)
# ---------------------------------------------------------------------------

_CYPHER_COUNT_NPC_PENDING = """
MATCH (pi:PendingIntent {npc_id: $npc_id, status: 'pending'})
RETURN count(pi) AS cnt
"""

_CYPHER_LOWEST_SCORE_PENDING = """
MATCH (pi:PendingIntent {npc_id: $npc_id, status: 'pending'})
RETURN pi.id AS id, pi.score AS score
ORDER BY pi.score ASC
LIMIT 1
"""

_CYPHER_DELETE_INTENT_BY_ID = """
MATCH (pi:PendingIntent {id: $intent_id})
DELETE pi
"""

_CYPHER_MERGE_PENDING_INTENT = """
MERGE (pi:PendingIntent {id: $id})
ON CREATE SET
    pi.npc_id        = $npc_id,
    pi.player_id     = $player_id,
    pi.tick          = $tick,
    pi.score         = $score,
    pi.reason        = $reason,
    pi.trigger_type  = $trigger_type,
    pi.trigger_ref   = $trigger_ref,
    pi.status        = 'pending',
    pi.created_tick  = $created_tick
"""

_CYPHER_GET_PENDING_FOR_PLAYER = """
MATCH (pi:PendingIntent {player_id: $player_id, status: 'pending'})
RETURN pi.id AS id, pi.npc_id AS npc_id, pi.player_id AS player_id,
       pi.tick AS tick, pi.score AS score, pi.reason AS reason,
       pi.trigger_type AS trigger_type, pi.trigger_ref AS trigger_ref,
       pi.created_tick AS created_tick
ORDER BY pi.score DESC
LIMIT $limit
"""

_CYPHER_MARK_DELIVERED = """
MATCH (pi:PendingIntent {id: $intent_id})
SET pi.status = 'delivered'
"""

_CYPHER_EXPIRE_STALE = """
MATCH (pi:PendingIntent {status: 'pending'})
WHERE pi.created_tick < $cutoff_tick
SET pi.status = 'expired'
RETURN count(pi) AS cnt
"""


# ---------------------------------------------------------------------------
# S14.1 query functions
# ---------------------------------------------------------------------------


async def get_npc_location(session: AsyncSession, npc_id: str) -> str | None:
    """Return the current location id of the NPC, or None if not located.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.

    Returns:
        Location node ID string, or None if no LOCATED_AT edge exists.
    """
    result = await session.run(_CYPHER_NPC_LOCATION, character_id=npc_id)
    try:
        record = await result.single()
    finally:
        await result.consume()
    return str(record["location_id"]) if record is not None else None


async def get_player_location(session: AsyncSession, player_id: str) -> str | None:
    """Return the current location id of the player, or None if not located.

    Args:
        session: Active Neo4j async session.
        player_id: Character node ID of the player.

    Returns:
        Location node ID string, or None if no LOCATED_AT edge exists.
    """
    result = await session.run(_CYPHER_PLAYER_LOCATION, player_id=player_id)
    try:
        record = await result.single()
    finally:
        await result.consume()
    return str(record["location_id"]) if record is not None else None


async def get_unmet_needs(session: AsyncSession, npc_id: str) -> list[dict[str, Any]]:
    """Return all Need nodes connected to the NPC via NEEDS edges.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.

    Returns:
        List of dicts with keys: id, kind, level, decay_rate, character_id.
    """
    result = await session.run(_CYPHER_UNMET_NEEDS, npc_id=npc_id)
    try:
        records = [dict(r) async for r in result]
    finally:
        await result.consume()
    return records


async def get_witnessed_events(
    session: AsyncSession, npc_id: str, since_tick: int
) -> list[dict[str, Any]]:
    """Return Event nodes the NPC KNOWS_ABOUT since since_tick.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.
        since_tick: Minimum tick at which the event was learned (inclusive).

    Returns:
        List of dicts with keys: id, summary, learned_at_tick.
    """
    result = await session.run(_CYPHER_WITNESSED_EVENTS, npc_id=npc_id, since_tick=since_tick)
    try:
        records = [dict(r) async for r in result]
    finally:
        await result.consume()
    return records


async def get_unresolved_goals(session: AsyncSession, npc_id: str) -> list[dict[str, Any]]:
    """Return Goal nodes the NPC PURSUES where status != 'complete'.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.

    Returns:
        List of dicts with keys: id, description, urgency, status.
    """
    result = await session.run(_CYPHER_UNRESOLVED_GOALS, npc_id=npc_id)
    try:
        records = [dict(r) async for r in result]
    finally:
        await result.consume()
    return records


# ---------------------------------------------------------------------------
# S14.2 queue query functions
# ---------------------------------------------------------------------------


async def count_npc_pending_intents(session: AsyncSession, npc_id: str) -> int:
    """Return count of PendingIntent nodes for npc_id with status='pending'.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.

    Returns:
        Integer count of pending intents.
    """
    result = await session.run(_CYPHER_COUNT_NPC_PENDING, npc_id=npc_id)
    try:
        record = await result.single()
    finally:
        await result.consume()
    return int(record["cnt"]) if record is not None else 0


async def get_lowest_score_pending(session: AsyncSession, npc_id: str) -> dict[str, Any] | None:
    """Return the lowest-score pending intent for npc_id, or None.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.

    Returns:
        Dict with keys id, score, or None if no pending intents exist.
    """
    result = await session.run(_CYPHER_LOWEST_SCORE_PENDING, npc_id=npc_id)
    try:
        record = await result.single()
    finally:
        await result.consume()
    return dict(record) if record is not None else None


async def delete_intent_by_id(session: AsyncSession, intent_id: str) -> None:
    """Delete a PendingIntent node by its id.

    Args:
        session: Active Neo4j async session.
        intent_id: Unique intent id to delete.
    """
    result = await session.run(_CYPHER_DELETE_INTENT_BY_ID, intent_id=intent_id)
    await result.consume()


async def merge_pending_intent(session: AsyncSession, *, id: str, npc_id: str,
                               player_id: str, tick: int, score: float,
                               reason: str, trigger_type: str,
                               trigger_ref: str, created_tick: int) -> None:
    """MERGE a PendingIntent node; no-op if it already exists (dedup on id).

    Args:
        session: Active Neo4j async session.
        id: Unique intent id (npc_id:player_id:tick:trigger_type).
        npc_id: NPC character id.
        player_id: Player character id.
        tick: Game tick the intent was formed.
        score: Intent urgency score.
        reason: Human-readable trigger phrase.
        trigger_type: One of need, event, goal.
        trigger_ref: ID of the triggering node.
        created_tick: Tick at which intent was enqueued (same as tick).
    """
    result = await session.run(
        _CYPHER_MERGE_PENDING_INTENT,
        id=id, npc_id=npc_id, player_id=player_id, tick=tick,
        score=score, reason=reason, trigger_type=trigger_type,
        trigger_ref=trigger_ref, created_tick=created_tick,
    )
    await result.consume()


async def get_pending_for_player(
    session: AsyncSession, player_id: str, limit: int
) -> list[dict[str, Any]]:
    """Return pending intents for player ordered by score DESC.

    Args:
        session: Active Neo4j async session.
        player_id: Player character id.
        limit: Maximum number of intents to return.

    Returns:
        List of dicts with all ConversationIntent fields plus id, created_tick.
    """
    result = await session.run(
        _CYPHER_GET_PENDING_FOR_PLAYER, player_id=player_id, limit=limit
    )
    try:
        records = [dict(r) async for r in result]
    finally:
        await result.consume()
    return records


async def mark_intent_delivered(session: AsyncSession, intent_id: str) -> None:
    """Set status='delivered' on the PendingIntent with the given id.

    Args:
        session: Active Neo4j async session.
        intent_id: Unique intent id to mark delivered.
    """
    result = await session.run(_CYPHER_MARK_DELIVERED, intent_id=intent_id)
    await result.consume()


async def expire_stale_intents(session: AsyncSession, cutoff_tick: int) -> int:
    """Set status='expired' on all pending intents older than cutoff_tick.

    Args:
        session: Active Neo4j async session.
        cutoff_tick: Intents with created_tick < cutoff_tick are expired.

    Returns:
        Count of intents expired.
    """
    result = await session.run(_CYPHER_EXPIRE_STALE, cutoff_tick=cutoff_tick)
    try:
        record = await result.single()
    finally:
        await result.consume()
    return int(record["cnt"]) if record is not None else 0
