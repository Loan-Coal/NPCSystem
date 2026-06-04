"""
Module: knowledge_sidebar_fetcher
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Fetches KNOWS_ABOUT edge data and corresponding ground-truth Event nodes
         for a given NPC. Returns paired tuples ready for KnowledgeSidebarWidget.
Dependencies: demo_game.client
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import logging

from demo_game.client import EngineClient

_logger = logging.getLogger(__name__)


def fetch_npc_knowledge(
    client: EngineClient,
    npc_id: str,
) -> list[tuple[dict, dict]]:
    """Fetch all KNOWS_ABOUT edges for an NPC paired with their ground-truth events.

    For each KNOWS_ABOUT edge from the given NPC, retrieves the corresponding
    Event node. Edges whose event node cannot be found (get_node returns None)
    are silently skipped.

    Args:
        client: Synchronous EngineClient instance.
        npc_id: Character node ID of the NPC to query.

    Returns:
        List of (edge_props, event_props) tuples, one per found event.
        Each edge_props dict contains: src_id, dst_id, knowledge_state,
        distorted_summary, distortion_level. Each event_props dict contains
        the full Event node properties.

    Raises:
        EngineClientError: If the KNOWS_ABOUT edge query fails.
    """
    edges = client.get_graph_edges("KNOWS_ABOUT", src_id=npc_id)
    pairs: list[tuple[dict, dict]] = []
    for edge in edges:
        event_id = edge.get("dst_id")
        if not event_id:
            continue
        event = client.get_node("Event", event_id)
        if event is None:
            _logger.warning("event '%s' not found, skipping", event_id)
            continue
        pairs.append((edge, event))
    return pairs
