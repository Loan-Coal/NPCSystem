"""
Package: quest_generation
Layer: engines
Purpose: LLM-powered quest generation with slot-filling, graph validation, and retry logic.
Does NOT: expose HTTP routes or manage quest lifecycle state transitions.
Dependencies injected: LLMStructuredProtocol, SlotValidator, list[QuestTemplateRecord].
Public surface: QuestGenerationEngine, QuestTemplateRecord, GeneratedQuest, SlotDefinition, SlotFill
"""

from __future__ import annotations
