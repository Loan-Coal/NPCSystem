"""
Module: scheme_writer
Layer: graph
Purpose: Upserts Scheme nodes, EXECUTES_SCHEME edges from Character to Scheme,
         SCHEME_STEP edges from Scheme to Event, and the active→discovered status
         transition. Read queries live in graph/scheme_reader.py.
Does NOT: call LLMs, import from engines layer, derive scheme content, run read
          queries, or manage transaction lifecycle beyond what callers provide.
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
         ``add_scheme_step`` also accepts ``AsyncTransaction`` directly so callers
         that need atomic Event+Step writes (scheme_advance_tick) can share one tx.
Used by: engines/scheming/scheming_engine.py, engines/scheming/scheme_advance_tick.py,
         engines/investigation/scheme_detection_tick.py.
"""

from __future__ import annotations

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.graph.transaction_coordinator import run_in_tx

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

_CYPHER_MARK_SCHEME_DISCOVERED = """
MATCH (s:Scheme {id: $scheme_id})
WHERE s.status = 'active'
SET s.status = 'discovered'
RETURN s.id AS scheme_id
"""

_DEFAULT_STATUS: str = "active"


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
    The write runs inside a single explicit transaction via run_in_tx so it is
    durably committed (SEV-01 L2-08 fix).

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
    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            _CYPHER_UPSERT_SCHEME,
            scheme_id=scheme_id,
            npc_id=npc_id,
            goal=goal,
            status=status,
            created_at_game_time=str(tick),
            started_at_tick=tick,
        )

    await run_in_tx(session, _work)


async def _run_add_scheme_step(
    runner: AsyncSession | AsyncTransaction,
    scheme_id: str,
    event_id: str,
    step_order: int,
    completed: bool,
) -> None:
    """Run the SCHEME_STEP MERGE on a session or transaction runner."""
    await runner.run(
        _CYPHER_ADD_SCHEME_STEP,
        scheme_id=scheme_id,
        event_id=event_id,
        step_order=step_order,
        completed=completed,
    )


async def add_scheme_step(
    *,
    scheme_id: str,
    event_id: str,
    step_order: int,
    completed: bool,
    session: AsyncSession | None = None,
    tx: AsyncTransaction | None = None,
) -> None:
    """Add or update an idempotent SCHEME_STEP edge (Scheme -> Event).

    Supply exactly one of ``tx`` (the write joins the caller's transaction — atomic with
    the paired upsert_event in scheme_advance_tick) or ``session`` (opens+commits its own).

    Args:
        scheme_id: Scheme node ID (edge source).
        event_id: Event node ID (edge destination).
        step_order: Ordinal position of this step in the scheme sequence.
        completed: Whether this step has been completed.
        session: Active Neo4j async session (standalone callers).
        tx: Caller-owned open transaction (atomic callers).

    Raises:
        ValueError: If neither or both of ``tx``/``session`` are provided.
    """
    if tx is not None and session is not None:
        raise ValueError("Provide tx OR session, not both.")
    if tx is None and session is None:
        raise ValueError("One of tx or session must be provided.")

    if tx is not None:
        await _run_add_scheme_step(tx, scheme_id, event_id, step_order, completed)
        return

    async def _work(inner_tx: AsyncTransaction) -> None:
        await _run_add_scheme_step(inner_tx, scheme_id, event_id, step_order, completed)

    await run_in_tx(session, _work)  # type: ignore[arg-type]


async def mark_scheme_discovered(
    session: AsyncSession,
    scheme_id: str,
) -> bool:
    """Flip an active scheme's status to 'discovered' (idempotent, schema-free).

    Only an 'active' scheme transitions; calling on an already-discovered or
    missing scheme is a no-op. The write runs inside an explicit transaction via
    run_in_tx (SEV-01 L2-05 fix — previously used bare session.run auto-commit).

    Args:
        session: Active Neo4j async session.
        scheme_id: Scheme node ID to mark discovered.

    Returns:
        True if the scheme transitioned active→discovered, else False.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    found: list[bool] = [False]

    async def _work(tx: AsyncTransaction) -> None:
        result = await tx.run(_CYPHER_MARK_SCHEME_DISCOVERED, scheme_id=scheme_id)
        record = await result.single()
        await result.consume()
        found[0] = record is not None

    await run_in_tx(session, _work)
    return found[0]
