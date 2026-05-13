"""
Module: quest_generation_engine
Layer: engines
Purpose: Orchestrates quest generation: template selection, LLM slot-filling with retry,
         graph validation, flavor text generation, and quest node persistence.
Does NOT: expose HTTP routes or manage quest lifecycle state transitions.
Dependencies: engines.quest_generation.slot_models, engines.quest_generation.slot_validator,
              engines.quest_generation.template_loader, engines.llm.protocols,
              graph.quest_node_service, common.yaml_utils
Dependencies injected: LLMClientProtocol, SlotValidator factory, list[QuestTemplateRecord].
Used by: npc_engine.api.routes.quest_generation
"""

from __future__ import annotations

import json
import logging
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import AsyncSession

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.engines.quest_generation.slot_models import (
    GeneratedQuest,
    QuestTemplateRecord,
    SlotDefinition,
    SlotFill,
)
from npc_engine.engines.quest_generation.slot_validator import SlotValidator
from npc_engine.graph.quest_node_service import create_quest

_logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_CYPHER_GET_CHARACTER = "MATCH (c:Character {id: $character_id}) RETURN c.archetype AS archetype, c.name AS name"
_CYPHER_GET_NODES_BY_TYPE = "MATCH (n:{label}) RETURN n.id AS id LIMIT 20"


def _load_prompt(prompt_path: Path) -> dict[str, str]:
    """Load a prompt YAML file, returning system and user_template strings."""
    return load_yaml_mapping(prompt_path, f"prompt file {prompt_path.name} must be a YAML mapping")


class QuestGenerationEngine:
    """Generates quests via LLM slot-filling with graph validation and retry logic."""

    def __init__(
        self,
        llm_client: LLMClientProtocol,
        templates: list[QuestTemplateRecord],
        prompts_dir: Path,
    ) -> None:
        """Initialise the quest generation engine.

        Args:
            llm_client: LLM adapter for slot-fill and flavor text generation.
            templates: Pre-loaded quest template records.
            prompts_dir: Path to the quest_generation prompts directory.
        """
        self._llm = llm_client
        self._templates = templates
        self._slot_fill_prompt = _load_prompt(prompts_dir / "slot_fill_v1.yaml")
        self._flavor_prompt = _load_prompt(prompts_dir / "flavor_v1.yaml")

    async def generate(
        self,
        session: AsyncSession,
        quest_giver_id: str,
    ) -> GeneratedQuest:
        """Generate a quest for the given quest giver.

        Selects a template by archetype, asks the LLM to fill slots (retrying
        up to 3 times on validation failure), then asks the LLM to generate
        flavor text. Writes the quest node and HAS_QUEST edge to the graph.

        Args:
            session: Active Neo4j async session.
            quest_giver_id: ID of the Character node that will give the quest.

        Returns:
            GeneratedQuest with the new quest_id, template_id, fills, and description.

        Raises:
            ValueError: If no template exists for the giver's archetype or the
                character node is not found.
        """
        archetype, giver_name = await self._get_character_info(session, quest_giver_id)
        template = self._select_template(archetype)
        validator = SlotValidator(session=session)

        fills_raw, fills = await self._fill_slots(session, template, validator)
        description = await self._generate_flavor(template, fills_raw, giver_name, template.description_template)

        quest_id = str(uuid.uuid4())
        fill_target = fills_raw.get("target") or fills_raw.get("item")
        payload: dict[str, Any] = {
            "quest_id": quest_id,
            "description": description,
            "quest_giver_id": quest_giver_id,
            "target_id": fills_raw.get("target") or fills_raw.get("item"),
            "reward_id": None,
            "success_condition": f"Complete the {template.name} quest",
            "failure_condition": None,
            "status": "offered",
            "severity": template.severity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }
        await create_quest(session, payload)

        return GeneratedQuest(
            quest_id=quest_id,
            template_id=template.id,
            fills=fills,
            description=description,
        )

    async def _get_character_info(
        self,
        session: AsyncSession,
        character_id: str,
    ) -> tuple[str, str]:
        """Fetch archetype and name for a character node."""
        result = await session.run(_CYPHER_GET_CHARACTER, character_id=character_id)
        records = [dict(r) async for r in result]
        if not records:
            raise ValueError(f"Character '{character_id}' not found in graph")
        row = records[0]
        return str(row.get("archetype") or "default"), str(row.get("name") or character_id)

    def _select_template(self, archetype: str) -> QuestTemplateRecord:
        """Select a template matching the archetype, falling back to any available."""
        matches = [t for t in self._templates if t.archetype == archetype]
        pool = matches if matches else self._templates
        if not pool:
            raise ValueError("No quest templates available")
        return random.choice(pool)

    async def _fill_slots(
        self,
        session: AsyncSession,
        template: QuestTemplateRecord,
        validator: SlotValidator,
    ) -> tuple[dict[str, str], tuple[SlotFill, ...]]:
        """Try LLM slot-filling up to _MAX_RETRIES times, then fall back deterministically."""
        candidates = await self._get_candidates(session, template.slot_definitions)
        violation_context = ""

        for attempt in range(_MAX_RETRIES):
            fills_raw = await self._ask_llm_for_fills(template, candidates, violation_context)
            violations = await validator.validate(fills_raw, template.slot_definitions)
            if not violations:
                fills = validator.build_fills(fills_raw, template.slot_definitions)
                return fills_raw, fills
            violation_context = "Previous violations: " + "; ".join(violations)
            _logger.warning(
                "quest_generation fill attempt %d/%d violations: %s",
                attempt + 1,
                _MAX_RETRIES,
                violations,
            )

        # Deterministic fallback: pick random valid nodes from graph
        _logger.warning("quest_generation falling back to deterministic slot fill")
        fills_raw = await self._deterministic_fill(session, template.slot_definitions, candidates)
        fills = validator.build_fills(fills_raw, template.slot_definitions)
        return fills_raw, fills

    async def _ask_llm_for_fills(
        self,
        template: QuestTemplateRecord,
        candidates: dict[str, list[str]],
        violation_context: str,
    ) -> dict[str, str]:
        """Call LLM for slot fills; return empty dict on any error."""
        slot_defs_text = json.dumps(
            [{"name": s.name, "node_type": s.node_type, "required": s.required}
             for s in template.slot_definitions]
        )
        candidates_text = json.dumps(candidates)
        user_prompt = self._slot_fill_prompt["user_template"].format(
            template_name=template.name,
            slot_definitions=slot_defs_text,
            candidates=candidates_text + (" " + violation_context if violation_context else ""),
        )
        system = self._slot_fill_prompt.get("system", "")
        try:
            schema = {
                "type": "object",
                "additionalProperties": {"type": "string"},
            }
            result = await self._llm.generate_structured(
                prompt=user_prompt,
                schema=schema,
                max_tokens=256,
                system=system,
            )
            return {str(k): str(v) for k, v in result.items() if isinstance(v, str)}
        except Exception:
            _logger.exception("LLM slot-fill call failed")
            return {}

    async def _generate_flavor(
        self,
        template: QuestTemplateRecord,
        fills_raw: dict[str, str],
        giver_name: str,
        default_description: str,
    ) -> str:
        """Call LLM for flavor text; return template default on any error."""
        user_prompt = self._flavor_prompt["user_template"].format(
            template_name=template.name,
            fills=json.dumps(fills_raw),
            giver_name=giver_name,
        )
        system = self._flavor_prompt.get("system", "")
        try:
            schema = {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "npc_plea": {"type": "string"},
                },
                "required": ["description", "npc_plea"],
            }
            result = await self._llm.generate_structured(
                prompt=user_prompt,
                schema=schema,
                max_tokens=256,
                system=system,
            )
            return str(result.get("description") or default_description)
        except Exception:
            _logger.warning("LLM flavor generation failed; using template default")
            return default_description

    async def _get_candidates(
        self,
        session: AsyncSession,
        slot_definitions: tuple[SlotDefinition, ...],
    ) -> dict[str, list[str]]:
        """Query the graph for candidate node IDs for each slot type."""
        candidates: dict[str, list[str]] = {}
        seen_types: set[str] = set()
        for slot_def in slot_definitions:
            node_type = slot_def.node_type
            if node_type in seen_types:
                continue
            seen_types.add(node_type)
            label = node_type.capitalize()
            cypher = f"MATCH (n:{label}) RETURN n.id AS id LIMIT 20"
            result = await session.run(cypher)
            ids = [str(r["id"]) async for r in result if r.get("id") is not None]
            candidates[node_type] = ids
        return candidates

    async def _deterministic_fill(
        self,
        session: AsyncSession,
        slot_definitions: tuple[SlotDefinition, ...],
        candidates: dict[str, list[str]],
    ) -> dict[str, str]:
        """Pick random valid nodes from candidates for each slot."""
        fills: dict[str, str] = {}
        for slot_def in slot_definitions:
            pool = candidates.get(slot_def.node_type, [])
            if pool:
                fills[slot_def.name] = random.choice(pool)
            elif slot_def.required:
                _logger.warning(
                    "No candidates for required slot '%s' (type=%s); using placeholder",
                    slot_def.name,
                    slot_def.node_type,
                )
                fills[slot_def.name] = f"unknown_{slot_def.node_type}"
        return fills
