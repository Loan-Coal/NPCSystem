"""
Module: goal_targets_writer
Layer: graph
Purpose: Write GOAL_TARGETS edges between Goal nodes and their target nodes (location, etc.).
Dependencies: neo4j.AsyncSession
Used by: npc_engine.engines.planning.goal_former
Does NOT: implement business logic, validate inputs beyond type hints, or call LLMs.
Dependencies injected: AsyncSession (passed per call).
"""

from __future__ import annotations

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher
# ---------------------------------------------------------------------------

CYPHER_MERGE_GOAL_TARGETS = """
MATCH (g:Goal {id: $goal_id})
MATCH (t {id: $target_id})
MERGE (g)-[r:GOAL_TARGETS]->(t)
SET r.priority = $priority
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_goal_targets_edge(
    session: AsyncSession,
    goal_id: str,
    target_id: str,
    priority: int,
) -> None:
    """Create or update a GOAL_TARGETS edge from a Goal to its target node.

    Uses MERGE so repeated calls with the same goal_id/target_id are idempotent.
    The priority field is always updated to reflect the latest urgency value.

    Args:
        session: Active Neo4j async session.
        goal_id: ID of the source Goal node.
        target_id: ID of the target node (typically a Location).
        priority: Edge priority value in range [0, 100].
    """
    await session.run(
        CYPHER_MERGE_GOAL_TARGETS,
        goal_id=goal_id,
        target_id=target_id,
        priority=priority,
    )
