"""
Package: knowledge_learning
Layer: engines
Purpose: Engine for extracting and persisting player-stated facts as NPC belief nodes.
Public surface: KnowledgeExtractionEngine, KnowledgeExtractionResult, LearnedFact
"""

from npc_engine.engines.knowledge_learning.models import (
    KnowledgeExtractionResult,
    LearnedFact,
)
from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
    KnowledgeExtractionEngine,
)

__all__ = [
    "KnowledgeExtractionEngine",
    "KnowledgeExtractionResult",
    "LearnedFact",
]
