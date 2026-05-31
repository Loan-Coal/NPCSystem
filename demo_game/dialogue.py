"""
Module: dialogue
Layer: demo_game
Purpose: Pure-logic helpers for the dialogue UI — payload building, response
         parsing, and degradation-level colour mapping. No Pygame, no HTTP.
Dependencies: dataclasses (stdlib only)
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_PROPOSAL_KINDS = frozenset({"propose_trade", "propose_quest", "claim_completion", "give_item"})


@dataclass(frozen=True)
class InteractionProposal:
    """Interaction proposal extracted from a DialogueResponse action field.

    Attributes:
        kind: Action type — one of the proposal-class types.
        target_id: Optional graph node ID the action targets.
        payload: Raw parameters dict from ActionModel.parameters.
    """

    kind: str
    target_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DialogueTurn:
    """Parsed result of one POST /v1/dialogue round-trip.

    Attributes:
        npc_text: The NPC's reply (from raw field ``npc_response``).
        degradation_level: Retrieval tier — ``"full"``, ``"graph_only"``,
            or ``"canned"``.
        emotion: Mood string from ``mood_update``, falling back to
            ``facial_expression.type`` when ``mood_update`` is None.
        relation_deltas: Trust/fear/affection deltas from this turn (or zeros).
        interaction_proposal: Non-None when the NPC surfaced a proposal action.
    """

    npc_text: str
    degradation_level: str
    emotion: str | None
    relation_deltas: dict[str, int] = field(default_factory=dict)
    interaction_proposal: InteractionProposal | None = None


# Colour constants for the degradation badge (RGB tuples).
# NOTE: engine returns lowercase values ("full", not "FULL").
DEGRADATION_COLORS: dict[str, tuple[int, int, int]] = {
    "full": (0, 200, 80),        # green
    "graph_only": (240, 160, 0), # amber
    "canned": (220, 50, 50),     # red
}

_GREY: tuple[int, int, int] = (128, 128, 128)


def build_dialogue_payload(
    npc_id: str,
    player_input: str,
    *,
    player_id: str,
    location_id: str | None = None,
    explicit_node_ids: tuple[str, ...] = (),
) -> dict:
    """Build keyword-argument dict for ``EngineClient.post_dialogue``.

    The returned dict can be unpacked directly:
    ``client.post_dialogue(**build_dialogue_payload(...))``.

    Args:
        npc_id: ID of the NPC being addressed.
        player_input: What the player typed.
        player_id: Fixed player identifier (e.g. ``"player_demo"``).
        location_id: Current location ID, or None.
        explicit_node_ids: Graph node IDs to pin as high-priority context.

    Returns:
        Dict with keys: player_id, npc_id, player_message, location_id,
        explicit_node_ids.
    """
    return {
        "player_id": player_id,
        "npc_id": npc_id,
        "player_message": player_input,
        "location_id": location_id,
        "explicit_node_ids": explicit_node_ids,
    }


def parse_dialogue_response(raw: dict) -> DialogueTurn:
    """Parse a flat DialogueResponse dict into a ``DialogueTurn``.

    Field mapping from engine response:
    - ``npc_response`` → ``DialogueTurn.npc_text``
    - ``degradation_level`` → ``DialogueTurn.degradation_level``
    - ``mood_update`` → ``DialogueTurn.emotion`` (fallback: ``facial_expression.type``)
    - ``action`` → ``DialogueTurn.interaction_proposal`` (proposal-class actions only)
    - ``relation_deltas`` → ``DialogueTurn.relation_deltas``

    Args:
        raw: Flat dict as returned by ``POST /v1/dialogue``.

    Returns:
        Immutable ``DialogueTurn`` with parsed fields.
    """
    mood: str | None = raw.get("mood_update")
    if mood is None:
        expression = raw.get("facial_expression") or {}
        mood = expression.get("type") or None

    action = raw.get("action") or {}
    kind = action.get("type", "speak")
    proposal: InteractionProposal | None = None
    if kind in _PROPOSAL_KINDS:
        proposal = InteractionProposal(
            kind=kind,
            target_id=action.get("target_id"),
            payload=action.get("parameters") or {},
        )

    raw_deltas = raw.get("relation_deltas") or {}
    deltas: dict[str, int] = {
        "trust": int(raw_deltas.get("trust", 0)),
        "fear": int(raw_deltas.get("fear", 0)),
        "affection": int(raw_deltas.get("affection", 0)),
    }

    return DialogueTurn(
        npc_text=raw["npc_response"],
        degradation_level=raw.get("degradation_level", "full"),
        emotion=mood,
        relation_deltas=deltas,
        interaction_proposal=proposal,
    )


def degradation_color(level: str) -> tuple[int, int, int]:
    """Return the RGB badge colour for a degradation level string.

    Args:
        level: One of ``"full"``, ``"graph_only"``, ``"canned"``.

    Returns:
        RGB tuple. Unknown values return grey ``(128, 128, 128)`` rather
        than raising, so the UI never crashes on unexpected engine output.
    """
    return DEGRADATION_COLORS.get(level, _GREY)
