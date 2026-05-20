"""
Module: political_queries
Layer: graph
Purpose: Read-only Cypher queries for Phase 7.2 Political Simulation.
         Returns title holders, heirs, agendas, votes, and leverage data.
         Title holders are always queried via HOLDS_TITLE edge — never via a stale field (F2 fix).
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.succession.succession_engine,
         npc_engine.engines.agenda.agenda_engine,
         npc_engine.graph.political_writer
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


# ---------------------------------------------------------------------------
# Title queries
# ---------------------------------------------------------------------------

_CYPHER_CURRENT_TITLE_HOLDER = """
MATCH (c:Character)-[h:HOLDS_TITLE]->(t:Title {id: $title_id})
RETURN properties(c) AS character, h.since_tick AS since_tick
ORDER BY h.since_tick DESC
LIMIT 1
"""

_CYPHER_TITLES_FOR_FACTION = """
MATCH (t:Title {faction_id: $faction_id})
RETURN properties(t) AS title
"""

_CYPHER_VACANT_INHERITABLE_TITLES = """
MATCH (t:Title {is_inheritable: true})
WHERE NOT exists { (c:Character)-[:HOLDS_TITLE]->(t) }
RETURN properties(t) AS title
"""


async def get_current_title_holder(
    session: AsyncSession,
    title_id: str,
) -> dict[str, Any] | None:
    """Return the current holder of a title via HOLDS_TITLE edge.

    Args:
        session: Active Neo4j async session.
        title_id: ID of the Title node.

    Returns:
        Dict with keys ``character`` (props) and ``since_tick``, or None if vacant.
    """
    result = await session.run(_CYPHER_CURRENT_TITLE_HOLDER, title_id=title_id)
    row = await result.single()
    if row is None:
        return None
    return {"character": dict(row["character"]), "since_tick": row["since_tick"]}


async def get_titles_for_faction(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Return all titles belonging to a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the Faction node.

    Returns:
        List of title property dicts.
    """
    result = await session.run(_CYPHER_TITLES_FOR_FACTION, faction_id=faction_id)
    return [dict(r["title"]) async for r in result]


async def get_vacant_inheritable_titles(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all inheritable Title nodes that have no current HOLDS_TITLE holder.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of title property dicts.
    """
    result = await session.run(_CYPHER_VACANT_INHERITABLE_TITLES)
    return [dict(r["title"]) async for r in result]


# ---------------------------------------------------------------------------
# Heir queries
# ---------------------------------------------------------------------------

_CYPHER_HEIRS_FOR_CHARACTER = """
MATCH (heir:Character)-[h:HEIR_OF]->(predecessor:Character {id: $character_id})
RETURN properties(heir) AS heir, h.priority AS priority, h.legitimacy AS legitimacy
ORDER BY h.priority ASC, h.legitimacy DESC
"""


async def get_heirs_for_character(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return heirs of a character ordered by priority ascending (lower = higher priority).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the predecessor Character node.

    Returns:
        List of dicts with keys: heir (props), priority, legitimacy.
    """
    result = await session.run(_CYPHER_HEIRS_FOR_CHARACTER, character_id=character_id)
    return [
        {
            "heir": dict(r["heir"]),
            "priority": r["priority"],
            "legitimacy": r["legitimacy"],
        }
        async for r in result
    ]


# ---------------------------------------------------------------------------
# Agenda queries
# ---------------------------------------------------------------------------

_CYPHER_OPEN_AGENDAS = """
MATCH (a:Agenda {status: 'open'})
RETURN properties(a) AS agenda
"""

_CYPHER_EXPIRED_OPEN_AGENDAS = """
MATCH (a:Agenda {status: 'open'})
WHERE a.deadline_tick IS NOT NULL AND a.deadline_tick <= $current_tick
RETURN properties(a) AS agenda
"""

_CYPHER_AGENDA_VOTES = """
MATCH (a:Agenda {id: $agenda_id})
OPTIONAL MATCH (supporter:Character)-[s:SUPPORTS_AGENDA]->(a)
OPTIONAL MATCH (opposer:Character)-[o:OPPOSES_AGENDA]->(a)
RETURN
  collect(DISTINCT {character: properties(supporter), weight: s.weight}) AS supports,
  collect(DISTINCT {character: properties(opposer), weight: o.weight}) AS opposes
"""


async def get_open_agendas(session: AsyncSession) -> list[dict[str, Any]]:
    """Return all Agenda nodes with status='open'.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of agenda property dicts.
    """
    result = await session.run(_CYPHER_OPEN_AGENDAS)
    return [dict(r["agenda"]) async for r in result]


async def get_expired_open_agendas(
    session: AsyncSession,
    current_tick: int,
) -> list[dict[str, Any]]:
    """Return open agendas whose deadline_tick has passed.

    Args:
        session: Active Neo4j async session.
        current_tick: Current game tick.

    Returns:
        List of agenda property dicts.
    """
    result = await session.run(_CYPHER_EXPIRED_OPEN_AGENDAS, current_tick=current_tick)
    return [dict(r["agenda"]) async for r in result]


async def get_agenda_votes(
    session: AsyncSession,
    agenda_id: str,
) -> dict[str, Any]:
    """Return tallied SUPPORTS_AGENDA and OPPOSES_AGENDA votes for an agenda.

    Args:
        session: Active Neo4j async session.
        agenda_id: ID of the Agenda node.

    Returns:
        Dict with keys ``supports`` (list of {character, weight}) and
        ``opposes`` (list of {character, weight}).
    """
    result = await session.run(_CYPHER_AGENDA_VOTES, agenda_id=agenda_id)
    row = await result.single()
    if row is None:
        return {"supports": [], "opposes": []}
    return {
        "supports": [r for r in row["supports"] if r.get("character")],
        "opposes": [r for r in row["opposes"] if r.get("character")],
    }


# ---------------------------------------------------------------------------
# Leverage queries
# ---------------------------------------------------------------------------

_CYPHER_LEVERAGE_HELD_BY = """
MATCH (holder:Character {id: $character_id})-[:HAS_LEVERAGE]->(lev:Leverage)-[:AGAINST]->(target:Character)
OPTIONAL MATCH (lev)-[:GROUNDED_IN]->(secret:Secret)
RETURN properties(lev) AS leverage,
       properties(target) AS target,
       properties(secret) AS secret
"""

_CYPHER_LEVERAGE_AGAINST = """
MATCH (holder:Character)-[:HAS_LEVERAGE]->(lev:Leverage)-[:AGAINST]->(target:Character {id: $character_id})
OPTIONAL MATCH (lev)-[:GROUNDED_IN]->(secret:Secret)
RETURN properties(lev) AS leverage,
       properties(holder) AS holder,
       properties(secret) AS secret
"""


async def get_leverage_held_by(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return all Leverage nodes held by a character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character who holds leverage.

    Returns:
        List of dicts with keys: leverage (props), target (props), secret (props or None).
    """
    result = await session.run(_CYPHER_LEVERAGE_HELD_BY, character_id=character_id)
    return [
        {
            "leverage": dict(r["leverage"]),
            "target": dict(r["target"]),
            "secret": dict(r["secret"]) if r["secret"] else None,
        }
        async for r in result
    ]


async def get_leverage_against(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return all Leverage nodes held against a character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character being leveraged.

    Returns:
        List of dicts with keys: leverage (props), holder (props), secret (props or None).
    """
    result = await session.run(_CYPHER_LEVERAGE_AGAINST, character_id=character_id)
    return [
        {
            "leverage": dict(r["leverage"]),
            "holder": dict(r["holder"]),
            "secret": dict(r["secret"]) if r["secret"] else None,
        }
        async for r in result
    ]
