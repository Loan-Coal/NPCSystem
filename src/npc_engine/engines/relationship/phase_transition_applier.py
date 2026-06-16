"""
Module: phase_transition_applier
Layer: engines
Purpose: After a dialogue relation delta lands, read the edge's current affinity
         scalars + phase, derive whether the relationship crossed a phase band,
         and persist the new phase only on a transition (F1.1 call-site wiring).
Does NOT: apply relation deltas, open sessions/transactions, or call LLM services.
Dependencies injected: RelationReadPort (read) + RelationPhaseWritePort (write) ports
         per call (DEC-122 / SEV-24 — no Neo4j session); composes the pure
         affinity_engine.derive_phase.
Used by: engines/dialogue/dialogue_handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.engines.relationship.affinity_engine import (
    PhaseTransition,
    RelationshipPhase,
    derive_phase,
)

if TYPE_CHECKING:
    from npc_engine.engines.ports.relation_phase_write_port import RelationPhaseWritePort
    from npc_engine.engines.ports.relation_read_port import RelationReadPort

_DEFAULT_PHASE: RelationshipPhase = RelationshipPhase.STRANGER


def _current_phase(stored: str | None) -> RelationshipPhase:
    """Map a stored phase string to its enum, defaulting an unset edge to STRANGER."""
    return RelationshipPhase(stored) if stored is not None else _DEFAULT_PHASE


async def apply_phase_transition(
    relation_reader: RelationReadPort,
    phase_writer: RelationPhaseWritePort,
    *,
    src_id: str,
    dst_id: str,
    tick: int,
) -> PhaseTransition | None:
    """Persist a relationship phase transition for the (src -> dst) edge if one occurred.

    Reads the post-delta scalars + stored phase via the read port, derives the band, and
    writes the new phase via the write port only when it differs. A missing edge is a
    no-op; an unset stored phase is treated as the STRANGER baseline.

    Args:
        relation_reader: Read port exposing the edge's scalars + persisted phase row.
        phase_writer: Write port persisting the new phase on transition.
        src_id: Source character (NPC) node id.
        dst_id: Destination character (player) node id.
        tick: Game tick recorded as the phase start tick on transition.

    Returns:
        The PhaseTransition that was persisted, or None when no transition occurred.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure (from the ports).
    """
    state = await relation_reader.get_relation_phase_row(src_id=src_id, dst_id=dst_id)
    if state is None:
        return None
    transition = derive_phase(
        trust=state.trust, fear=state.fear, affection=state.affection,
        current_phase=_current_phase(state.relationship_phase), tick=tick,
    )
    if transition is None:
        return None
    await phase_writer.write_relationship_phase(
        src_id=src_id, dst_id=dst_id, phase=transition.new_phase.value, tick=tick,
    )
    return transition
