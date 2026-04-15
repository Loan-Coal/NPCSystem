"""
relation_mutator.py - Applies validated relation deltas through graph writer.

Does NOT: decide delta policy rules.

Dependencies injected: AsyncSession, Settings.
"""

from neo4j import AsyncSession

from api.schemas import RelationDeltas
from config import Settings
from graph.graph_writer import apply_relation_delta
from utils.errors import RelationEdgeNotFoundError


async def apply_dialogue_relation_deltas(
    session: AsyncSession,
    settings: Settings,
    npc_id: str,
    player_id: str,
    relation_deltas: RelationDeltas,
    cause_id: str,
    tick_id: int,
) -> None:
    """Apply dialogue relation deltas, skipping missing-edge cases safely."""

    try:
        await apply_relation_delta(
            session=session,
            settings=settings,
            src_id=npc_id,
            dst_id=player_id,
            deltas=relation_deltas.model_dump(),
            cause_id=cause_id,
            tick_id=tick_id,
        )
    except RelationEdgeNotFoundError:
        return
