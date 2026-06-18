"""
Module: quest_generation_port
Layer: engines
Purpose: Structural Protocols for the quest-generation graph domain — context assembly,
         quest persistence, slot validation, and trigger reads. Engines import these ports
         and hold no Neo4j session; the adapters in graph/repositories/ own sessions.
Does NOT: open sessions, run Cypher, call LLMs, or contain engine logic.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.quest_generation.*, npc_engine.engines.quest_generation.slot_validator.
"""

from __future__ import annotations

from typing import Protocol, Any


class QuestGenerationGraphPort(Protocol):
    """All graph reads/writes needed by QuestGenerationEngine and SlotValidator."""

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
