"""
test_quest_generation_engine.py - Unit tests for quest generation: template loader,
slot validator, and generation engine with LLM mocking.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.quest_generation.slot_models import (
    GeneratedQuest,
    QuestTemplateRecord,
    SlotDefinition,
)
from npc_engine.engines.quest_generation.slot_validator import SlotValidator
from npc_engine.engines.quest_generation.template_loader import load_templates
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.utils.errors import LLMRequestError


# ---------------------------------------------------------------------------
# Mock quest gen repo factory
# ---------------------------------------------------------------------------


def _make_quest_gen_repo(
    node_labels: dict[str, list[str] | None] | None = None,
    archetype: str = "merchant",
    name: str = "Bob",
    giver_context: dict | None = None,
    candidate_ids: list[str] | None = None,
) -> Any:
    """Return a mock QuestGenerationGraphPort with configurable returns."""
    repo = MagicMock()
    _labels = node_labels or {}
    _giver_ctx: dict[str, Any] = giver_context or {
        "goals": [], "beliefs": [], "mood": "neutral", "mood_intensity": 0,
        "needs": [], "inventory": [], "location": "tavern", "faction": [],
    }

    async def _check_node_labels(*, node_id: str) -> list[str] | None:
        return _labels.get(node_id)

    repo.check_node_labels = _check_node_labels
    repo.get_template_skill_requirements = AsyncMock(return_value=[])
    repo.check_skill_threshold = AsyncMock(return_value=True)
    repo.get_world_state_day_and_rate = AsyncMock(return_value=(1, 1.0))
    repo.get_world_state_context = AsyncMock(return_value="Year 1, Season: spring")
    repo.get_character_info = AsyncMock(return_value=(archetype, name))
    repo.get_giver_context = AsyncMock(return_value=_giver_ctx)
    repo.get_candidate_ids_by_label = AsyncMock(return_value=candidate_ids or [])
    repo.create_quest = AsyncMock(return_value={})
    repo.record_causation = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Test 1: template_loader loads real YAML files
# ---------------------------------------------------------------------------


def test_template_loader_loads_yaml() -> None:
    templates_dir = (
        Path(__file__).resolve().parent.parent.parent
        / "src" / "npc_engine" / "prompts" / "quest_generation" / "templates"
    )
    templates = load_templates(templates_dir)
    assert len(templates) >= 2
    for t in templates:
        assert t.id
        assert t.name
        assert t.archetype
        assert isinstance(t.severity, int)
        assert t.description_template
        assert t.reward_template
        assert len(t.slot_definitions) >= 1


# ---------------------------------------------------------------------------
# Test 2: slot_validator accepts valid fills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slot_validator_accepts_valid_fills() -> None:
    repo = _make_quest_gen_repo(node_labels={"item_001": ["Item"]})
    validator = SlotValidator(quest_gen_repo=repo)
    slot_defs = (SlotDefinition(name="item", node_type="item", required=True),)
    violations = await validator.validate({"item": "item_001"}, slot_defs)
    assert violations == []


# ---------------------------------------------------------------------------
# Test 3: slot_validator rejects fills with wrong node type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slot_validator_rejects_wrong_type() -> None:
    repo = _make_quest_gen_repo(node_labels={"char_001": ["Character"]})
    validator = SlotValidator(quest_gen_repo=repo)
    slot_defs = (SlotDefinition(name="item", node_type="item", required=True),)
    violations = await validator.validate({"item": "char_001"}, slot_defs)
    assert len(violations) == 1
    assert "item" in violations[0]


# ---------------------------------------------------------------------------
# Helpers for engine tests
# ---------------------------------------------------------------------------


def _make_template(archetype: str = "merchant") -> QuestTemplateRecord:
    return QuestTemplateRecord(
        id="fetch_item_v1",
        name="Fetch Item",
        archetype=archetype,
        severity=20,
        slot_definitions=(
            SlotDefinition(name="item", node_type="item", required=True),
        ),
        description_template="Retrieve {item} from somewhere.",
        reward_template="10 gold coins",
    )


def _make_engine(
    llm_client: Any,
    templates: list[QuestTemplateRecord] | None = None,
    prompts_dir: Path | None = None,
    quest_gen_repo: Any = None,
) -> QuestGenerationEngine:
    if templates is None:
        templates = [_make_template()]
    if prompts_dir is None:
        prompts_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "npc_engine" / "prompts" / "quest_generation"
        )
    if quest_gen_repo is None:
        quest_gen_repo = _make_quest_gen_repo(
            node_labels={"item_001": ["Item"]},
            candidate_ids=["item_001"],
        )
    return QuestGenerationEngine(
        llm_client=llm_client,
        templates=templates,
        prompts_dir=prompts_dir,
        quest_gen_repo=quest_gen_repo,
    )


# ---------------------------------------------------------------------------
# Test 4: generate succeeds on first try — LLM returns valid fills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_succeeds_on_first_try() -> None:
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="merchant",
        name="Bob",
        candidate_ids=["item_001"],
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "item_001"},
            {"description": "Go get the sword!", "npc_plea": "Please hurry!"},
        ]
    )

    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.quest_id
    assert result.template_id == "fetch_item_v1"
    assert result.description == "Go get the sword!"
    assert llm_client.generate_structured.call_count == 2


# ---------------------------------------------------------------------------
# Test 5: generate retries on validation violation, succeeds on third attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_retries_on_violation() -> None:
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"bad_node": ["Character"], "item_001": ["Item"]},
        archetype="merchant",
        name="Bob",
        candidate_ids=["item_001"],
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "bad_node"},
            {"item": "bad_node"},
            {"item": "item_001"},
            {"description": "Find the item.", "npc_plea": "Please!"},
        ]
    )

    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.quest_id
    assert llm_client.generate_structured.call_count == 4


# ---------------------------------------------------------------------------
# Test 6: generate falls back to deterministic after max retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_falls_back_after_max_retries() -> None:
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={},
        archetype="merchant",
        name="Bob",
        candidate_ids=["item_001"],
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "nonexistent_001"},
            {"item": "nonexistent_002"},
            {"item": "nonexistent_003"},
            {"description": "Find it!", "npc_plea": "Go!"},
        ]
    )

    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.quest_id


# ---------------------------------------------------------------------------
# Test 7: generate uses template defaults when flavor LLM call fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_uses_template_defaults_on_flavor_error() -> None:
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="merchant",
        name="Bob",
        candidate_ids=["item_001"],
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "item_001"},
            LLMRequestError(model="mock", detail="LLM flavor error"),
        ]
    )

    template = _make_template()
    engine = _make_engine(llm_client, templates=[template], quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.description == template.description_template


# ---------------------------------------------------------------------------
# Test 8: generate writes Quest node with status="draft" (not "offered")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_writes_draft_status() -> None:
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="merchant",
        name="Bob",
        candidate_ids=["item_001"],
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "item_001"},
            {"description": "Gather the herbs!", "npc_plea": "Please hurry!"},
        ]
    )
    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    await engine.generate(quest_giver_id="giver_001")

    quest_gen_repo.create_quest.assert_awaited_once()
    call_kwargs = quest_gen_repo.create_quest.call_args.kwargs
    assert call_kwargs["payload"]["status"] == "draft"


# ---------------------------------------------------------------------------
# Test 9: slot-fill prompt includes GIVER_NEEDS when NPC has needs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_includes_needs_in_slot_fill_prompt() -> None:
    giver_context = {
        "goals": [], "beliefs": [], "mood": "neutral", "mood_intensity": 0,
        "needs": [{"kind": "supply", "level": 15}],
        "inventory": [], "location": "tavern", "faction": [],
    }
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="merchant",
        name="Bob",
        giver_context=giver_context,
        candidate_ids=["item_001"],
    )

    captured_prompts: list[str] = []

    async def capture_llm(prompt: str, schema: Any, max_tokens: int, system: str = "") -> dict:
        captured_prompts.append(prompt)
        if len(captured_prompts) == 1:
            return {"item": "item_001"}
        return {"description": "Find supplies!", "npc_plea": "We need supplies!"}

    llm_client = MagicMock()
    llm_client.generate_structured = capture_llm

    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert len(captured_prompts) >= 1
    slot_fill_prompt = captured_prompts[0]
    assert "supply" in slot_fill_prompt, "Expected need kind 'supply' in slot-fill prompt"
    assert "GIVER_NEEDS" in slot_fill_prompt, "Expected GIVER_NEEDS label in slot-fill prompt"


# ---------------------------------------------------------------------------
# Test 10: slot-fill prompt includes GIVER_LOCATION when NPC has a location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_includes_location_in_slot_fill_prompt() -> None:
    giver_context = {
        "goals": [], "beliefs": [], "mood": "neutral", "mood_intensity": 0,
        "needs": [], "inventory": [], "location": "guard_barracks", "faction": [],
    }
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="guard_captain",
        name="Sorn",
        giver_context=giver_context,
        candidate_ids=["item_001"],
    )

    captured_prompts: list[str] = []

    async def capture_llm(prompt: str, schema: Any, max_tokens: int, system: str = "") -> dict:
        captured_prompts.append(prompt)
        if len(captured_prompts) == 1:
            return {"item": "item_001"}
        return {"description": "Patrol the barracks!", "npc_plea": "We need help!"}

    llm_client = MagicMock()
    llm_client.generate_structured = capture_llm

    template = _make_template(archetype="guard_captain")
    engine = _make_engine(llm_client, templates=[template], quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    slot_fill_prompt = captured_prompts[0]
    assert "guard_barracks" in slot_fill_prompt, "Expected location 'guard_barracks' in slot-fill prompt"
    assert "GIVER_LOCATION" in slot_fill_prompt, "Expected GIVER_LOCATION label in slot-fill prompt"


# ---------------------------------------------------------------------------
# Test 11: flavor prompt includes NPC context (needs + location)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_includes_npc_context_in_flavor_prompt() -> None:
    giver_context = {
        "goals": [], "beliefs": [], "mood": "neutral", "mood_intensity": 0,
        "needs": [{"kind": "safety", "level": 10}],
        "inventory": [], "location": "market_square", "faction": [],
    }
    quest_gen_repo = _make_quest_gen_repo(
        node_labels={"item_001": ["Item"]},
        archetype="merchant",
        name="Alice",
        giver_context=giver_context,
        candidate_ids=["item_001"],
    )

    captured_prompts: list[str] = []

    async def capture_llm(prompt: str, schema: Any, max_tokens: int, system: str = "") -> dict:
        captured_prompts.append(prompt)
        if len(captured_prompts) == 1:
            return {"item": "item_001"}
        return {"description": "Secure the market!", "npc_plea": "We are not safe!"}

    llm_client = MagicMock()
    llm_client.generate_structured = capture_llm

    engine = _make_engine(llm_client, quest_gen_repo=quest_gen_repo)
    result = await engine.generate(quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert len(captured_prompts) >= 2
    flavor_prompt = captured_prompts[1]
    assert "safety" in flavor_prompt, "Expected need kind 'safety' in flavor prompt"
    assert "market_square" in flavor_prompt, "Expected location 'market_square' in flavor prompt"
