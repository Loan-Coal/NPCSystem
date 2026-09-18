"""
Package: ports
Layer: engines
Purpose: Structural graph-access Protocols for ports meeting the DIP threshold
         (2+ implementors OR 3+ callers). Below-threshold ports were collapsed to
         concrete constructor injection in T9.1b–d (DEC-275).
Does NOT: open sessions, run Cypher, hold state, or import the graph layer.
Dependencies injected: none (pure interfaces).
Public surface: WorldStateGraphPort, RelationReadPort, PlayerLocationReadPort,
                CharacterReadPort, PlanningGraphPort, IntentGraphPort,
                InteractionGraphPort, RelationPhaseWritePort.
"""

from __future__ import annotations

from npc_engine.engines.ports.character_read_port import CharacterReadPort
from npc_engine.engines.ports.intent_port import IntentGraphPort
from npc_engine.engines.ports.interaction_port import InteractionGraphPort
from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
from npc_engine.engines.ports.planning_port import PlanningGraphPort
from npc_engine.engines.ports.relation_phase_write_port import RelationPhaseWritePort
from npc_engine.engines.ports.relation_read_port import RelationReadPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort

__all__ = [
    "CharacterReadPort",
    "IntentGraphPort",
    "InteractionGraphPort",
    "PlanningGraphPort",
    "PlayerLocationReadPort",
    "RelationPhaseWritePort",
    "RelationReadPort",
    "WorldStateGraphPort",
]
