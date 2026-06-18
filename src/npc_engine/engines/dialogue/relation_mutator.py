"""
relation_mutator.py - Applies validated relation deltas through the dialogue graph port.
Layer: engines
Purpose: Emit structured audit-log events and delegate relation-delta writes to the
         injected DialogueGraphPort (which owns the first-contact retry logic).

Does NOT: import neo4j types; open sessions; implement graph write logic.

Dependencies injected: DialogueGraphPort, Settings.

Structured audit log events emitted:
- ``relation_delta_attempt``: before the graph write (INFO).
- ``relation_delta_applied``: after a successful write (INFO).
All events carry npc_id, player_id, tick_id, and cause_id as extra fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.engines.dialogue.dialogue_models import RelationDeltas
from npc_engine.utils.logging import get_logger

if TYPE_CHECKING:
    from npc_engine.engines.ports.dialogue_graph_port import DialogueGraphPort

_LOGGER = get_logger(__name__)


async def apply_dialogue_relation_deltas(
    repo: DialogueGraphPort,
    settings: object,
    npc_id: str,
    player_id: str,
    relation_deltas: RelationDeltas,
    cause_id: str,
    tick_id: int,
) -> None:
    """Apply validated relation deltas from a dialogue turn to the graph via port.

    Emits structured audit log events before and after the write.
    First-contact edge creation is handled by the port adapter.

    Args:
        repo: DialogueGraphPort implementation managing the graph writes.
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
    await repo.apply_relation_deltas(
        npc_id=npc_id,
        player_id=player_id,
        relation_deltas=relation_deltas,
        cause_id=cause_id,
        tick_id=tick_id,
        settings=settings,
    )
    _LOGGER.info("relation_delta_applied", extra=log_extra)
