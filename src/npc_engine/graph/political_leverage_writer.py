"""
Module: political_leverage_writer
Layer: graph
Purpose: Write operations for Leverage nodes and HAS_LEVERAGE / AGAINST / GROUNDED_IN edges.
Does NOT: call LLMs.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.succession.succession_engine (indirectly via leverage ops)
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession


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
