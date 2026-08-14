"""
Module: test_prompt_determinism
Layer: retrieval (test)
Purpose: Guard CLAUDE.md's strict "Idempotent assembly" rule — no wall-clock value may
         reach prompt content. Measured 2026-08-14 during EVAL-P20.0: of 145 eval records
         whose only between-run difference was `world.last_updated_at` plus
         `emotion_updated_at_tick`, 36 of 36 produced DIFFERENT npc_response text. Two
         fields carrying no dialogue signal were sufficient on their own to destroy
         reproducibility, and with it ~81% of the 393 human labels at every regeneration.
Dependencies: npc_engine.retrieval.context (context_utils, context_builder).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from npc_engine.retrieval.context.context_builder import _build_tier0_items
from npc_engine.retrieval.context.context_utils import (
    NON_PROMPT_NODE_FIELDS,
    serialize_json,
)


#: Field names that are wall-clock values or derived from them. None of these may appear
#: anywhere in serialized prompt content, at any nesting depth.
_WALL_CLOCK_FIELDS = (
    "created_at",
    "updated_at",
    "last_updated_at",
    "last_graph_updated_at",
    "last_embedding_indexed_at",
    "emotion_updated_at_tick",
    "expires_at_tick",
)


class _FakeWorldState(BaseModel):
    """Minimal stand-in carrying the fields the real world state leaks."""

    id: str = "world"
    epoch: str = "war"
    active_conditions: list[str] = ["northern_war"]
    last_updated_at: str = "2026-08-14T13:01:57.129000Z"
    last_graph_updated_at: str = "2026-06-23T06:40:00.468676Z"


def test_wall_clock_fields_are_all_declared_non_prompt() -> None:
    """Every known wall-clock field is on the strip list."""
    missing = [f for f in _WALL_CLOCK_FIELDS if f not in NON_PROMPT_NODE_FIELDS]
    assert missing == [], f"wall-clock fields missing from NON_PROMPT_NODE_FIELDS: {missing}"


def test_strip_removes_wall_clock_fields_at_any_depth() -> None:
    """routine_override nests its tick one level down; a flat strip would miss it."""
    payload = {
        "emotion_valence": 98,
        "emotion_updated_at_tick": 1786712528,
        "routine_override": {"location_id": "home", "expires_at_tick": 1786712533},
    }
    result = json.loads(serialize_json(payload, strip_fields=NON_PROMPT_NODE_FIELDS))

    assert "emotion_updated_at_tick" not in result
    assert "expires_at_tick" not in result["routine_override"]
    # Semantic content must survive — stripping is about wall-clock noise, not state.
    assert result["emotion_valence"] == 98
    assert result["routine_override"]["location_id"] == "home"


def test_tier0_world_item_carries_no_wall_clock_value() -> None:
    """The pinned Tier-0 world item is dumped into every prompt; it must be timestamp-free.

    This is the regression for the measured defect: context_builder previously called
    world_state.model_dump_json() with no field stripping at all.
    """
    items = _build_tier0_items(_FakeWorldState(), {"valence": 0, "arousal": 0})
    world_item = next(item for item in items if item.key == "world")
    payload = json.loads(world_item.text)

    for field in _WALL_CLOCK_FIELDS:
        assert field not in payload, f"{field} leaked into the Tier-0 world prompt item"
    # The world item must still carry the state the NPC reasons about.
    assert payload["epoch"] == "war"
    assert payload["active_conditions"] == ["northern_war"]


def test_tier0_world_item_is_byte_stable_across_wall_clock_change() -> None:
    """Two world states differing only in wall-clock fields serialize identically.

    Byte equality is the property that makes a regeneration reproduce text and lets
    human labels survive it.
    """
    early = _FakeWorldState(last_updated_at="2026-08-14T13:01:57.129000Z")
    later = _FakeWorldState(last_updated_at="2026-08-14T13:04:39.225000Z")

    text_early = next(i for i in _build_tier0_items(early, {}) if i.key == "world").text
    text_later = next(i for i in _build_tier0_items(later, {}) if i.key == "world").text

    assert text_early == text_later
