"""
Module: test_branch_node
Layer: demo_game (tests)
Purpose: Unit tests for BranchNode and BranchOption construction, validation,
         and apply_all dispatch. Tests the garrick_deserter first-slice authored
         branch constants.
Dependencies: demo_game.branch_node, demo_game.branch_effects, unittest.mock, pytest
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from demo_game.branch_effects import GotoBeatEffect, RepDeltaEffect
from demo_game.branch_node import (
    BRANCH_ID_GARRICK,
    OPTION_LABEL_SPARE,
    OPTION_LABEL_TURN_IN,
    BranchNode,
    BranchOption,
)


# ---------------------------------------------------------------------------
# BranchOption
# ---------------------------------------------------------------------------


def test_branch_option_construction() -> None:
    """BranchOption stores label and effects tuple."""
    effect = RepDeltaEffect("npc_a", "faction_x", 10, "loc_a", 1)
    option = BranchOption(label="Spare", effects=(effect,))
    assert option.label == "Spare"
    assert option.effects == (effect,)


def test_branch_option_apply_all_calls_each_effect() -> None:
    """apply_all calls apply() on each effect in order."""
    client = MagicMock()
    e1 = RepDeltaEffect("npc_a", "faction_x", 10, "loc_a", 1)
    e2 = RepDeltaEffect("npc_b", "faction_y", -5, "loc_b", 2)
    option = BranchOption(label="Mixed", effects=(e1, e2))
    option.apply_all(client)
    assert client.adjust_npc_reputation.call_count == 2
    client.adjust_npc_reputation.assert_any_call("npc_a", "faction_x", 10, "loc_a", 1)
    client.adjust_npc_reputation.assert_any_call("npc_b", "faction_y", -5, "loc_b", 2)


def test_branch_option_apply_all_empty_effects() -> None:
    """apply_all with no effects does not raise."""
    client = MagicMock()
    option = BranchOption(label="Pass", effects=())
    option.apply_all(client)  # should not raise


def test_branch_option_is_frozen() -> None:
    """BranchOption is a frozen dataclass."""
    import dataclasses
    effect = RepDeltaEffect("npc_a", "faction_x", 5, "loc_a", 0)
    option = BranchOption(label="Test", effects=(effect,))
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        option.label = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BranchNode
# ---------------------------------------------------------------------------


def test_branch_node_construction() -> None:
    """BranchNode stores branch_id, prompt_text, and options."""
    opt_a = BranchOption(label="A", effects=())
    opt_b = BranchOption(label="B", effects=())
    node = BranchNode(
        branch_id="branch_x",
        prompt_text="What do you do?",
        options=(opt_a, opt_b),
    )
    assert node.branch_id == "branch_x"
    assert node.prompt_text == "What do you do?"
    assert len(node.options) == 2


def test_branch_node_requires_at_least_two_options() -> None:
    """BranchNode raises ValueError when fewer than 2 options are provided."""
    opt_a = BranchOption(label="Only", effects=())
    with pytest.raises(ValueError, match="at least 2 options"):
        BranchNode(branch_id="bad", prompt_text="?", options=(opt_a,))


def test_branch_node_empty_options_raises() -> None:
    """BranchNode raises ValueError with an empty options tuple."""
    with pytest.raises(ValueError):
        BranchNode(branch_id="bad", prompt_text="?", options=())


def test_branch_node_is_frozen() -> None:
    """BranchNode is a frozen dataclass."""
    import dataclasses
    opt_a = BranchOption(label="A", effects=())
    opt_b = BranchOption(label="B", effects=())
    node = BranchNode(branch_id="n", prompt_text="q", options=(opt_a, opt_b))
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        node.branch_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Garrick first-slice authored branch
# ---------------------------------------------------------------------------


def test_garrick_branch_id_constant() -> None:
    """BRANCH_ID_GARRICK is the stable identifier for the garrick branch."""
    assert BRANCH_ID_GARRICK == "branch_garrick_deserter"


def test_garrick_option_labels_exist() -> None:
    """Spare and turn-in label constants are non-empty strings."""
    assert OPTION_LABEL_SPARE
    assert OPTION_LABEL_TURN_IN


def test_garrick_branch_can_be_constructed() -> None:
    """The garrick deserter branch can be built with two RepDeltaEffect options."""
    spare_effect = RepDeltaEffect(
        character_id="garrick_deserter",
        faction_id="thieves_guild",
        delta=15,
        location_id="loc_tavern",
        tick_id=1,
    )
    turn_in_effect = RepDeltaEffect(
        character_id="garrick_deserter",
        faction_id="city_guard",
        delta=20,
        location_id="loc_tavern",
        tick_id=1,
    )
    opt_spare = BranchOption(label=OPTION_LABEL_SPARE, effects=(spare_effect,))
    opt_turn_in = BranchOption(label=OPTION_LABEL_TURN_IN, effects=(turn_in_effect,))
    node = BranchNode(
        branch_id=BRANCH_ID_GARRICK,
        prompt_text=(
            "Garrick trembles before you. You know he deserted his post "
            "during the northern siege. The city guard is offering a reward. "
            "What do you do?"
        ),
        options=(opt_spare, opt_turn_in),
    )
    assert node.branch_id == BRANCH_ID_GARRICK
    assert len(node.options) == 2


def test_garrick_spare_applies_correct_faction() -> None:
    """Spare option's RepDeltaEffect targets the expected faction."""
    spare_effect = RepDeltaEffect(
        character_id="garrick_deserter",
        faction_id="thieves_guild",
        delta=15,
        location_id="loc_tavern",
        tick_id=1,
    )
    client = MagicMock()
    spare_effect.apply(client)
    client.adjust_npc_reputation.assert_called_once_with(
        "garrick_deserter", "thieves_guild", 15, "loc_tavern", 1
    )


def test_garrick_turn_in_applies_city_guard_faction() -> None:
    """Turn-in option's RepDeltaEffect targets city_guard."""
    turn_in_effect = RepDeltaEffect(
        character_id="garrick_deserter",
        faction_id="city_guard",
        delta=20,
        location_id="loc_tavern",
        tick_id=1,
    )
    client = MagicMock()
    turn_in_effect.apply(client)
    client.adjust_npc_reputation.assert_called_once_with(
        "garrick_deserter", "city_guard", 20, "loc_tavern", 1
    )


def test_build_garrick_branch_has_two_opposite_options() -> None:
    """build_garrick_branch returns the authored 2-option garrick fork (spare/turn-in)."""
    from demo_game.branch_node import (
        build_garrick_branch, BRANCH_ID_GARRICK, OPTION_LABEL_SPARE, OPTION_LABEL_TURN_IN,
    )

    node = build_garrick_branch()
    assert node.branch_id == BRANCH_ID_GARRICK
    assert len(node.options) == 2
    assert node.options[0].label == OPTION_LABEL_SPARE
    assert node.options[1].label == OPTION_LABEL_TURN_IN
    # each option carries exactly one effect
    assert len(node.options[0].effects) == 1
    assert len(node.options[1].effects) == 1
