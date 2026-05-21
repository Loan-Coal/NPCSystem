"""
Module: renderer
Layer: demo_game.graph_panel
Purpose: Render a GraphSnapshot onto a Pygame Surface using networkx layout
         and matplotlib. STUB — full implementation in Phase 2.4.
Dependencies: networkx, matplotlib, pygame (all installed via requirements.txt)
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.graph_panel.fetcher import GraphDelta, GraphSnapshot


def render_snapshot(
    snapshot: GraphSnapshot,
    surface: object,
    delta: GraphDelta | None = None,
) -> None:
    """Render a GraphSnapshot onto a pygame.Surface.

    Nodes are colored by type. Edge thickness reflects relationship weight.
    New edges from delta are highlighted yellow for two render cycles.

    Args:
        snapshot: Current graph snapshot to render.
        surface: Target pygame.Surface to blit onto.
        delta: Optional delta; new edges are highlighted yellow.

    Raises:
        NotImplementedError: Full implementation arrives in Phase 2.4.
    """
    raise NotImplementedError("render_snapshot() will be implemented in Phase 2.4")
