"""
relation_mutator.py - Applies validated relation deltas through graph writer.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: decide delta policy rules.

Dependencies injected: AsyncSession, Settings.

Structured audit log events emitted:
- ``relation_delta_attempt``: before the graph write (INFO).
- ``relation_delta_applied``: after a successful write (INFO).
- ``relation_edge_missing``: when no RELATES_TO edge exists (WARNING).
All events carry npc_id, player_id, tick_id, and cause_id as extra fields.
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
from npc_engine.graph.graph_writer import apply_relation_delta
from npc_engine.utils.errors import RelationEdgeNotFoundError
from npc_engine.utils.logging import get_logger


_LOGGER = get_logger(__name__)


async def _write_delta(
    session: AsyncSession,
    settings: Settings,
    npc_id: str,
    player_id: str,
    relation_deltas: RelationDeltas,
    cause_id: str,
    tick_id: int,
    log_extra: dict[str, object],
) -> None:
    """Attempt the graph write and emit applied/missing audit events."""
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
        _LOGGER.info("relation_delta_applied", extra=log_extra)
    except RelationEdgeNotFoundError:
        _LOGGER.warning("relation_edge_missing", extra=log_extra)


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

    Emits structured audit log events before the write, after success, and
    when the target RELATES_TO edge is not found. Missing-edge errors are
    caught and logged so the caller's response flow is not interrupted.

    Args:
        session: Active Neo4j async session.
        settings: Application settings forwarded to the graph writer.
        npc_id: Source node identifier (NPC).
        player_id: Destination node identifier (player).
        relation_deltas: Per-field delta values from the dialogue response.
        cause_id: Opaque string identifying the cause for audit logging.
        tick_id: Game tick identifier for delta log attribution.
    """
    log_extra: dict[str, object] = {
        "npc_id": npc_id,
        "player_id": player_id,
        "tick_id": tick_id,
        "cause_id": cause_id,
    }
    _LOGGER.info(
        "relation_delta_attempt",
        extra={**log_extra, "deltas": str(relation_deltas.model_dump())},
    )
    await _write_delta(session, settings, npc_id, player_id, relation_deltas, cause_id, tick_id, log_extra)
