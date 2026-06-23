"""
Module: investigation_queries
Layer: graph
Purpose: Read-only Cypher queries for the Detective/Mystery investigation module.
         Returns evidence, deductions, suspects, alibi windows, witnesses, and
         contradicting rumors linked to a crime event.
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.graph.intrigue.investigation_service, npc_engine.engines.investigation.investigation_engine
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


# ---------------------------------------------------------------------------
# Evidence queries
# ---------------------------------------------------------------------------

_CYPHER_EVIDENCE_FOR_EVENT = """
MATCH (ev:Evidence)
WHERE ev.links_to_event_id = $event_id
RETURN properties(ev) AS evidence
"""

_CYPHER_IMPLICATES_FOR_EVIDENCE = """
MATCH (ev:Evidence {id: $evidence_id})-[r:IMPLICATES]->(c:Character)
RETURN properties(c) AS character, r.weight AS weight, r.is_misleading AS is_misleading
"""

_CYPHER_EVIDENCE_AT_LOCATION = """
MATCH (ev:Evidence)-[:PRESENT_AT]->(loc:Location {id: $location_id})
RETURN properties(ev) AS evidence
"""


async def get_evidence_for_event(
    session: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return all Evidence nodes linked to a given event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.

    Returns:
        List of evidence property dicts.
    """
    result = await session.run(_CYPHER_EVIDENCE_FOR_EVENT, event_id=event_id)
    return [dict(r["evidence"]) async for r in result]


async def get_suspects_for_evidence(
    session: AsyncSession,
    evidence_id: str,
) -> list[dict[str, Any]]:
    """Return characters implicated by a specific evidence node.

    Args:
        session: Active Neo4j async session.
        evidence_id: ID of the Evidence node.

    Returns:
        List of dicts with keys: character, weight, is_misleading.
    """
    result = await session.run(_CYPHER_IMPLICATES_FOR_EVIDENCE, evidence_id=evidence_id)
    return [
        {
            "character": dict(r["character"]),
            "weight": r["weight"],
            "is_misleading": r["is_misleading"],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Deduction queries
# ---------------------------------------------------------------------------

_CYPHER_DEDUCTIONS_FOR_CHARACTER = """
MATCH (d:Deduction {held_by_character_id: $character_id})
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(ev:Evidence)
RETURN properties(d) AS deduction, collect(properties(ev)) AS supporting_evidence
"""


async def get_deductions_for_character(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return all Deduction nodes held by an investigator character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the investigator Character node.

    Returns:
        List of dicts with keys: deduction (props), supporting_evidence (list of props).
    """
    result = await session.run(_CYPHER_DEDUCTIONS_FOR_CHARACTER, character_id=character_id)
    return [
        {
            "deduction": dict(r["deduction"]),
            "supporting_evidence": [dict(e) for e in r["supporting_evidence"] if e],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Suspect queries
# ---------------------------------------------------------------------------

_CYPHER_SUSPECTS_FOR_EVENT = """
MATCH (investigator:Character)-[s:SUSPECTS]->(suspect:Character)
WHERE s.event_id = $event_id
RETURN properties(investigator) AS investigator,
       properties(suspect) AS suspect,
       s.confidence AS confidence
"""


async def get_suspects_for_event(
    session: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return all SUSPECTS edges linked to a given event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.

    Returns:
        List of dicts with keys: investigator, suspect, confidence.
    """
    result = await session.run(_CYPHER_SUSPECTS_FOR_EVENT, event_id=event_id)
    return [
        {
            "investigator": dict(r["investigator"]),
            "suspect": dict(r["suspect"]),
            "confidence": r["confidence"],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Alibi queries
# ---------------------------------------------------------------------------

_CYPHER_ALIBI_WINDOW = """
MATCH (c:Character {id: $character_id})-[w:WAS_AT]->(loc:Location)
WHERE w.arrived_at_tick <= $to_tick AND w.departed_at_tick >= $from_tick
RETURN properties(loc) AS location,
       w.arrived_at_tick AS arrived_at_tick,
       w.departed_at_tick AS departed_at_tick,
       w.reason AS reason
ORDER BY w.arrived_at_tick ASC
"""


async def get_alibi_window(
    session: AsyncSession,
    character_id: str,
    from_tick: int,
    to_tick: int,
) -> list[dict[str, Any]]:
    """Return WAS_AT edges for a character covering the given tick window.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        from_tick: Start of the window (inclusive).
        to_tick: End of the window (inclusive).

    Returns:
        List of dicts with keys: location, arrived_at_tick, departed_at_tick, reason.
    """
    result = await session.run(
        _CYPHER_ALIBI_WINDOW,
        character_id=character_id,
        from_tick=from_tick,
        to_tick=to_tick,
    )
    return [
        {
            "location": dict(r["location"]),
            "arrived_at_tick": r["arrived_at_tick"],
            "departed_at_tick": r["departed_at_tick"],
            "reason": r["reason"],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Witness queries
# ---------------------------------------------------------------------------

_CYPHER_WITNESSES_OF_EVENT = """
MATCH (witness:Character)-[w:WITNESSED]->(subject:Character)
WHERE w.event_id = $event_id
RETURN properties(witness) AS witness,
       properties(subject) AS subject,
       w.action_type AS action_type,
       w.witnessed_at_tick AS witnessed_at_tick,
       w.clarity AS clarity,
       w.interpretation AS interpretation
"""


async def get_witnesses_of_event(
    session: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return all WITNESSED edges for a given event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.

    Returns:
        List of dicts with keys: witness, subject, action_type, witnessed_at_tick,
        clarity, interpretation.
    """
    result = await session.run(_CYPHER_WITNESSES_OF_EVENT, event_id=event_id)
    return [
        {
            "witness": dict(r["witness"]),
            "subject": dict(r["subject"]),
            "action_type": r["action_type"],
            "witnessed_at_tick": r["witnessed_at_tick"],
            "clarity": r["clarity"],
            "interpretation": r["interpretation"],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Rumor contradiction queries
# ---------------------------------------------------------------------------

_CYPHER_CONTRADICTING_RUMORS = """
MATCH (r1:Rumor)-[:CONTRADICTS]->(r2:Rumor)
WHERE r1.origin_event_id = $event_id OR r2.origin_event_id = $event_id
RETURN properties(r1) AS rumor_a, properties(r2) AS rumor_b
"""


async def get_contradicting_rumors(
    session: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return pairs of Rumor nodes that CONTRADICTS each other, linked to an event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.

    Returns:
        List of dicts with keys: rumor_a, rumor_b (property dicts of conflicting rumors).
    """
    result = await session.run(_CYPHER_CONTRADICTING_RUMORS, event_id=event_id)
    return [
        {"rumor_a": dict(r["rumor_a"]), "rumor_b": dict(r["rumor_b"])}
        async for r in result
    ]
