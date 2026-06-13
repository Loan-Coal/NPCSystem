"""
Module: scheme_writer
Layer: graph
Purpose: Upserts Scheme nodes, EXECUTES_SCHEME edges from Character to Scheme,
         and SCHEME_STEP edges from Scheme to Event in Neo4j.
Does NOT: call LLMs, import from engines layer, derive scheme content, or manage
          transaction lifecycle beyond what callers provide.
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
Used by: engines/scheming/scheming_engine.py (cap reader + write path).
"""

from __future__ import annotations

from neo4j import AsyncSession
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Cypher constants — use labels/edge names from type_registry YAML contracts
# ---------------------------------------------------------------------------

_CYPHER_UPSERT_SCHEME = """
MERGE (s:Scheme {id: $scheme_id})
ON CREATE SET s.id = $scheme_id,
              s.npc_id = $npc_id,
              s.goal = $goal,
              s.status = $status,
              s.created_at_game_time = $created_at_game_time
SET s.goal = $goal,
    s.status = $status
WITH s
MATCH (c:Character {id: $npc_id})
MERGE (c)-[e:EXECUTES_SCHEME {started_at_tick: $started_at_tick}]->(s)
"""

_CYPHER_ADD_SCHEME_STEP = """
MATCH (s:Scheme {id: $scheme_id})
MERGE (ev:Event {id: $event_id})
MERGE (s)-[st:SCHEME_STEP]->(ev)
SET st.step_order = $step_order,
    st.completed = $completed
"""

_CYPHER_GET_ACTIVE_SCHEMES = """
MATCH (c:Character {id: $npc_id})-[:EXECUTES_SCHEME]->(s:Scheme)
WHERE s.status = 'active'
RETURN s.id, s.npc_id, s.goal, s.status, s.created_at_game_time
"""

_CYPHER_GET_ALL_ACTIVE_SCHEMES_WITH_STEPS = """
MATCH (c:Character)-[:EXECUTES_SCHEME]->(s:Scheme)
WHERE s.status = 'active'
OPTIONAL MATCH (s)-[st:SCHEME_STEP]->(:Event)
RETURN s.id AS scheme_id, s.npc_id AS npc_id, s.goal AS goal,
       count(st) AS step_count
"""

_DEFAULT_STATUS: str = "active"


# ---------------------------------------------------------------------------
# Read model
# ---------------------------------------------------------------------------


class SchemeRecord(BaseModel):
    """Graph record representing a Scheme node.

    Attributes:
        id: Stable scheme node ID.
        npc_id: NPC that owns (EXECUTES_SCHEME) this scheme.
        goal: Free-text description of the scheme's covert goal.
        status: Current lifecycle status (e.g. 'active', 'completed', 'failed').
        created_at_game_time: Game-tick string when the scheme was created, if set.
    """

    id: str
    npc_id: str
    goal: str
    status: str | None = None
    created_at_game_time: str | None = None


class ActiveSchemeProgress(BaseModel):
    """Active scheme plus its current step count, across all NPCs.

    Used by the F1.6 scheme-advance tick to decide which schemes are below the
    step cap and what the next step_order should be.

    Attributes:
        scheme_id: Stable scheme node ID.
        npc_id: NPC that owns the scheme (the covert event's actor/location source).
        goal: Free-text covert goal (used to template the covert event summary).
        step_count: Number of existing SCHEME_STEP edges on the scheme.
    """

    scheme_id: str
    npc_id: str
    goal: str
    step_count: int


# ---------------------------------------------------------------------------
# Write functions
# ---------------------------------------------------------------------------


async def upsert_scheme(
    session: AsyncSession,
    scheme_id: str,
    npc_id: str,
    goal: str,
    tick: int,
    status: str = _DEFAULT_STATUS,
) -> None:
    """Upsert a Scheme node and attach the EXECUTES_SCHEME edge from the Character.

    Uses MERGE keyed on scheme_id so the operation is idempotent.

    Args:
        session: Active Neo4j async session.
        scheme_id: Stable unique ID for the Scheme node.
        npc_id: Character node ID that owns (EXECUTES) the scheme.
        goal: Free-text covert goal description.
        tick: Current game tick stored as started_at_tick on the edge.
        status: Lifecycle status string; defaults to 'active'.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            _CYPHER_UPSERT_SCHEME,
            scheme_id=scheme_id,
            npc_id=npc_id,
            goal=goal,
            status=status,
            created_at_game_time=str(tick),
            started_at_tick=tick,
        )
        await tx.commit()


async def add_scheme_step(
    session: AsyncSession,
    scheme_id: str,
    event_id: str,
    step_order: int,
    completed: bool,
) -> None:
    """Add or update a SCHEME_STEP edge from a Scheme node to an Event node.

    Uses MERGE so repeated calls with the same (scheme_id, event_id) are idempotent;
    step_order and completed are always SET to the provided values.

    Args:
        session: Active Neo4j async session.
        scheme_id: Scheme node ID (source of the SCHEME_STEP edge).
        event_id: Event node ID (destination of the SCHEME_STEP edge).
        step_order: Ordinal position of this step in the scheme sequence.
        completed: Whether this step has been completed.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            _CYPHER_ADD_SCHEME_STEP,
            scheme_id=scheme_id,
            event_id=event_id,
            step_order=step_order,
            completed=completed,
        )
        await tx.commit()


# ---------------------------------------------------------------------------
# Read function — used by the cap check in scheming_engine
# ---------------------------------------------------------------------------


async def get_active_schemes(
    session: AsyncSession,
    npc_id: str,
) -> list[SchemeRecord]:
    """Fetch all active Scheme nodes for a given NPC.

    Returns an empty list when the NPC has no EXECUTES_SCHEME edges to Scheme
    nodes with status='active'.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID to query.

    Returns:
        List of SchemeRecord instances (may be empty).

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    result = await session.run(_CYPHER_GET_ACTIVE_SCHEMES, npc_id=npc_id)
    records: list[SchemeRecord] = []
    async for row in result:
        data = row.data()
        records.append(
            SchemeRecord(
                id=data["s.id"],
                npc_id=data["s.npc_id"],
                goal=data["s.goal"],
                status=data.get("s.status"),
                created_at_game_time=data.get("s.created_at_game_time"),
            )
        )
    return records


async def get_all_active_schemes_with_steps(
    session: AsyncSession,
) -> list[ActiveSchemeProgress]:
    """Fetch every active Scheme (across all NPCs) with its current step count.

    Returns an empty list when no active schemes exist.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of ActiveSchemeProgress (may be empty).

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    result = await session.run(_CYPHER_GET_ALL_ACTIVE_SCHEMES_WITH_STEPS)
    records: list[ActiveSchemeProgress] = []
    async for row in result:
        data = row.data()
        records.append(
            ActiveSchemeProgress(
                scheme_id=data["scheme_id"],
                npc_id=data["npc_id"],
                goal=data["goal"],
                step_count=int(data["step_count"]),
            )
        )
    return records
