"""
awareness_seeder.py - Seeds factual KNOWS_ABOUT edges for affected NPCs.

Does NOT: choose event templates or open transactions.

Dependencies injected: AsyncTransaction (via graph.event_queries.seed_awareness_tx).
"""

from __future__ import annotations

from neo4j import AsyncTransaction

from npc_engine.graph.event_queries import seed_awareness_tx as _seed_awareness_tx


async def seed_awareness_tx(tx: AsyncTransaction, event_id: str, location_id: str, tick_id: int) -> None:
    """Mark all active NPCs at the given location as knowing the event.

    Delegates to graph.event_queries.seed_awareness_tx. Must be called within
    an open transaction.

    Args:
        tx: Active Neo4j async transaction.
        event_id: Event node ID to seed awareness for.
        location_id: Location node ID scoping which characters are seeded.
        tick_id: Current game tick recorded on each KNOWS_ABOUT edge.
    """
    await _seed_awareness_tx(tx=tx, event_id=event_id, location_id=location_id, tick_id=tick_id)
