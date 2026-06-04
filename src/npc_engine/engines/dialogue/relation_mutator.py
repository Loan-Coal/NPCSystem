"""
relation_mutator.py - Applies validated relation deltas through graph writer.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: decide delta policy rules.

Dependencies injected: AsyncSession, Settings.
"""

from neo4j import AsyncSession

from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
from npc_engine.config import Settings
from npc_engine.graph.graph_writer import apply_relation_delta
from npc_engine.utils.errors import RelationEdgeNotFoundError


async def apply_dialogue_relation_deltas(
    session: AsyncSession,
    settings: Settings,
    npc_id: str,
    player_id: str,
    relation_deltas: RelationDeltas,
    cause_id: str,
    tick_id: int,
) -> None:
    """Apply validated relation deltas from a dialogue turn to the graph.

    Missing-edge errors are silently swallowed so the caller's response flow
    is not interrupted when no relation edge yet exists.

    Args:
        session: Active Neo4j async session.
        settings: Application settings forwarded to the graph writer.
        npc_id: Source node identifier (NPC).
        player_id: Destination node identifier (player).
        relation_deltas: Per-field delta values from the dialogue response.
        cause_id: Opaque string identifying the cause for audit logging.
        tick_id: Game tick identifier for delta log attribution.
    """

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
