"""
Module: quest_generation_port
Layer: engines
Purpose: Structural Protocols for the quest-generation graph domain split by consumer
         role — context assembly / quest persistence for QuestGenerationEngine, slot
         validation reads for SlotValidator, and trigger reads for the three trigger
         classes. Engines import these ports and hold no Neo4j session; the adapters
         in graph/repositories/ own sessions.
Does NOT: open sessions, run Cypher, call LLMs, or contain engine logic.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.quest_generation.quest_generation_engine (QuestContextGraphPort),
         npc_engine.engines.quest_generation.slot_validator (SlotValidationGraphPort),
         npc_engine.engines.quest_generation.event_quest_trigger (EventTriggerGraphPort),
         npc_engine.engines.quest_generation.world_state_quest_trigger (EventTriggerGraphPort),
         npc_engine.engines.quest_generation.need_quest_trigger (NeedTriggerGraphPort).
"""

from __future__ import annotations

from typing import Protocol, Any


class QuestContextGraphPort(Protocol):
    """Graph reads and writes used directly by QuestGenerationEngine."""

    async def get_world_state_day_and_rate(
        self, *, world_id: str = "world"
    ) -> tuple[int, float]:
        """Return (world_day, quest_generation_rate) from the WorldState node."""
        ...

    async def get_world_state_context(
        self, *, world_id: str = "world"
    ) -> dict[str, Any]:
        """Return {'epoch': str, 'active_conditions': list} for prompt context."""
        ...

    async def get_character_info(self, *, character_id: str) -> tuple[str, str]:
        """Return (archetype, name) for a character node."""
        ...

    async def get_giver_context(self, *, character_id: str) -> dict[str, Any]:
        """Return assembled giver context dict[str, Any] (goals, beliefs, mood, needs, inventory, location, faction)."""
        ...

    async def get_candidate_ids_by_label(self, *, label: str) -> list[str]:
        """Return all node IDs with the given graph label."""
        ...

    async def create_quest(self, *, payload: dict[str, Any]) -> None:
        """Persist a Quest node from the payload dict."""
        ...

    async def record_causation(
        self,
        *,
        effect_node_id: str,
        effect_node_type: str,
        cause_event_id: str,
        causation_strength: int,
        cause_type: str,
        tick_lag: int,
    ) -> None:
        """Write a CAUSED_BY edge from effect to cause event."""
        ...


class SlotValidationGraphPort(Protocol):
    """Graph reads used by SlotValidator to check node existence and skill thresholds."""

    async def check_node_labels(self, *, node_id: str) -> list[str] | None:
        """Return labels for a node ID, or None if the node does not exist."""
        ...

    async def get_template_skill_requirements(
        self, *, template_id: str
    ) -> list[dict[str, Any]]:
        """Return REQUIRES_SKILL edge payloads for the given QuestTemplate node."""
        ...

    async def check_skill_threshold(
        self, *, character_id: str, skill_id: str, min_level: int
    ) -> bool:
        """Return True if the character meets the skill threshold."""
        ...


class EventTriggerGraphPort(Protocol):
    """Graph reads for EventQuestTrigger and WorldStateQuestTrigger."""

    async def get_unprocessed_trigger_events(
        self, trigger_types: frozenset[str], max_count: int
    ) -> list[dict[str, Any]]:
        """Return Event nodes whose type matches trigger_types with no CAUSED_BY quest yet."""
        ...

    async def get_military_npc_at_location(
        self, *, location_id: str, archetypes: frozenset[str]
    ) -> str | None:
        """Return a character ID at the location whose archetype is in archetypes, or None."""
        ...

    async def get_any_military_npc(
        self, *, archetypes: frozenset[str]
    ) -> str | None:
        """Return any character ID whose archetype is in archetypes, or None."""
        ...

    async def has_draft_quest(self, *, character_id: str) -> bool:
        """Return True if the character already has an outstanding draft quest."""
        ...


class NeedTriggerGraphPort(Protocol):
    """Graph reads for NeedQuestTrigger."""

    async def get_all_needs_below_threshold(
        self, *, threshold: int
    ) -> list[dict[str, Any]]:
        """Return Need nodes with level at or below threshold."""
        ...

    async def has_draft_quest(self, *, character_id: str) -> bool:
        """Return True if the character already has an outstanding draft quest."""
        ...
