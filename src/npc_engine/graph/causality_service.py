"""
Module: causality_service
Layer: graph
Purpose: Functions for recording and querying CAUSED_BY edges (event consequence provenance).
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.causality_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.events.event_handler, npc_engine.engines.quest_generation,
         npc_engine.engines.faction_politics, npc_engine.api.routes.causality
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.causality_queries import (
    CYPHER_CREATE_CAUSED_BY,
    get_causes,
    get_consequence_chain,
)


async def record_causation(
    session: AsyncSession,
    *,
    effect_node_id: str,
    effect_node_type: str,
    cause_event_id: str,
    causation_strength: int,
    cause_type: str,
    tick_lag: int,
) -> None:
    """Write a CAUSED_BY edge from an effect node to its cause event.

    Args:
        session: Active Neo4j async session.
        effect_node_id: ID of the effect node (Event, Quest, or Rumor).
        effect_node_type: Label of the effect node (informational, not used in query).
        cause_event_id: ID of the Event node that caused the effect.
        causation_strength: How strongly this cause drove the effect (0–100).
        cause_type: Relationship type ("direct", "indirect", "narrative").
        tick_lag: Ticks between the cause and the effect.
    """
    await session.run(
        CYPHER_CREATE_CAUSED_BY,
        effect_node_id=effect_node_id,
        cause_event_id=cause_event_id,
        causation_strength=causation_strength,
        cause_type=cause_type,
        tick_lag=tick_lag,
    )


async def get_consequence_chain_svc(
    session: AsyncSession,
    *,
    root_event_id: str,
    max_depth: int = 5,
) -> list[dict[str, Any]]:
    """Walk CAUSED_BY edges forward from a root event and return the causal chain.

    Args:
        session: Active Neo4j async session.
        root_event_id: ID of the originating event node.
        max_depth: Maximum edge hops to traverse (default 5).

    Returns:
        List of effect node dicts ordered by depth ascending.
    """
    return await get_consequence_chain(
        session, root_event_id=root_event_id, max_depth=max_depth
    )


async def get_causes_svc(
    session: AsyncSession,
    *,
    node_id: str,
    node_type: str,
) -> list[dict[str, Any]]:
    """Return direct cause events for a given node.

    Args:
        session: Active Neo4j async session.
        node_id: ID of the effect node.
        node_type: Label of the effect node.

    Returns:
        List of cause event dicts.
    """
    return await get_causes(session, node_id=node_id, node_type=node_type)
