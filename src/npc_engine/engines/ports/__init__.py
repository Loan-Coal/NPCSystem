"""
Package: ports
Layer: engines
Purpose: Structural graph-access Protocols for ports meeting the DIP threshold
         (2+ implementors OR 3+ callers). Below-threshold ports were collapsed to
         concrete constructor injection in T9.1b–d (DEC-275).
Does NOT: open sessions, run Cypher, hold state, or import the graph layer.
Dependencies injected: none (pure interfaces).
Public surface: WorldStateGraphPort, MemoryConsolidationGraphPort, ChapterGraphPort,
                RelationReadPort, PlayerLocationReadPort,
                CharacterReadPort, EventGraphPort, KnowledgeGraphPort,
                ReputationGraphPort, PlayerModelGraphPort, PlanningGraphPort,
                IntentGraphPort, InteractionGraphPort,
                ProactiveMemoryReadPort, RelationPhaseWritePort.
"""

from __future__ import annotations

from npc_engine.engines.ports.chapter_port import ChapterGraphPort
from npc_engine.engines.ports.character_read_port import CharacterReadPort
from npc_engine.engines.ports.event_port import EventGraphPort
from npc_engine.engines.ports.intent_port import IntentGraphPort
from npc_engine.engines.ports.interaction_port import InteractionGraphPort
from npc_engine.engines.ports.knowledge_port import KnowledgeGraphPort
from npc_engine.engines.ports.memory_consolidation_port import MemoryConsolidationGraphPort
from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
from npc_engine.engines.ports.planning_port import PlanningGraphPort
from npc_engine.engines.ports.proactive_memory_read_port import ProactiveMemoryReadPort
from npc_engine.engines.ports.player_model_port import PlayerModelGraphPort
from npc_engine.engines.ports.relation_phase_write_port import RelationPhaseWritePort
from npc_engine.engines.ports.relation_read_port import RelationReadPort
from npc_engine.engines.ports.reputation_port import ReputationGraphPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort

__all__ = [
    "ChapterGraphPort",
    "CharacterReadPort",
    "EventGraphPort",
    "IntentGraphPort",
    "InteractionGraphPort",
    "KnowledgeGraphPort",
    "MemoryConsolidationGraphPort",
    "PlanningGraphPort",
    "PlayerLocationReadPort",
    "PlayerModelGraphPort",
    "ProactiveMemoryReadPort",
    "RelationPhaseWritePort",
    "RelationReadPort",
    "ReputationGraphPort",
    "WorldStateGraphPort",
]
