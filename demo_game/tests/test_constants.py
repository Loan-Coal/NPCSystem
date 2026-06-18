"""
Module: test_constants
Layer: demo_game (tests)
Purpose: Invariant tests for demo_game.constants — data integrity checks.
Dependencies: demo_game.constants
Used by: make test-demo
"""

from __future__ import annotations

from demo_game.constants import (
    FACTION_COLOURS,
    LOCATION_TINTS,
    NPC_DISPLAY_NAMES,
    NPC_FACTIONS,
    PALETTE,
)


def test_npc_factions_keys_match_display_names() -> None:
    """NPC_FACTIONS must have exactly the same keys as NPC_DISPLAY_NAMES.

    Ensures every NPC in the demo world has a faction, and no phantom NPC
    IDs exist in NPC_FACTIONS that are absent from the display name registry.
    """
    assert set(NPC_FACTIONS.keys()) == set(NPC_DISPLAY_NAMES.keys()), (
        f"Mismatch: NPC_FACTIONS={set(NPC_FACTIONS.keys())} "
        f"NPC_DISPLAY_NAMES={set(NPC_DISPLAY_NAMES.keys())}"
    )


def test_npc_factions_all_values_are_known_factions() -> None:
    """Every faction value in NPC_FACTIONS must be a key in FACTION_COLOURS."""
    for npc_id, faction in NPC_FACTIONS.items():
        assert faction in FACTION_COLOURS, (
            f"{npc_id} has faction '{faction}' which is not in FACTION_COLOURS"
        )


def test_faction_colours_are_valid_rgb_tuples() -> None:
    """Every colour in FACTION_COLOURS is a 3-tuple with values in [0, 255]."""
    for faction, colour in FACTION_COLOURS.items():
        assert len(colour) == 3, f"{faction} colour is not a 3-tuple"
        for component in colour:
            assert 0 <= component <= 255, f"{faction} colour component {component} out of range"


# ---------------------------------------------------------------------------
# PALETTE
# ---------------------------------------------------------------------------

_REQUIRED_PALETTE_KEYS = {"bg", "amber", "white", "grey", "red", "green", "panel", "border"}


def test_palette_has_all_required_keys() -> None:
    """PALETTE must contain exactly the required set of keys."""
    missing = _REQUIRED_PALETTE_KEYS - set(PALETTE.keys())
    assert not missing, f"PALETTE is missing keys: {missing}"


def test_palette_values_are_valid_rgb_tuples() -> None:
    """Every value in PALETTE is a 3-tuple of ints in [0, 255]."""
    for key, colour in PALETTE.items():
        assert len(colour) == 3, f"PALETTE[{key!r}] is not a 3-tuple"
        for component in colour:
            assert isinstance(component, int), f"PALETTE[{key!r}] component {component!r} is not int"
            assert 0 <= component <= 255, f"PALETTE[{key!r}] component {component} out of range"


# ---------------------------------------------------------------------------
# LOCATION_TINTS
# ---------------------------------------------------------------------------

_REQUIRED_LOCATION_TINT_KEYS = {"loc_tavern", "loc_market_square", "loc_guard_barracks"}


def test_location_tints_has_all_demo_locations() -> None:
    """LOCATION_TINTS must cover every demo location."""
    missing = _REQUIRED_LOCATION_TINT_KEYS - set(LOCATION_TINTS.keys())
    assert not missing, f"LOCATION_TINTS is missing keys: {missing}"


def test_location_tints_values_are_valid_rgb_tuples() -> None:
    """Every value in LOCATION_TINTS is a 3-tuple of ints in [0, 255]."""
    for loc, colour in LOCATION_TINTS.items():
        assert len(colour) == 3, f"LOCATION_TINTS[{loc!r}] is not a 3-tuple"
        for component in colour:
            assert isinstance(component, int), f"LOCATION_TINTS[{loc!r}] component {component!r} is not int"
            assert 0 <= component <= 255, f"LOCATION_TINTS[{loc!r}] component {component} out of range"
