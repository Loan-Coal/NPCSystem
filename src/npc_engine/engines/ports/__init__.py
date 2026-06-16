"""
Package: ports
Layer: engines
Purpose: Structural graph-access Protocols organized by graph domain (the engine
         side of the repository facade). Engines depend on these Ports instead of
         importing neo4j / graph functions or holding a session; Neo4j adapters in
         graph/repositories/ implement them structurally, injected at the api
         composition root (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, hold state, or import the graph layer.
Dependencies injected: none (pure interfaces).
Public surface: NeedGraphPort, MoodGraphPort, GroupGraphPort, SkillGraphPort,
                RoutineGraphPort, PoliticalGraphPort, StoryPacingGraphPort,
                WorldStateGraphPort, MemoryConsolidationGraphPort, ChapterGraphPort,
                MilitaryGraphPort, RelationReadPort, PlayerLocationReadPort,
                CharacterReadPort, EmotionGraphPort, EventGraphPort, KnowledgeGraphPort,
                ReputationGraphPort, PlayerModelGraphPort, PlanningGraphPort,
                EconomyGraphPort, IntentGraphPort, InteractionGraphPort,
                InvestigationGraphPort, MemoryGraphPort,
                ProactiveMemoryReadPort, RelationPhaseWritePort.
"""

from __future__ import annotations

from npc_engine.engines.ports.chapter_port import ChapterGraphPort
from npc_engine.engines.ports.character_read_port import CharacterReadPort
from npc_engine.engines.ports.economy_port import EconomyGraphPort
from npc_engine.engines.ports.emotion_port import EmotionGraphPort
from npc_engine.engines.ports.event_port import EventGraphPort
from npc_engine.engines.ports.group_port import GroupGraphPort
from npc_engine.engines.ports.intent_port import IntentGraphPort
from npc_engine.engines.ports.interaction_port import InteractionGraphPort
from npc_engine.engines.ports.investigation_port import InvestigationGraphPort
from npc_engine.engines.ports.knowledge_port import KnowledgeGraphPort
from npc_engine.engines.ports.memory_consolidation_port import MemoryConsolidationGraphPort
from npc_engine.engines.ports.memory_port import MemoryGraphPort
from npc_engine.engines.ports.military_port import MilitaryGraphPort
from npc_engine.engines.ports.mood_port import MoodGraphPort
from npc_engine.engines.ports.need_port import NeedGraphPort
from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
from npc_engine.engines.ports.planning_port import PlanningGraphPort
from npc_engine.engines.ports.proactive_memory_read_port import ProactiveMemoryReadPort
from npc_engine.engines.ports.player_model_port import PlayerModelGraphPort
from npc_engine.engines.ports.pledge_port import PledgeGraphPort
from npc_engine.engines.ports.political_port import PoliticalGraphPort
from npc_engine.engines.ports.relation_phase_write_port import RelationPhaseWritePort
from npc_engine.engines.ports.relation_read_port import RelationReadPort
from npc_engine.engines.ports.reputation_port import ReputationGraphPort
from npc_engine.engines.ports.routine_port import RoutineGraphPort
from npc_engine.engines.ports.skill_port import SkillGraphPort
from npc_engine.engines.ports.story_pacing_port import StoryPacingGraphPort
from npc_engine.engines.ports.treaty_port import TreatyGraphPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort

__all__ = [
    "ChapterGraphPort",
    "CharacterReadPort",
    "EconomyGraphPort",
    "EmotionGraphPort",
    "EventGraphPort",
    "GroupGraphPort",
    "IntentGraphPort",
    "InteractionGraphPort",
    "InvestigationGraphPort",
    "KnowledgeGraphPort",
    "MemoryConsolidationGraphPort",
    "MemoryGraphPort",
    "MilitaryGraphPort",
    "MoodGraphPort",
    "NeedGraphPort",
    "PlanningGraphPort",
    "PlayerLocationReadPort",
    "PlayerModelGraphPort",
    "PledgeGraphPort",
    "PoliticalGraphPort",
    "ProactiveMemoryReadPort",
    "RelationPhaseWritePort",
    "RelationReadPort",
    "ReputationGraphPort",
    "RoutineGraphPort",
    "SkillGraphPort",
    "StoryPacingGraphPort",
    "TreatyGraphPort",
    "WorldStateGraphPort",
]
