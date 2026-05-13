"""
test_quest_generation_engine.py - Unit tests for quest generation: template loader,
slot validator, and generation engine with LLM mocking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.quest_generation.slot_models import (
    GeneratedQuest,
    QuestTemplateRecord,
    SlotDefinition,
    SlotFill,
)
from npc_engine.engines.quest_generation.slot_validator import SlotValidator
from npc_engine.engines.quest_generation.template_loader import load_templates
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine


# ---------------------------------------------------------------------------
# Async session fakes
# ---------------------------------------------------------------------------


@dataclass
class _AsyncIter:
    _items: list[Any]
    _idx: int = field(default=0, init=False)

    def __aiter__(self) -> "_AsyncIter":
        return self

    async def __anext__(self) -> Any:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


@dataclass
class _FakeResult:
    _records: list[dict]

    def __aiter__(self) -> _AsyncIter:
        return _AsyncIter(self._records)


class _FakeSessionWithNodes:
    """Session stub that returns preconfigured node records by query content."""

    def __init__(self, node_map: dict[str, dict | None]) -> None:
        self._node_map = node_map
        self.write_calls: list[tuple] = []

    async def run(self, query: str, **kwargs: Any) -> _FakeResult:
        node_id = kwargs.get("node_id") or kwargs.get("character_id") or kwargs.get("quest_id")
        if node_id in self._node_map:
            val = self._node_map[node_id]
            if val is None:
                return _FakeResult([])
            return _FakeResult([val])
        if "Character" in query and "archetype" in query:
            char_id = kwargs.get("character_id")
            result = self._node_map.get(char_id)
            if result is None:
                return _FakeResult([])
            return _FakeResult([result])
        return _FakeResult([])

    async def begin_transaction(self) -> "_FakeTx":
        return _FakeTx(self)


class _FakeTx:
    def __init__(self, session: _FakeSessionWithNodes) -> None:
        self._session = session

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def run(self, query: str, **kwargs: Any) -> _FakeResult:
        self._session.write_calls.append((query, kwargs))
        return _FakeResult([])


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
    node_map = {
        "item_001": {"labels": ["Item"]},
    }
    session = _FakeSessionWithNodes(node_map)
    validator = SlotValidator(session=session)
    slot_defs = (SlotDefinition(name="item", node_type="item", required=True),)
    violations = await validator.validate({"item": "item_001"}, slot_defs)
    assert violations == []


# ---------------------------------------------------------------------------
# Test 3: slot_validator rejects fills with wrong node type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slot_validator_rejects_wrong_type() -> None:
    node_map = {
        "char_001": {"labels": ["Character"]},
    }
    session = _FakeSessionWithNodes(node_map)
    validator = SlotValidator(session=session)
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
) -> QuestGenerationEngine:
    if templates is None:
        templates = [_make_template()]
    if prompts_dir is None:
        prompts_dir = (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "npc_engine" / "prompts" / "quest_generation"
        )
    return QuestGenerationEngine(
        llm_client=llm_client,
        templates=templates,
        prompts_dir=prompts_dir,
    )


# ---------------------------------------------------------------------------
# Test 4: generate succeeds on first try — LLM returns valid fills
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_succeeds_on_first_try() -> None:
    session = _FakeSessionWithNodes(
        node_map={
            "giver_001": {"archetype": "merchant", "name": "Bob"},
            "item_001": {"labels": ["Item"]},
        }
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "item_001"},
            {"description": "Go get the sword!", "npc_plea": "Please hurry!"},
        ]
    )

    engine = _make_engine(llm_client)
    result = await engine.generate(session=session, quest_giver_id="giver_001")

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
    session = _FakeSessionWithNodes(
        node_map={
            "giver_001": {"archetype": "merchant", "name": "Bob"},
            "bad_node": {"labels": ["Character"]},
            "item_001": {"labels": ["Item"]},
        }
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

    engine = _make_engine(llm_client)
    result = await engine.generate(session=session, quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.quest_id
    assert llm_client.generate_structured.call_count == 4


# ---------------------------------------------------------------------------
# Test 6: generate falls back to deterministic after max retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_falls_back_after_max_retries() -> None:
    class _DeterministicSession(_FakeSessionWithNodes):
        async def run(self, query: str, **kwargs: Any) -> _FakeResult:
            if "archetype" in query or "name" in query:
                char_id = kwargs.get("character_id")
                val = self._node_map.get(char_id)
                if val is None:
                    return _FakeResult([])
                return _FakeResult([val])
            if "MATCH (n:Item)" in query:
                return _FakeResult([{"id": "item_001"}])
            node_id = kwargs.get("node_id")
            val = self._node_map.get(node_id) if node_id else None
            return _FakeResult([val] if val else [])

    session = _DeterministicSession(
        node_map={
            "giver_001": {"archetype": "merchant", "name": "Bob"},
        }
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

    engine = _make_engine(llm_client)
    result = await engine.generate(session=session, quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.quest_id


# ---------------------------------------------------------------------------
# Test 7: generate uses template defaults when flavor LLM call fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_uses_template_defaults_on_flavor_error() -> None:
    session = _FakeSessionWithNodes(
        node_map={
            "giver_001": {"archetype": "merchant", "name": "Bob"},
            "item_001": {"labels": ["Item"]},
        }
    )

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(
        side_effect=[
            {"item": "item_001"},
            Exception("LLM flavor error"),
        ]
    )

    template = _make_template()
    engine = _make_engine(llm_client, templates=[template])
    result = await engine.generate(session=session, quest_giver_id="giver_001")

    assert isinstance(result, GeneratedQuest)
    assert result.description == template.description_template
