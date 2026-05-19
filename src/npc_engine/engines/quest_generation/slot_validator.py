"""
Module: slot_validator
Layer: engines
Purpose: Validates proposed slot fills against the graph by checking node existence, type,
         and character skill thresholds for slots with REQUIRES_SKILL constraints.
Does NOT: call LLMs or write to the graph.
Dependencies: neo4j.AsyncSession, graph.skill_queries
Dependencies injected: AsyncSession (graph reader).
Used by: npc_engine.engines.quest_generation.quest_generation_engine
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from neo4j import AsyncSession

from npc_engine.engines.quest_generation.slot_models import SlotDefinition, SlotFill
from npc_engine.graph.skill_queries import check_skill_threshold

if TYPE_CHECKING:
    pass

_CYPHER_CHECK_NODE = "MATCH (n {id: $node_id}) RETURN labels(n) AS labels LIMIT 1"
_CYPHER_TEMPLATE_SKILL_REQS = """
MATCH (qt:QuestTemplate {id: $template_id})-[r:REQUIRES_SKILL]->(s:Skill)
RETURN s.id AS skill_id, toInteger(r.min_level) AS min_level
"""


class SlotValidator:
    """Validates slot fills by querying the graph for node existence and type."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise the validator with a live graph session.

        Args:
            session: Active Neo4j async session used for node look-ups.
        """
        self._session = session

    async def validate(
        self,
        fills: dict[str, str],
        slot_definitions: tuple[SlotDefinition, ...],
    ) -> list[str]:
        """Validate proposed slot fills against the graph.

        For each required slot, verifies the proposed node exists and carries
        the expected label. Optional slots are skipped when absent.

        Args:
            fills: Mapping of slot_name → node_id proposed by the LLM.
            slot_definitions: Slot definitions from the chosen template.

        Returns:
            List of violation strings; empty list means all fills are valid.
        """
        violations: list[str] = []
        for slot_def in slot_definitions:
            node_id = fills.get(slot_def.name)
            if node_id is None:
                if slot_def.required:
                    violations.append(f"required slot '{slot_def.name}' has no fill")
                continue
            node_labels = await self._get_labels(node_id)
            if node_labels is None:
                violations.append(
                    f"slot '{slot_def.name}' references non-existent node '{node_id}'"
                )
                continue
            expected = slot_def.node_type.lower()
            actual = {label.lower() for label in node_labels}
            if expected not in actual:
                violations.append(
                    f"slot '{slot_def.name}' node '{node_id}' has labels {sorted(actual)}"
                    f" but expected '{expected}'"
                )
        return violations

    async def check_skill_requirements(
        self,
        template_id: str,
        character_fills: dict[str, str],
    ) -> list[str]:
        """Check whether characters filling slots meet the template's skill requirements.

        Queries REQUIRES_SKILL edges from the QuestTemplate node. For each required skill,
        checks all character-type fills. Returns violations for any character that does not
        meet the minimum level.

        Args:
            template_id: ID of the QuestTemplate node in the graph.
            character_fills: Mapping of slot_name → character_id for character slots.

        Returns:
            List of violation strings; empty means all skill requirements are satisfied.
        """
        result = await self._session.run(_CYPHER_TEMPLATE_SKILL_REQS, template_id=template_id)
        requirements = [dict(r) async for r in result]
        if not requirements:
            return []
        violations: list[str] = []
        for req in requirements:
            skill_id = req["skill_id"]
            min_level = int(req["min_level"])
            for slot_name, character_id in character_fills.items():
                meets = await check_skill_threshold(
                    self._session,
                    character_id=character_id,
                    skill_id=skill_id,
                    min_level=min_level,
                )
                if not meets:
                    violations.append(
                        f"slot '{slot_name}' character '{character_id}' does not meet "
                        f"skill_threshold_not_met: skill='{skill_id}' min_level={min_level}"
                    )
        return violations

    async def _get_labels(self, node_id: str) -> list[str] | None:
        """Return labels for a node ID, or None if the node does not exist."""
        result = await self._session.run(_CYPHER_CHECK_NODE, node_id=node_id)
        records = [dict(r) async for r in result]
        if not records:
            return None
        return list(records[0].get("labels", []))

    def build_fills(
        self,
        raw: dict[str, str],
        slot_definitions: tuple[SlotDefinition, ...],
    ) -> tuple[SlotFill, ...]:
        """Convert a raw fill mapping into typed SlotFill tuples.

        Args:
            raw: Mapping of slot_name → node_id.
            slot_definitions: Slot definitions providing expected node_type.

        Returns:
            Tuple of SlotFill instances for all filled slots.
        """
        type_by_name = {s.name: s.node_type for s in slot_definitions}
        return tuple(
            SlotFill(slot_name=k, node_id=v, node_type=type_by_name.get(k, "unknown"))
            for k, v in raw.items()
        )
