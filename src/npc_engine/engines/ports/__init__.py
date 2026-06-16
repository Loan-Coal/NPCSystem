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
                WorldStateGraphPort.
"""

from __future__ import annotations

from npc_engine.engines.ports.group_port import GroupGraphPort
from npc_engine.engines.ports.mood_port import MoodGraphPort
from npc_engine.engines.ports.need_port import NeedGraphPort
from npc_engine.engines.ports.political_port import PoliticalGraphPort
from npc_engine.engines.ports.routine_port import RoutineGraphPort
from npc_engine.engines.ports.skill_port import SkillGraphPort
from npc_engine.engines.ports.story_pacing_port import StoryPacingGraphPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort

__all__ = [
    "GroupGraphPort",
    "MoodGraphPort",
    "NeedGraphPort",
    "PoliticalGraphPort",
    "RoutineGraphPort",
    "SkillGraphPort",
    "StoryPacingGraphPort",
    "WorldStateGraphPort",
]
