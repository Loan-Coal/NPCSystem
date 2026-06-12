"""
Module: branch_node
Layer: demo_game
Purpose: Pure data classes for the branch primitive. BranchNode is a fork
         construct containing a prompt and a list of BranchOptions, each
         carrying typed effects. Zero src/npc_engine imports.
Dependencies: dataclasses, demo_game.branch_effects
Used by: demo_game.scenarios, demo_game.ui.branch_panel,
         demo_game.tests.test_branch_node
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from demo_game.branch_effects import BranchEffect

if TYPE_CHECKING:
    from demo_game.client import EngineClient


@dataclass(frozen=True)
class BranchOption:
    """A single selectable option within a BranchNode.

    Each option carries a display label and a list of effects that are
    applied sequentially when the player selects this option.

    Attributes:
        label: Short human-readable label, e.g. "Spare the deserter".
        effects: Ordered sequence of BranchEffect instances applied on selection.
    """

    label: str
    effects: tuple[BranchEffect, ...]

    def apply_all(self, client: "EngineClient") -> None:
        """Apply every effect in sequence using the live EngineClient.

        Args:
            client: The EngineClient used to call the NPC Engine API.
        """
        for effect in self.effects:
            effect.apply(client)


@dataclass(frozen=True)
class BranchNode:
    """A fork construct presenting a prompt and two or more options to the player.

    BranchNode is pure data — it does not call the client directly.
    The scenario runner or UI layer calls option.apply_all(client) once the
    player has chosen.

    Attributes:
        branch_id: Stable identifier used to record the choice in BranchState.
        prompt_text: The narrative question or situation presented to the player.
        options: Ordered list of BranchOption instances (minimum 2).
    """

    branch_id: str
    prompt_text: str
    options: tuple[BranchOption, ...]

    def __post_init__(self) -> None:
        """Validate that the node has at least two options."""
        if len(self.options) < _MIN_OPTIONS:
            raise ValueError(
                f"BranchNode '{self.branch_id}' must have at least "
                f"{_MIN_OPTIONS} options; got {len(self.options)}."
            )


# Minimum options required per branch node.
_MIN_OPTIONS: int = 2


# ---------------------------------------------------------------------------
# First-slice authored content — garrick_deserter spare/turn-in branch
# ---------------------------------------------------------------------------

# Stable IDs used by seed data and BranchState records.
BRANCH_ID_GARRICK: str = "branch_garrick_deserter"
OPTION_LABEL_SPARE: str = "Spare the deserter"
OPTION_LABEL_TURN_IN: str = "Turn him in to the City Guard"

# Rep delta magnitudes for the garrick branch.
_GARRICK_REP_DELTA_SPARE: int = 15
_GARRICK_REP_DELTA_TURN_IN: int = 20

# Location and tick used for garrick reputation events.
_GARRICK_LOCATION_ID: str = "loc_tavern"
_GARRICK_TICK_ID: int = 1
