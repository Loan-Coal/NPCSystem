"""
Module: investigation_service
Layer: graph
Purpose: Write operations for the Detective/Mystery investigation module.
         Creates Evidence, Deduction nodes and IMPLICATES, PRESENT_AT, SUPPORTED_BY,
         SUSPECTS edges.
Does NOT: read graph state beyond MERGE requirements, call LLMs, or import engine code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.investigation.investigation_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


# ---------------------------------------------------------------------------
# Evidence write operations
# ---------------------------------------------------------------------------

_CYPHER_CREATE_EVIDENCE = """
CREATE (e:Evidence {
    id: $id,
    kind: $kind,
    description: $description,
    discovered_at_tick: $discovered_at_tick,
    discovered_by_character_id: $discovered_by_character_id,
    links_to_event_id: $links_to_event_id,
    confidence: $confidence
})
"""

_CYPHER_CREATE_IMPLICATES = """
MATCH (e:Evidence {id: $evidence_id})
MATCH (c:Character {id: $character_id})
MERGE (e)-[r:IMPLICATES {character_id: $character_id}]->(c)
SET r.weight = $weight, r.is_misleading = $is_misleading
"""

_CYPHER_CREATE_PRESENT_AT = """
MATCH (e:Evidence {id: $evidence_id})
MATCH (l:Location {id: $location_id})
MERGE (e)-[:PRESENT_AT]->(l)
"""


async def create_evidence(
    session: AsyncSession,
    *,
    kind: str,
    description: str,
    discovered_at_tick: int,
    discovered_by_character_id: str,
    links_to_event_id: str | None = None,
    confidence: int = 100,
) -> str:
    """Create an Evidence node and return its ID.

    Args:
        session: Active Neo4j async session.
        kind: Evidence kind — 'physical', 'testimonial', or 'documentary'.
        description: Human-readable description of the evidence.
        discovered_at_tick: Game tick when the evidence was found.
        discovered_by_character_id: ID of the Character who found it.
        links_to_event_id: Optional ID of the Event this evidence relates to.
        confidence: Initial confidence level 0–100.

    Returns:
        ID of the newly created Evidence node.
    """
    evidence_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_EVIDENCE,
        id=evidence_id,
        kind=kind,
        description=description,
        discovered_at_tick=discovered_at_tick,
        discovered_by_character_id=discovered_by_character_id,
        links_to_event_id=links_to_event_id,
        confidence=confidence,
    )
    return evidence_id


async def implicate(
    session: AsyncSession,
    *,
    evidence_id: str,
    character_id: str,
    weight: int,
    is_misleading: bool = False,
) -> None:
    """Create or update an IMPLICATES edge from Evidence to Character.

    Args:
        session: Active Neo4j async session.
        evidence_id: ID of the Evidence node.
        character_id: ID of the implicated Character node.
        weight: Implication strength 0–100.
        is_misleading: True if this implication is a red herring.
    """
    await session.run(
        _CYPHER_CREATE_IMPLICATES,
        evidence_id=evidence_id,
        character_id=character_id,
        weight=weight,
        is_misleading=is_misleading,
    )


async def set_evidence_location(
    session: AsyncSession,
    *,
    evidence_id: str,
    location_id: str,
) -> None:
    """Create a PRESENT_AT edge from Evidence to Location.

    Args:
        session: Active Neo4j async session.
        evidence_id: ID of the Evidence node.
        location_id: ID of the Location node where the evidence was found.
    """
    await session.run(
        _CYPHER_CREATE_PRESENT_AT,
        evidence_id=evidence_id,
        location_id=location_id,
    )


# ---------------------------------------------------------------------------
# Deduction write operations
# ---------------------------------------------------------------------------

_CYPHER_CREATE_DEDUCTION = """
CREATE (d:Deduction {
    id: $id,
    held_by_character_id: $held_by_character_id,
    claim: $claim,
    confidence: $confidence,
    status: $status
})
"""

_CYPHER_CREATE_SUPPORTED_BY = """
MATCH (d:Deduction {id: $deduction_id})
MATCH (e:Evidence {id: $evidence_id})
MERGE (d)-[:SUPPORTED_BY]->(e)
"""

_CYPHER_UPDATE_DEDUCTION_STATUS = """
MATCH (d:Deduction {id: $deduction_id})
SET d.status = $status
"""


async def create_deduction(
    session: AsyncSession,
    *,
    held_by_character_id: str,
    claim: str,
    confidence: int,
    supporting_evidence_ids: list[str] | None = None,
) -> str:
    """Create a Deduction node and SUPPORTED_BY edges to its evidence.

    Args:
        session: Active Neo4j async session.
        held_by_character_id: ID of the Character who formed the deduction.
        claim: The deductive claim text.
        confidence: Confidence in the claim 0–100.
        supporting_evidence_ids: Optional list of Evidence IDs that support this claim.

    Returns:
        ID of the newly created Deduction node.
    """
    deduction_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_DEDUCTION,
        id=deduction_id,
        held_by_character_id=held_by_character_id,
        claim=claim,
        confidence=confidence,
        status="open",
    )
    for evidence_id in (supporting_evidence_ids or []):
        await session.run(
            _CYPHER_CREATE_SUPPORTED_BY,
            deduction_id=deduction_id,
            evidence_id=evidence_id,
        )
    return deduction_id


async def update_deduction_status(
    session: AsyncSession,
    *,
    deduction_id: str,
    status: str,
) -> None:
    """Update the status of a Deduction node.

    Args:
        session: Active Neo4j async session.
        deduction_id: ID of the Deduction node.
        status: New status — 'open', 'confirmed', or 'refuted'.
    """
    await session.run(
        _CYPHER_UPDATE_DEDUCTION_STATUS,
        deduction_id=deduction_id,
        status=status,
    )


# ---------------------------------------------------------------------------
# Suspect write operations
# ---------------------------------------------------------------------------

_CYPHER_RECORD_SUSPECT = """
MATCH (investigator:Character {id: $suspecting_character_id})
MATCH (suspect:Character {id: $suspect_character_id})
MERGE (investigator)-[s:SUSPECTS {event_id: $event_id, suspect_id: $suspect_character_id}]->(suspect)
SET s.confidence = $confidence
"""


async def record_suspect(
    session: AsyncSession,
    *,
    suspecting_character_id: str,
    suspect_character_id: str,
    event_id: str,
    confidence: int,
) -> None:
    """Create or update a SUSPECTS edge from investigator to suspect.

    Args:
        session: Active Neo4j async session.
        suspecting_character_id: ID of the investigator Character.
        suspect_character_id: ID of the suspected Character.
        event_id: ID of the Event being investigated.
        confidence: Suspicion confidence 0–100.
    """
    await session.run(
        _CYPHER_RECORD_SUSPECT,
        suspecting_character_id=suspecting_character_id,
        suspect_character_id=suspect_character_id,
        event_id=event_id,
        confidence=confidence,
    )
