"""
Module: test_dialogue_logic
Layer: demo_game (tests)
Purpose: TDD unit tests for dialogue.py — payload builders, response parser,
         degradation color mapping. No Pygame, no HTTP, no engine required.
Dependencies: demo_game.dialogue
Used by: make test-demo
"""

from __future__ import annotations

import pytest

from demo_game.dialogue import (
    DEGRADATION_COLORS,
    DialogueTurn,
    build_dialogue_payload,
    degradation_color,
    parse_dialogue_response,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_response(
    *,
    npc_response: str = "Hello, traveller.",
    degradation_level: str = "full",
    mood_update: str | None = "calm",
    facial_expression_type: str = "neutral",
    facial_expression_intensity: int = 0,
) -> dict:
    """Build a minimal fake DialogueResponse dict for parse tests."""
    return {
        "npc_response": npc_response,
        "degradation_level": degradation_level,
        "mood_update": mood_update,
        "facial_expression": {
            "type": facial_expression_type,
            "intensity": facial_expression_intensity,
        },
        "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
        "action": {"type": "speak", "target_id": None, "parameters": {}},
        "session_id": "player_demo:mira_innkeeper",
        "cached": False,
    }


# ---------------------------------------------------------------------------
# build_dialogue_payload
# ---------------------------------------------------------------------------


def test_build_dialogue_payload_returns_correct_shape() -> None:
    payload = build_dialogue_payload(
        "mira_innkeeper",
        "Good morning!",
        player_id="player_demo",
    )
    assert payload["npc_id"] == "mira_innkeeper"
    assert payload["player_message"] == "Good morning!"
    assert payload["player_id"] == "player_demo"
    assert "location_id" in payload
    assert "explicit_node_ids" in payload


def test_build_dialogue_payload_includes_location_id() -> None:
    payload = build_dialogue_payload(
        "captain_sorn",
        "Is the road safe?",
        player_id="player_demo",
        location_id="loc_guard_barracks",
    )
    assert payload["location_id"] == "loc_guard_barracks"


def test_build_dialogue_payload_allows_none_location() -> None:
    payload = build_dialogue_payload(
        "mira_innkeeper",
        "Hi",
        player_id="player_demo",
        location_id=None,
    )
    assert payload["location_id"] is None


def test_build_dialogue_payload_explicit_node_ids_defaults_to_empty() -> None:
    payload = build_dialogue_payload(
        "mira_innkeeper",
        "Hi",
        player_id="player_demo",
    )
    assert payload["explicit_node_ids"] == ()


# ---------------------------------------------------------------------------
# parse_dialogue_response — npc_text
# ---------------------------------------------------------------------------


def test_parse_dialogue_response_extracts_npc_text() -> None:
    raw = _raw_response(npc_response="Welcome to the tavern!")
    turn = parse_dialogue_response(raw)
    assert turn.npc_text == "Welcome to the tavern!"


# ---------------------------------------------------------------------------
# parse_dialogue_response — degradation_level
# ---------------------------------------------------------------------------


def test_parse_dialogue_response_extracts_degradation_level_full() -> None:
    turn = parse_dialogue_response(_raw_response(degradation_level="full"))
    assert turn.degradation_level == "full"


def test_parse_dialogue_response_extracts_degradation_level_graph_only() -> None:
    turn = parse_dialogue_response(_raw_response(degradation_level="graph_only"))
    assert turn.degradation_level == "graph_only"


def test_parse_dialogue_response_extracts_degradation_level_canned() -> None:
    turn = parse_dialogue_response(_raw_response(degradation_level="canned"))
    assert turn.degradation_level == "canned"


# ---------------------------------------------------------------------------
# parse_dialogue_response — emotion
# ---------------------------------------------------------------------------


def test_parse_dialogue_response_extracts_emotion_from_mood_update() -> None:
    raw = _raw_response(mood_update="cautious", facial_expression_type="frown")
    turn = parse_dialogue_response(raw)
    assert turn.emotion == "cautious"


def test_parse_dialogue_response_falls_back_to_facial_expression_when_mood_is_none() -> None:
    raw = _raw_response(mood_update=None, facial_expression_type="concerned")
    turn = parse_dialogue_response(raw)
    assert turn.emotion == "concerned"


def test_parse_dialogue_response_emotion_is_none_when_both_absent() -> None:
    raw = _raw_response(mood_update=None, facial_expression_type="neutral")
    raw["facial_expression"]["type"] = "neutral"
    turn = parse_dialogue_response(raw)
    # neutral is a valid fallback — emotion is the facial_expression type
    assert turn.emotion == "neutral"


# ---------------------------------------------------------------------------
# DialogueTurn is frozen (immutable)
# ---------------------------------------------------------------------------


def test_dialogue_turn_is_immutable() -> None:
    turn = parse_dialogue_response(_raw_response())
    with pytest.raises((AttributeError, TypeError)):
        turn.npc_text = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# degradation_color
# ---------------------------------------------------------------------------


def test_degradation_color_full_is_green() -> None:
    color = degradation_color("full")
    r, g, b = color
    assert g > r and g > b, "full should be green-dominant"
    assert color == DEGRADATION_COLORS["full"]


def test_degradation_color_graph_only_is_amber() -> None:
    color = degradation_color("graph_only")
    r, g, b = color
    assert r > b and g > b, "graph_only should be amber (red+green dominant over blue)"
    assert color == DEGRADATION_COLORS["graph_only"]


def test_degradation_color_canned_is_red() -> None:
    color = degradation_color("canned")
    r, g, b = color
    assert r > g and r > b, "canned should be red-dominant"
    assert color == DEGRADATION_COLORS["canned"]


def test_degradation_color_unknown_returns_grey() -> None:
    color = degradation_color("unknown_value")
    assert color == (128, 128, 128)


def test_degradation_color_empty_string_returns_grey() -> None:
    color = degradation_color("")
    assert color == (128, 128, 128)
