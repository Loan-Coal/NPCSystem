"""
Module: scheme_reader
Layer: graph
Purpose: Read-only queries over Scheme nodes — per-NPC active schemes (cap check),
         all active schemes with step counts (advance tick), and discoverable
         schemes (detection tick). Split from scheme_writer to keep each module
         single-responsibility and under the 300-line limit.
Does NOT: call LLMs, import from engines, mutate the graph, or manage transactions.
Dependencies injected: AsyncSession (per call — stateless).
Used by: engines/scheming/scheming_engine.py, engines/scheming/scheme_advance_tick.py,
         engines/investigation/scheme_detection_tick.py.
"""

from __future__ import annotations

from neo4j import AsyncSession
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

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

# Discoverable = an active scheme with >= $min_steps covert steps whose owner shares
# a location with another character (a potential witness to the covert activity).
_CYPHER_GET_DISCOVERABLE_SCHEME_IDS = """
MATCH (c:Character)-[:EXECUTES_SCHEME]->(s:Scheme)
WHERE s.status = 'active'
OPTIONAL MATCH (s)-[st:SCHEME_STEP]->(:Event)
WITH s, c, count(st) AS step_count
WHERE step_count >= $min_steps
MATCH (c)-[:LOCATED_AT]->(:Location)<-[:LOCATED_AT]-(other:Character)
WHERE other.id <> c.id
RETURN DISTINCT s.id AS scheme_id
"""

# All schemes for an NPC (any status) with their ordered steps — feeds the F2.3 route.
_CYPHER_GET_SCHEMES_WITH_STEPS_FOR_NPC = """
MATCH (c:Character {id: $npc_id})-[:EXECUTES_SCHEME]->(s:Scheme)
OPTIONAL MATCH (s)-[st:SCHEME_STEP]->(e:Event)
WITH s, st, e ORDER BY st.step_order
RETURN s.id AS scheme_id, s.goal AS goal, s.status AS status,
       collect({step_order: st.step_order, completed: st.completed, summary: e.summary}) AS steps
"""

_DISCOVERED_STATUS: str = "discovered"


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class SchemeRecord(BaseModel):
    """Graph record representing a Scheme node.

    Attributes:
        id: Stable scheme node ID.
        npc_id: NPC that owns (EXECUTES_SCHEME) this scheme.
        goal: Free-text description of the scheme's covert goal.
        status: Current lifecycle status (e.g. 'active', 'discovered', 'completed').
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


class SchemeStepView(BaseModel):
    """One covert step of a scheme, ordered by step_order.

    Attributes:
        step_order: 1-based ordinal of the step.
        completed: Whether the step is marked completed.
        summary: The covert Event's summary (the in-world deed), if present.
    """

    step_order: int
    completed: bool
    summary: str | None = None


class SchemeWithSteps(BaseModel):
    """A scheme (any status) with its ordered steps and a discovered flag.

    Attributes:
        scheme_id: Stable scheme node ID.
        goal: Free-text covert goal.
        status: Lifecycle status ('active', 'discovered', ...).
        discovered: True when status == 'discovered' (surfaced to the player).
        steps: Ordered covert steps that have manifested so far.
    """

    scheme_id: str
    goal: str
    status: str | None = None
    discovered: bool = False
    steps: list[SchemeStepView] = []


# ---------------------------------------------------------------------------
# Read functions
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


async def get_discoverable_scheme_ids(
    session: AsyncSession,
    min_steps: int,
) -> list[str]:
    """Return active scheme IDs ripe for discovery (witnessed + enough steps).

    A scheme is discoverable when it has at least ``min_steps`` covert steps and
    its owner shares a location with another character (a potential witness).

    Args:
        session: Active Neo4j async session.
        min_steps: Minimum SCHEME_STEP count before a scheme can be discovered.

    Returns:
        List of discoverable scheme IDs (may be empty).

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    result = await session.run(_CYPHER_GET_DISCOVERABLE_SCHEME_IDS, min_steps=min_steps)
    return [row.data()["scheme_id"] async for row in result]


def _to_step_views(raw_steps: list[dict]) -> list[SchemeStepView]:
    """Convert raw step maps to SchemeStepView, dropping null placeholders.

    A scheme with no steps yields a single map whose step_order is None (from the
    OPTIONAL MATCH); such rows are filtered out.

    Args:
        raw_steps: List of {step_order, completed, summary} maps from the query.

    Returns:
        Ordered list of SchemeStepView (may be empty).
    """
    views = [
        SchemeStepView(
            step_order=int(step["step_order"]),
            completed=bool(step.get("completed")),
            summary=step.get("summary"),
        )
        for step in raw_steps
        if step.get("step_order") is not None
    ]
    return sorted(views, key=lambda v: v.step_order)


async def get_schemes_with_steps_for_npc(
    session: AsyncSession,
    npc_id: str,
) -> list[SchemeWithSteps]:
    """Fetch all schemes (any status) for an NPC with their ordered steps.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID whose schemes are requested.

    Returns:
        List of SchemeWithSteps (may be empty). ``discovered`` is True when the
        scheme's status is 'discovered'.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    result = await session.run(_CYPHER_GET_SCHEMES_WITH_STEPS_FOR_NPC, npc_id=npc_id)
    schemes: list[SchemeWithSteps] = []
    async for row in result:
        data = row.data()
        schemes.append(
            SchemeWithSteps(
                scheme_id=data["scheme_id"],
                goal=data["goal"],
                status=data.get("status"),
                discovered=data.get("status") == _DISCOVERED_STATUS,
                steps=_to_step_views(data.get("steps", [])),
            )
        )
    return schemes
