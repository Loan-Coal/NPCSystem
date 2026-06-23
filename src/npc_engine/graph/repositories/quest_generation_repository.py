"""
Module: quest_generation_repository
Layer: graph
Purpose: Neo4j adapters for quest-generation graph domain (context assembly, quest
         persistence, slot validation) and trigger read domains (event triggers,
         need triggers). Implements QuestGenerationGraphPort, EventTriggerGraphPort,
         and NeedTriggerGraphPort structurally.
Does NOT: contain LLM logic, run slot-fill retries, or import from engines/.
Dependencies injected: GraphDB.
Used by: api composition root (dependencies_engines.py).
"""

from __future__ import annotations

from typing import Any

from npc_engine.graph.knowledge.belief_queries import get_beliefs_for_character
from npc_engine.graph.knowledge.causality_service import record_causation
from npc_engine.graph.db import GraphDB
from npc_engine.graph.event.event_trigger_queries import (
    get_any_military_npc,
    get_military_npc_at_location,
    get_unprocessed_trigger_events,
)
from npc_engine.graph.needs_goals.goal_queries import get_goals_for_character
from npc_engine.graph.graph_reader import get_npc_location_id
from npc_engine.graph.group.group_service import get_groups_for_character_svc
from npc_engine.graph.item_queries import get_items_for_character
from npc_engine.graph.emotion.mood_queries import get_character_mood
from npc_engine.graph.needs_goals.need_queries import get_all_needs_below_threshold, get_needs_for_character
from npc_engine.graph.need_quest_queries import has_draft_quest
from npc_engine.graph.quest_generation_queries import (
    check_node_labels,
    get_candidate_ids_by_label,
    get_character_info,
    get_template_skill_requirements,
)
from npc_engine.graph.quest_node_service import create_quest
from npc_engine.graph.skill_queries import check_skill_threshold
from npc_engine.graph.world_state.world_state_reader import get_world_state


class Neo4jQuestGenerationRepository:
    """Session-per-call adapter for quest-generation graph reads/writes (QuestGenerationGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_world_state_day_and_rate(
        self, *, world_id: str = "world"
    ) -> tuple[int, float]:
        """Return (world_day, quest_generation_rate) from the WorldState node."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            ws = await get_world_state(session=session, world_id=world_id)
            return ws.day, ws.quest_generation_rate

    async def get_world_state_context(self, *, world_id: str = "world") -> dict[str, Any]:
        """Return {'epoch': str, 'active_conditions': list} for prompt context."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            ws = await get_world_state(session=session, world_id=world_id)
            return {"epoch": ws.epoch, "active_conditions": ws.active_conditions}

    async def get_character_info(self, *, character_id: str) -> tuple[str, str]:
        """Return (archetype, name) for a character node."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_character_info(session, character_id=character_id)

    async def get_giver_context(self, *, character_id: str) -> dict[str, Any]:
        """Return assembled giver context dict[str, Any] (goals, beliefs, mood, needs, inventory, location, faction)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            goals = await get_goals_for_character(session, character_id=character_id, k=3, status_filter="active")
            beliefs = await get_beliefs_for_character(session, character_id=character_id, k=3)
            mood = await get_character_mood(session, character_id=character_id)
            needs = await get_needs_for_character(session, character_id=character_id)
            inventory = await get_items_for_character(session, character_id=character_id, k=5)
            location_id = await get_npc_location_id(session, npc_id=character_id)
            groups = await get_groups_for_character_svc(session, character_id=character_id)
        return {
            "goals": [g.get("objective", "") for g in (goals or [])],
            "beliefs": [b.get("content", "") for b in (beliefs or [])],
            "mood": mood[0] if mood else "neutral",
            "needs": [{"kind": n.get("kind", ""), "level": n.get("level", 0)} for n in (needs or [])],
            "inventory": [i.get("id", "") for i in (inventory or []) if i.get("id")],
            "location": location_id or "unknown",
            "faction": [g.get("name", g.get("group_id", "")) for g in (groups or [])],
        }

    async def get_candidate_ids_by_label(self, *, label: str) -> list[str]:
        """Return all node IDs with the given graph label."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_candidate_ids_by_label(session, label=label)

    async def create_quest(self, *, payload: dict[str, Any]) -> None:
        """Persist a Quest node from the payload dict."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await create_quest(session, payload)

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
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            await record_causation(
                session,
                effect_node_id=effect_node_id,
                effect_node_type=effect_node_type,
                cause_event_id=cause_event_id,
                causation_strength=causation_strength,
                cause_type=cause_type,
                tick_lag=tick_lag,
            )

    async def check_node_labels(self, *, node_id: str) -> list[str] | None:
        """Return labels for a node ID, or None if the node does not exist."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await check_node_labels(session, node_id=node_id)

    async def get_template_skill_requirements(self, *, template_id: str) -> list[dict[str, Any]]:
        """Return REQUIRES_SKILL edge payloads for the given QuestTemplate node."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_template_skill_requirements(session, template_id=template_id)

    async def check_skill_threshold(
        self, *, character_id: str, skill_id: str, min_level: int
    ) -> bool:
        """Return True if the character meets the skill threshold."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await check_skill_threshold(
                session, character_id=character_id, skill_id=skill_id, min_level=min_level
            )


class Neo4jEventTriggerRepository:
    """Session-per-call adapter for event and world-state trigger reads (EventTriggerGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_unprocessed_trigger_events(
        self, trigger_types: frozenset[str], max_count: int
    ) -> list[dict[str, Any]]:
        """Return Event nodes whose type matches trigger_types with no CAUSED_BY quest yet."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_unprocessed_trigger_events(session, trigger_types, max_count)

    async def get_military_npc_at_location(
        self, *, location_id: str, archetypes: frozenset[str]
    ) -> str | None:
        """Return a character ID at the location whose archetype is in archetypes, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_military_npc_at_location(session, location_id, archetypes)

    async def get_any_military_npc(self, *, archetypes: frozenset[str]) -> str | None:
        """Return any character ID whose archetype is in archetypes, or None."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_any_military_npc(session, archetypes)


class Neo4jNeedTriggerRepository:
    """Session-per-call adapter for need trigger reads (NeedTriggerGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_all_needs_below_threshold(self, *, threshold: int) -> list[dict[str, Any]]:
        """Return Need nodes with level at or below threshold."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_all_needs_below_threshold(session, threshold=threshold)

    async def has_draft_quest(self, *, character_id: str) -> bool:
        """Return True if the character already has an outstanding draft quest."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await has_draft_quest(session, character_id)
