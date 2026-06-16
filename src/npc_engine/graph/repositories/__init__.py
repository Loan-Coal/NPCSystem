"""
Package: repositories
Layer: graph
Purpose: Neo4j-backed repository adapters that implement the engine-layer graph
         Ports (structural Protocols). Each adapter holds a GraphDB driver holder
         and opens a session per operation, so engines depend on an abstraction and
         never hold a Neo4j session — the swap seam for cache/alternate-DB/microservice
         backends (DEC-122 / SEV-24).
Does NOT: contain business/decay logic, call LLMs, or import the engines layer.
Dependencies injected: GraphDB (per adapter, at the api composition root).
Public surface: Neo4jNeedRepository, Neo4jMoodRepository, Neo4jGroupRepository,
                Neo4jSkillRepository, Neo4jChapterRepository, Neo4jMilitaryRepository,
                Neo4jRelationReadRepository, Neo4jPlayerLocationReadRepository,
                Neo4jCharacterReadRepository.
"""

from __future__ import annotations

from npc_engine.graph.repositories.chapter_repository import Neo4jChapterRepository
from npc_engine.graph.repositories.character_read_repository import (
    Neo4jCharacterReadRepository,
)
from npc_engine.graph.repositories.group_repository import Neo4jGroupRepository
from npc_engine.graph.repositories.memory_consolidation_repository import (
    Neo4jMemoryConsolidationRepository,
)
from npc_engine.graph.repositories.military_repository import Neo4jMilitaryRepository
from npc_engine.graph.repositories.mood_repository import Neo4jMoodRepository
from npc_engine.graph.repositories.need_repository import Neo4jNeedRepository
from npc_engine.graph.repositories.player_location_read_repository import (
    Neo4jPlayerLocationReadRepository,
)
from npc_engine.graph.repositories.pledge_repository import Neo4jPledgeRepository
from npc_engine.graph.repositories.political_repository import Neo4jPoliticalRepository
from npc_engine.graph.repositories.relation_read_repository import (
    Neo4jRelationReadRepository,
)
from npc_engine.graph.repositories.routine_repository import Neo4jRoutineRepository
from npc_engine.graph.repositories.skill_repository import Neo4jSkillRepository
from npc_engine.graph.repositories.story_pacing_repository import Neo4jStoryPacingRepository
from npc_engine.graph.repositories.treaty_repository import Neo4jTreatyRepository
from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository

__all__ = [
    "Neo4jChapterRepository",
    "Neo4jCharacterReadRepository",
    "Neo4jGroupRepository",
    "Neo4jMemoryConsolidationRepository",
    "Neo4jMilitaryRepository",
    "Neo4jMoodRepository",
    "Neo4jNeedRepository",
    "Neo4jPlayerLocationReadRepository",
    "Neo4jPledgeRepository",
    "Neo4jPoliticalRepository",
    "Neo4jRelationReadRepository",
    "Neo4jRoutineRepository",
    "Neo4jSkillRepository",
    "Neo4jStoryPacingRepository",
    "Neo4jTreatyRepository",
    "Neo4jWorldStateRepository",
]
