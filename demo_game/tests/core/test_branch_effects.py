"""
Module: test_branch_effects
Layer: demo_game (tests)
Purpose: Unit tests for all BranchEffect subclasses. Verifies each effect's
         apply() calls the correct EngineClient mock method with the correct
         arguments. GotoBeatEffect is tested as a no-op.
Dependencies: demo_game.branches.branch_effects, unittest.mock, pytest
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.branches.branch_effects import (
    BranchEffect,
    GotoBeatEffect,
    OfferQuestEffect,
    RepDeltaEffect,
    SetBeliefEffect,
    WorldStateEffect,
)


def _mock_client() -> MagicMock:
    """Return a MagicMock with all relevant EngineClient methods."""
    client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_all_effect_types_conform_to_protocol() -> None:
    """All concrete effect classes satisfy the BranchEffect protocol."""
    effects = [
        RepDeltaEffect("npc_a", "faction_x", 10, "loc_tavern", 1),
        SetBeliefEffect("npc_a", "The war is coming", 80, {"year": 1}),
        WorldStateEffect("war", ("siege",)),
        OfferQuestEffect("quest_1", "choice_a", "player_1"),
        GotoBeatEffect("beat_ending"),
    ]
    for effect in effects:
        assert isinstance(effect, BranchEffect)


# ---------------------------------------------------------------------------
# RepDeltaEffect
# ---------------------------------------------------------------------------


def test_rep_delta_effect_calls_adjust_npc_reputation() -> None:
    """RepDeltaEffect.apply calls adjust_npc_reputation with correct args."""
    client = _mock_client()
    effect = RepDeltaEffect(
        character_id="garrick_deserter",
        faction_id="city_guard",
        delta=20,
        location_id="loc_tavern",
        tick_id=1,
    )
    effect.apply(client)
    client.adjust_npc_reputation.assert_called_once_with(
        "garrick_deserter", "city_guard", 20, "loc_tavern", 1
    )


def test_rep_delta_effect_negative_delta() -> None:
    """RepDeltaEffect works correctly with a negative delta."""
    client = _mock_client()
    effect = RepDeltaEffect("npc_a", "faction_b", -15, "loc_market_square", 2)
    effect.apply(client)
    client.adjust_npc_reputation.assert_called_once_with(
        "npc_a", "faction_b", -15, "loc_market_square", 2
    )


def test_rep_delta_effect_is_frozen() -> None:
    """RepDeltaEffect is a frozen dataclass (cannot be mutated)."""
    import dataclasses
    effect = RepDeltaEffect("npc", "faction", 5, "loc", 0)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        effect.delta = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SetBeliefEffect
# ---------------------------------------------------------------------------


def test_set_belief_effect_calls_post_belief() -> None:
    """SetBeliefEffect.apply calls post_belief with correct args."""
    client = _mock_client()
    game_time = {"year": 1, "season": "winter", "day": 1, "time_of_day": "morning"}
    effect = SetBeliefEffect(
        character_id="mira_innkeeper",
        content="The deserter was a good man",
        confidence=70,
        game_time=game_time,
        node_id="belief_mira_garrick",
    )
    effect.apply(client)
    client.post_belief.assert_called_once_with(
        "mira_innkeeper",
        "The deserter was a good man",
        70,
        game_time,
        node_id="belief_mira_garrick",
    )


def test_set_belief_effect_no_node_id() -> None:
    """SetBeliefEffect passes node_id=None when omitted."""
    client = _mock_client()
    game_time = {"year": 1}
    effect = SetBeliefEffect("npc_a", "content", 50, game_time)
    effect.apply(client)
    client.post_belief.assert_called_once_with(
        "npc_a", "content", 50, game_time, node_id=None
    )


# ---------------------------------------------------------------------------
# WorldStateEffect
# ---------------------------------------------------------------------------


def test_world_state_effect_calls_put_world_state() -> None:
    """WorldStateEffect.apply calls put_world_state with epoch and conditions."""
    client = _mock_client()
    effect = WorldStateEffect(epoch="war", active_conditions=("siege", "martial_law"))
    effect.apply(client)
    client.put_world_state.assert_called_once_with(
        "war", ["siege", "martial_law"]
    )


def test_world_state_effect_empty_conditions() -> None:
    """WorldStateEffect handles empty active_conditions tuple."""
    client = _mock_client()
    effect = WorldStateEffect(epoch="peace", active_conditions=())
    effect.apply(client)
    client.put_world_state.assert_called_once_with("peace", [])


# ---------------------------------------------------------------------------
# OfferQuestEffect
# ---------------------------------------------------------------------------


def test_offer_quest_effect_calls_post_quest_choice() -> None:
    """OfferQuestEffect.apply calls post_quest_choice with correct args."""
    client = _mock_client()
    effect = OfferQuestEffect(
        quest_id="quest_garrick", choice_id="spare", player_id="player_1"
    )
    effect.apply(client)
    client.post_quest_choice.assert_called_once_with(
        "quest_garrick", "spare", "player_1"
    )


# ---------------------------------------------------------------------------
# GotoBeatEffect
# ---------------------------------------------------------------------------


def test_goto_beat_effect_apply_is_noop() -> None:
    """GotoBeatEffect.apply does NOT call any client methods."""
    client = _mock_client()
    effect = GotoBeatEffect(target_beat_id="beat_ending_spare")
    effect.apply(client)
    client.adjust_npc_reputation.assert_not_called()
    client.post_belief.assert_not_called()
    client.put_world_state.assert_not_called()
    client.post_quest_choice.assert_not_called()


def test_goto_beat_effect_stores_target_beat_id() -> None:
    """GotoBeatEffect exposes target_beat_id attribute."""
    effect = GotoBeatEffect(target_beat_id="beat_spare_outcome")
    assert effect.target_beat_id == "beat_spare_outcome"
