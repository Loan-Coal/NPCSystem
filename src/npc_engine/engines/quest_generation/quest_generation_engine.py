"""
Module: quest_generation_engine
Layer: engines
Purpose: Orchestrates quest generation: template selection, LLM slot-filling with retry,
         graph validation, flavor text generation, and quest node persistence.
Does NOT: expose HTTP routes or manage quest lifecycle state transitions.
    Does NOT: hold a Neo4j session (DEC-122 / SEV-24).
Dependencies: engines.quest_generation.slot_models, engines.quest_generation.slot_validator,
              engines.quest_generation.template_loader, engines.llm.protocols,
              engines.ports.quest_generation_port, graph.generic_graph_utils (pure util).
Dependencies injected: LLMStructuredProtocol, QuestGenerationGraphPort,
    list[QuestTemplateRecord] (via __init__).
Used by: npc_engine.api.routes.quest_generation

NOTE: This file exceeds the 300-line hard limit (~390 lines). The additional
context-assembly delegation is one cohesive pipeline. Splitting into a
QuestContextAssembler would be natural in Phase 4 when more NPC context dimensions
are added. See DECISIONS.md "quest_generation_engine.py line limit (S3.1)".
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.llm.protocols import LLMStructuredProtocol
from npc_engine.engines.ports.quest_generation_port import QuestGenerationGraphPort
from npc_engine.engines.quest_generation.slot_models import (
    GeneratedQuest,
    QuestTemplateRecord,
    SlotDefinition,
    SlotFill,
)
from npc_engine.engines.quest_generation.slot_validator import SlotValidator
from npc_engine.graph.generic_graph_utils import resolve_node_label
from npc_engine.utils.errors import LLMRequestError, LLMTimeoutError

_logger = logging.getLogger(__name__)

_QUEST_SEED_NAMESPACE = "quest_generation"
_MAX_RETRIES = 3


def _quest_rng_seed(quest_giver_id: str, world_day: int) -> int:
    """Derive a deterministic integer seed for quest-generation RNG.

    Reproducible for the same (giver, world_day) pair; different pairs or
    days produce different seeds so quest content varies.

    Args:
        quest_giver_id: ID of the NPC initiating the quest.
        world_day: Current world day (from WorldState.day).

    Returns:
        A 64-bit integer seed suitable for ``random.Random(seed)``.
    """
    raw = f"{_QUEST_SEED_NAMESPACE}|{quest_giver_id}|{world_day}"
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8], byteorder="little")


def _load_prompt(prompt_path: Path) -> dict[str, str]:
    """Load a prompt YAML file, returning system and user_template strings."""
    return load_yaml_mapping(prompt_path, f"prompt file {prompt_path.name} must be a YAML mapping")


class QuestGenerationEngine:
    """Generates quests via LLM slot-filling with graph validation and retry logic."""

    def __init__(
        self,
        llm_client: LLMStructuredProtocol,
        templates: list[QuestTemplateRecord],
        prompts_dir: Path,
        max_tokens: int = 256,
        quest_gen_repo: QuestGenerationGraphPort | None = None,
    ) -> None:
        """Initialise the quest generation engine.

        Args:
            llm_client: LLM adapter for slot-fill and flavor text generation.
            templates: Pre-loaded quest template records.
            prompts_dir: Path to the quest_generation prompts directory.
            max_tokens: Maximum tokens to generate in LLM calls (sourced from llm_config.yaml).
            quest_gen_repo: Graph port for quest generation reads/writes (DEC-122 / SEV-24); required.

        Raises:
            ValueError: If quest_gen_repo is None.
        """
        if quest_gen_repo is None:
            raise ValueError("QuestGenerationEngine requires a QuestGenerationGraphPort injected via __init__")
        self._llm = llm_client
        self._templates = templates
        self._max_tokens = max_tokens
        self._slot_fill_prompt = _load_prompt(prompts_dir / "slot_fill_v2.yaml")
        self._flavor_prompt = _load_prompt(prompts_dir / "flavor_v2.yaml")
        self._quest_gen_repo = quest_gen_repo

    async def generate(
        self,
        quest_giver_id: str,
        cause_event_id: str | None = None,
    ) -> GeneratedQuest:
        """Generate a quest for the given quest giver.

        Selects a template by archetype, asks the LLM to fill slots (retrying
        up to 3 times on validation failure), then asks the LLM to generate
        flavor text. Writes the quest node and HAS_QUEST edge to the graph.

        Args:
            quest_giver_id: ID of the Character node that will give the quest.
            cause_event_id: When provided, writes a CAUSED_BY edge from the new quest
                to this event ID (narrative causation, strength=80).

        Returns:
            GeneratedQuest with the new quest_id, template_id, fills, and description.

        Raises:
            ValueError: If no template exists for the giver's archetype or the
                character node is not found.
        """
        world_day, quest_generation_rate = await self._quest_gen_repo.get_world_state_day_and_rate()
        quest_seed = _quest_rng_seed(quest_giver_id, world_day)
        rng = random.Random(quest_seed)
        _logger.debug("quest_rng seed=%d giver=%s world_day=%d", quest_seed, quest_giver_id, world_day)
        if quest_generation_rate < 1.0 and rng.random() > quest_generation_rate:
            raise ValueError(
                f"Quest generation suppressed by pacing engine (rate={quest_generation_rate:.2f})"
            )
        world_state_context = await self._quest_gen_repo.get_world_state_context()
        archetype, giver_name = await self._quest_gen_repo.get_character_info(character_id=quest_giver_id)
        giver_context: dict[str, Any] = {
            **await self._quest_gen_repo.get_giver_context(character_id=quest_giver_id),
            "world_state": world_state_context,
        }
        template = self._select_template(archetype, rng=rng)
        validator = SlotValidator(quest_gen_repo=self._quest_gen_repo)

        fills_raw, fills = await self._fill_slots(template, validator, giver_name=giver_name, archetype=archetype, giver_context=giver_context, rng=rng)
        description = await self._generate_flavor(template, fills_raw, giver_name, template.description_template, giver_context)

        quest_id = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "quest_id": quest_id,
            "description": description,
            "quest_giver_id": quest_giver_id,
            "target_id": fills_raw.get("target") or fills_raw.get("item"),
            "reward_id": None,
            "success_condition": f"Complete the {template.name} quest",
            "failure_condition": None,
            "status": "draft",
            "severity": template.severity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "source": "generated",
        }
        await self._quest_gen_repo.create_quest(payload=payload)
        if cause_event_id is not None:
            await self._quest_gen_repo.record_causation(
                effect_node_id=quest_id,
                effect_node_type="quest",
                cause_event_id=cause_event_id,
                causation_strength=80,
                cause_type="narrative",
                tick_lag=0,
            )

        return GeneratedQuest(
            quest_id=quest_id,
            template_id=template.id,
            fills=fills,
            description=description,
        )

    def _format_npc_context(self, giver_context: dict[str, Any]) -> str:
        """Serialize giver context to a structured text block for v2 prompts."""
        return "\n".join([
            f"GIVER_MOOD: {giver_context.get('mood', 'neutral')}",
            f"GIVER_NEEDS: {json.dumps(giver_context.get('needs', []))}",
            f"GIVER_GOALS: {json.dumps(giver_context.get('goals', []))}",
            f"GIVER_BELIEFS: {json.dumps(giver_context.get('beliefs', []))}",
            f"GIVER_INVENTORY: {json.dumps(giver_context.get('inventory', []))}",
            f"GIVER_LOCATION: {giver_context.get('location', 'unknown')}",
            f"GIVER_FACTION: {json.dumps(giver_context.get('faction', []))}",
            f"WORLD_STATE: {json.dumps(giver_context.get('world_state', {}))}",
        ])

    def _select_template(self, archetype: str, rng: random.Random | None = None) -> QuestTemplateRecord:
        """Select a template matching the archetype, falling back to any available."""
        matches = [t for t in self._templates if t.archetype == archetype]
        pool = matches if matches else self._templates
        if not pool:
            raise ValueError("No quest templates available")
        _rng = rng if rng is not None else random.Random()
        return _rng.choice(pool)

    async def _fill_slots(
        self,
        template: QuestTemplateRecord,
        validator: SlotValidator,
        *,
        giver_name: str = "",
        archetype: str = "",
        giver_context: dict[str, Any] | None = None,
        rng: random.Random | None = None,
    ) -> tuple[dict[str, str], tuple[SlotFill, ...]]:
        """Try LLM slot-filling up to _MAX_RETRIES times, then fall back deterministically."""
        candidates = await self._get_candidates(template.slot_definitions)
        violation_context = ""

        for attempt in range(_MAX_RETRIES):
            fills_raw = await self._ask_llm_for_fills(
                template, candidates, violation_context,
                giver_name=giver_name, archetype=archetype, giver_context=giver_context,
            )
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

        _logger.warning("quest_generation falling back to deterministic slot fill")
        fills_raw = self._deterministic_fill(template.slot_definitions, candidates, rng=rng)
        fills = validator.build_fills(fills_raw, template.slot_definitions)
        return fills_raw, fills

    async def _ask_llm_for_fills(
        self,
        template: QuestTemplateRecord,
        candidates: dict[str, list[str]],
        violation_context: str,
        *,
        giver_name: str = "",
        archetype: str = "",
        giver_context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Call LLM for slot fills; return empty dict on any error."""
        slot_defs_text = json.dumps(
            [{"name": s.name, "node_type": s.node_type, "required": s.required}
             for s in template.slot_definitions]
        )
        candidates_text = json.dumps(candidates)
        giver_ctx_text = ""
        if giver_context:
            giver_ctx_text = (
                f"GIVER: {giver_name} (archetype: {archetype})\n"
                + self._format_npc_context(giver_context)
            )
        violation_prefix = f"PREVIOUS_VIOLATIONS: {violation_context}\n" if violation_context else ""
        user_prompt = self._slot_fill_prompt["user_template"].format(
            template_name=template.name,
            slot_definitions=slot_defs_text,
            candidates=candidates_text,
            giver_context=giver_ctx_text,
            violation_context=violation_prefix,
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
                max_tokens=self._max_tokens,
                system=system,
            )
            return {str(k): str(v) for k, v in result.items() if isinstance(v, str)}
        except (LLMTimeoutError, LLMRequestError) as error:
            _logger.warning("LLM error during slot fill: %s", error)
            return {}
        except ValidationError as error:
            _logger.warning("Schema validation error during slot fill: %s", error)
            return {}

    async def _generate_flavor(
        self,
        template: QuestTemplateRecord,
        fills_raw: dict[str, str],
        giver_name: str,
        default_description: str,
        giver_context: dict[str, Any] | None = None,
    ) -> str:
        """Call LLM for flavor text grounded in NPC context; return template default on any error."""
        giver_ctx_text = self._format_npc_context(giver_context) if giver_context else ""
        user_prompt = self._flavor_prompt["user_template"].format(
            template_name=template.name,
            fills=json.dumps(fills_raw),
            giver_name=giver_name,
            giver_context=giver_ctx_text,
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
                max_tokens=self._max_tokens,
                system=system,
            )
            return str(result.get("description") or default_description)
        except (LLMTimeoutError, LLMRequestError) as error:
            _logger.warning("LLM error during flavor generation: %s", error)
            return default_description
        except ValidationError as error:
            _logger.warning("Schema validation error during flavor generation: %s", error)
            return default_description

    async def _get_candidates(
        self,
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
            label = resolve_node_label(node_type)
            ids = await self._quest_gen_repo.get_candidate_ids_by_label(label=label)
            candidates[node_type] = ids
        return candidates

    def _deterministic_fill(
        self,
        slot_definitions: tuple[SlotDefinition, ...],
        candidates: dict[str, list[str]],
        rng: random.Random | None = None,
    ) -> dict[str, str]:
        """Pick random valid nodes from candidates for each slot."""
        _rng = rng if rng is not None else random.Random()
        fills: dict[str, str] = {}
        for slot_def in slot_definitions:
            pool = candidates.get(slot_def.node_type, [])
            if pool:
                fills[slot_def.name] = _rng.choice(pool)
            elif slot_def.required:
                _logger.warning(
                    "No candidates for required slot '%s' (type=%s); using placeholder",
                    slot_def.name,
                    slot_def.node_type,
                )
                fills[slot_def.name] = f"unknown_{slot_def.node_type}"
        return fills
