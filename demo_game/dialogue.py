"""
Module: dialogue
Layer: demo_game
Purpose: Pure-logic helpers for the dialogue UI — payload building, response
         parsing, and degradation-level colour mapping. No Pygame, no HTTP.
Dependencies: dataclasses (stdlib only)
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DialogueTurn:
    """Parsed result of one POST /v1/dialogue round-trip.

    Attributes:
        npc_text: The NPC's reply (from raw field ``npc_response``).
        degradation_level: Retrieval tier — ``"full"``, ``"graph_only"``,
            or ``"canned"``.
        emotion: Mood string from ``mood_update``, falling back to
            ``facial_expression.type`` when ``mood_update`` is None.
    """

    npc_text: str
    degradation_level: str
    emotion: str | None


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

    Args:
        raw: Flat dict as returned by ``POST /v1/dialogue``.

    Returns:
        Immutable ``DialogueTurn`` with parsed fields.
    """
    mood: str | None = raw.get("mood_update")
    if mood is None:
        expression = raw.get("facial_expression") or {}
        mood = expression.get("type") or None

    return DialogueTurn(
        npc_text=raw["npc_response"],
        degradation_level=raw.get("degradation_level", "full"),
        emotion=mood,
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
