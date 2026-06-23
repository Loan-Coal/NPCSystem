"""
Module: political_agenda_writer
Layer: graph
Purpose: Write operations for Agenda nodes and SUPPORTS_AGENDA / OPPOSES_AGENDA edges.
Does NOT: call LLMs or tally votes (tallying is in the engine layer).
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.agenda.agenda_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


_CYPHER_CREATE_AGENDA = """
CREATE (a:Agenda {
    id: $id,
    description: $description,
    proposed_by_faction_id: $proposed_by_faction_id,
    status: $status,
    deadline_tick: $deadline_tick
})
"""

_CYPHER_SET_AGENDA_STATUS = """
MATCH (a:Agenda {id: $agenda_id})
SET a.status = $status
"""

_CYPHER_VOTE_SUPPORTS = """
MATCH (c:Character {id: $character_id})
MATCH (a:Agenda {id: $agenda_id})
MERGE (c)-[v:SUPPORTS_AGENDA {agenda_id: $agenda_id}]->(a)
SET v.weight = $weight
"""

_CYPHER_VOTE_OPPOSES = """
MATCH (c:Character {id: $character_id})
MATCH (a:Agenda {id: $agenda_id})
MERGE (c)-[v:OPPOSES_AGENDA {agenda_id: $agenda_id}]->(a)
SET v.weight = $weight
"""


async def create_agenda(
    session: AsyncSession,
    *,
    description: str,
    proposed_by_faction_id: str,
    deadline_tick: int | None = None,
) -> str:
    """Create an Agenda node with status='open' and return its ID.

    Args:
        session: Active Neo4j async session.
        description: Human-readable agenda description.
        proposed_by_faction_id: ID of the proposing Faction node.
        deadline_tick: Optional tick at which the agenda must be resolved.

    Returns:
        ID of the newly created Agenda node.
    """
    agenda_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_AGENDA,
        id=agenda_id,
        description=description,
        proposed_by_faction_id=proposed_by_faction_id,
        status="open",
        deadline_tick=deadline_tick,
    )
    return agenda_id


async def set_agenda_status(
    session: AsyncSession,
    *,
    agenda_id: str,
    status: str,
) -> None:
    """Update the status of an Agenda node.

    Args:
        session: Active Neo4j async session.
        agenda_id: ID of the Agenda node.
        status: New status — 'open', 'passed', or 'failed'.
    """
    await session.run(_CYPHER_SET_AGENDA_STATUS, agenda_id=agenda_id, status=status)


async def vote_on_agenda(
    session: AsyncSession,
    *,
    character_id: str,
    agenda_id: str,
    weight: int,
    supports: bool,
) -> None:
    """Create or update a vote edge for a character on an agenda.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the voting Character node.
        agenda_id: ID of the Agenda node.
        weight: Voting weight 0–100.
        supports: True for SUPPORTS_AGENDA, False for OPPOSES_AGENDA.
    """
    cypher = _CYPHER_VOTE_SUPPORTS if supports else _CYPHER_VOTE_OPPOSES
    await session.run(cypher, character_id=character_id, agenda_id=agenda_id, weight=weight)
