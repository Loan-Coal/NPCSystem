"""
Module: branch_effects
Layer: demo_game
Purpose: Typed branch effects for BranchOption. Each effect class is a frozen
         dataclass that implements the BranchEffect protocol. Adding a new effect
         type = creating a new class here (OCP — never edit existing effect classes).
         Effects call ONLY existing EngineClient methods.
Dependencies: typing, dataclasses
Used by: demo_game.branches.branch_node, demo_game.tests.test_branch_effects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from demo_game.client import EngineClient

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class BranchEffect(Protocol):
    """Protocol implemented by every branch effect class.

    apply() is called with the live EngineClient once the player confirms a
    BranchOption.  Control-flow effects (GotoBeatEffect) do NOT call the
    client; they carry metadata only.
    """

    def apply(self, client: "EngineClient") -> None:  # noqa: D102
        ...


# ---------------------------------------------------------------------------
# Concrete effect classes (frozen dataclasses — one per effect type)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepDeltaEffect:
    """Apply a standing delta between a character and a faction.

    Calls client.adjust_npc_reputation(character_id, faction_id, delta,
    location_id, tick_id).

    Attributes:
        character_id: Character node ID whose reputation changes.
        faction_id: Faction node ID.
        delta: Signed standing delta (positive = gain, negative = loss).
        location_id: Location where the standing change occurred (for gossip seed).
        tick_id: Current game tick at which the change occurs.
    """

    character_id: str
    faction_id: str
    delta: int
    location_id: str
    tick_id: int

    def apply(self, client: "EngineClient") -> None:
        """Apply reputation delta via EngineClient.adjust_npc_reputation."""
        client.adjust_npc_reputation(
            self.character_id,
            self.faction_id,
            self.delta,
            self.location_id,
            self.tick_id,
        )


@dataclass(frozen=True)
class SetBeliefEffect:
    """Create or update a belief on a character node.

    Calls client.post_belief(character_id, content, confidence, game_time).

    Attributes:
        character_id: Character node ID.
        content: Belief text (1–512 chars).
        confidence: Confidence level (0–100).
        game_time: Dict with year, season, day, time_of_day keys.
        node_id: Optional stable node ID for idempotent re-seeding.
    """

    character_id: str
    content: str
    confidence: int
    game_time: dict
    node_id: str | None = None

    def apply(self, client: "EngineClient") -> None:
        """Create a belief via EngineClient.post_belief."""
        client.post_belief(
            self.character_id,
            self.content,
            self.confidence,
            self.game_time,
            node_id=self.node_id,
        )


@dataclass(frozen=True)
class WorldStateEffect:
    """Flip the world state epoch and/or active conditions.

    Calls client.put_world_state(epoch, active_conditions).

    Attributes:
        epoch: New epoch string, e.g. "war" or "peace".
        active_conditions: List of active condition IDs.
    """

    epoch: str
    active_conditions: tuple[str, ...]

    def apply(self, client: "EngineClient") -> None:
        """Update world state via EngineClient.put_world_state."""
        client.put_world_state(self.epoch, list(self.active_conditions))


@dataclass(frozen=True)
class OfferQuestEffect:
    """Record the player's choice for a branching quest node.

    Calls client.post_quest_choice(quest_id, choice_id, player_id).

    Attributes:
        quest_id: Quest node ID.
        choice_id: Chosen branch identifier.
        player_id: Player character ID.
    """

    quest_id: str
    choice_id: str
    player_id: str

    def apply(self, client: "EngineClient") -> None:
        """Post a quest branch choice via EngineClient.post_quest_choice."""
        client.post_quest_choice(self.quest_id, self.choice_id, self.player_id)


@dataclass(frozen=True)
class GotoBeatEffect:
    """Control-flow metadata that redirects the scenario to a named beat.

    GotoBeatEffect carries no side-effects; the scenario runner reads
    target_beat_id from the chosen option and jumps to the named beat.
    apply() is intentionally a no-op.

    Attributes:
        target_beat_id: ID of the scenario beat to jump to after this option.
    """

    target_beat_id: str

    def apply(self, client: "EngineClient") -> None:
        """No-op — GotoBeatEffect is control-flow metadata only."""
