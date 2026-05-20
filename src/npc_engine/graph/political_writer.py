"""
Module: political_writer
Layer: graph
Purpose: Write operations for Phase 7.2 Political Simulation.
         Creates and manages Title, Agenda, and Leverage nodes with their connecting edges.
         Succession (HOLDS_TITLE), voting (SUPPORTS/OPPOSES_AGENDA), and heir registration
         are all handled here.
Does NOT: call LLMs or implement voting logic (tallying is in the engine layer).
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.succession.succession_engine,
         npc_engine.engines.agenda.agenda_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


# ---------------------------------------------------------------------------
# Title write operations
# ---------------------------------------------------------------------------

_CYPHER_CREATE_TITLE = """
CREATE (t:Title {
    id: $id,
    name: $name,
    faction_id: $faction_id,
    power: $power,
    is_inheritable: $is_inheritable
})
"""

_CYPHER_REMOVE_HOLDS_TITLE = """
MATCH (c:Character)-[h:HOLDS_TITLE]->(t:Title {id: $title_id})
DELETE h
"""

_CYPHER_CREATE_HOLDS_TITLE = """
MATCH (c:Character {id: $character_id})
MATCH (t:Title {id: $title_id})
CREATE (c)-[:HOLDS_TITLE {since_tick: $since_tick}]->(t)
"""

_CYPHER_CREATE_HEIR_OF = """
MATCH (heir:Character {id: $heir_id})
MATCH (predecessor:Character {id: $predecessor_id})
MERGE (heir)-[h:HEIR_OF {predecessor_id: $predecessor_id}]->(predecessor)
SET h.priority = $priority, h.legitimacy = $legitimacy
"""


async def create_title(
    session: AsyncSession,
    *,
    name: str,
    faction_id: str,
    power: int,
    is_inheritable: bool,
) -> str:
    """Create a Title node and return its ID.

    Args:
        session: Active Neo4j async session.
        name: Title name (e.g., 'Duke of Ember').
        faction_id: ID of the Faction that owns this title.
        power: Political power value of the title.
        is_inheritable: Whether the title passes to heirs on vacancy.

    Returns:
        ID of the newly created Title node.
    """
    title_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_TITLE,
        id=title_id,
        name=name,
        faction_id=faction_id,
        power=power,
        is_inheritable=is_inheritable,
    )
    return title_id


async def grant_title(
    session: AsyncSession,
    *,
    character_id: str,
    title_id: str,
    tick: int,
) -> None:
    """Grant a title to a character, removing any existing holder first.

    This removes all existing HOLDS_TITLE edges for the title before creating
    the new one, ensuring exactly one holder at a time.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character receiving the title.
        title_id: ID of the Title node.
        tick: Current game tick (stored on the HOLDS_TITLE edge as since_tick).
    """
    await session.run(_CYPHER_REMOVE_HOLDS_TITLE, title_id=title_id)
    await session.run(
        _CYPHER_CREATE_HOLDS_TITLE,
        character_id=character_id,
        title_id=title_id,
        since_tick=tick,
    )


async def add_heir(
    session: AsyncSession,
    *,
    heir_id: str,
    predecessor_id: str,
    priority: int,
    legitimacy: int,
) -> None:
    """Register a character as heir to another character.

    Uses MERGE so re-registering an heir updates priority/legitimacy without duplicating.

    Args:
        session: Active Neo4j async session.
        heir_id: ID of the heir Character node.
        predecessor_id: ID of the predecessor Character node.
        priority: Succession order — lower number means higher priority.
        legitimacy: Legitimacy score 0–100.
    """
    await session.run(
        _CYPHER_CREATE_HEIR_OF,
        heir_id=heir_id,
        predecessor_id=predecessor_id,
        priority=priority,
        legitimacy=legitimacy,
    )


# ---------------------------------------------------------------------------
# Agenda write operations
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Leverage write operations
# ---------------------------------------------------------------------------

_CYPHER_CREATE_LEVERAGE_NODE = """
CREATE (l:Leverage {
    id: $id,
    demand: $demand,
    status: $status,
    created_at_tick: $created_at_tick
})
"""

_CYPHER_CREATE_HAS_LEVERAGE = """
MATCH (holder:Character {id: $holder_id})
MATCH (lev:Leverage {id: $leverage_id})
CREATE (holder)-[:HAS_LEVERAGE]->(lev)
"""

_CYPHER_CREATE_AGAINST = """
MATCH (lev:Leverage {id: $leverage_id})
MATCH (target:Character {id: $target_id})
CREATE (lev)-[:AGAINST]->(target)
"""

_CYPHER_CREATE_GROUNDED_IN = """
MATCH (lev:Leverage {id: $leverage_id})
MATCH (s:Secret {id: $secret_id})
CREATE (lev)-[:GROUNDED_IN]->(s)
"""

_CYPHER_SET_LEVERAGE_STATUS = """
MATCH (l:Leverage {id: $leverage_id})
SET l.status = $status
"""


async def create_leverage(
    session: AsyncSession,
    *,
    holder_id: str,
    target_id: str,
    secret_id: str,
    demand: str,
    tick: int,
) -> str:
    """Create a reified Leverage node with HAS_LEVERAGE, AGAINST, and GROUNDED_IN edges.

    All three edges are created atomically. If any MATCH fails (missing nodes),
    the Cypher will silently skip the edge — callers must ensure nodes exist.

    Args:
        session: Active Neo4j async session.
        holder_id: ID of the Character who holds the leverage.
        target_id: ID of the Character who is leveraged.
        secret_id: ID of the Secret node that grounds this leverage (F3 fix).
        demand: The demand the holder is making.
        tick: Current game tick.

    Returns:
        ID of the newly created Leverage node.
    """
    leverage_id = str(uuid.uuid4())
    await session.run(
        _CYPHER_CREATE_LEVERAGE_NODE,
        id=leverage_id,
        demand=demand,
        status="held",
        created_at_tick=tick,
    )
    await session.run(_CYPHER_CREATE_HAS_LEVERAGE, holder_id=holder_id, leverage_id=leverage_id)
    await session.run(_CYPHER_CREATE_AGAINST, leverage_id=leverage_id, target_id=target_id)
    await session.run(_CYPHER_CREATE_GROUNDED_IN, leverage_id=leverage_id, secret_id=secret_id)
    return leverage_id


async def use_leverage(
    session: AsyncSession,
    *,
    leverage_id: str,
) -> None:
    """Mark a Leverage node as used.

    Args:
        session: Active Neo4j async session.
        leverage_id: ID of the Leverage node.
    """
    await session.run(_CYPHER_SET_LEVERAGE_STATUS, leverage_id=leverage_id, status="used")
