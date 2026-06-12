"""
Module: phase_transition_applier
Layer: engines
Purpose: After a dialogue relation delta lands, read the edge's current affinity
         scalars + phase, derive whether the relationship crossed a phase band,
         and persist the new phase only on a transition (F1.1 call-site wiring).
Does NOT: apply relation deltas, open transactions, or call LLM services.
Dependencies injected: AsyncSession (per call); composes the graph phase
         reader/writer and the pure affinity_engine.derive_phase.
Used by: engines/dialogue/dialogue_handler.
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.relationship.affinity_engine import (
    PhaseTransition,
    RelationshipPhase,
    derive_phase,
)
from npc_engine.graph.relation_phase_reader import get_relation_phase_state
from npc_engine.graph.relation_phase_writer import write_relationship_phase

_DEFAULT_PHASE: RelationshipPhase = RelationshipPhase.STRANGER


def _current_phase(stored: str | None) -> RelationshipPhase:
    """Map a stored phase string to its enum, defaulting an unset edge to STRANGER."""
    return RelationshipPhase(stored) if stored is not None else _DEFAULT_PHASE


async def apply_phase_transition(
    *, session: AsyncSession, src_id: str, dst_id: str, tick: int
) -> PhaseTransition | None:
    """Persist a relationship phase transition for the (src -> dst) edge if one occurred.

    Reads the post-delta scalars + stored phase, derives the band, and writes the new
    phase only when it differs. A missing edge is a no-op; an unset stored phase is
    treated as the STRANGER baseline.

    Args:
        session: Active Neo4j async session (opens its own sub-transactions).
        src_id: Source character (NPC) node id.
        dst_id: Destination character (player) node id.
        tick: Game tick recorded as the phase start tick on transition.

    Returns:
        The PhaseTransition that was persisted, or None when no transition occurred.

    Raises:
        neo4j.exceptions.Neo4jError: On graph connectivity or query failure.
    """
    state = await get_relation_phase_state(session=session, src_id=src_id, dst_id=dst_id)
    if state is None:
        return None
    transition = derive_phase(
        trust=state.trust, fear=state.fear, affection=state.affection,
        current_phase=_current_phase(state.relationship_phase), tick=tick,
    )
    if transition is None:
        return None
    await write_relationship_phase(
        session=session, src_id=src_id, dst_id=dst_id,
        phase=transition.new_phase.value, tick=tick,
    )
    return transition
