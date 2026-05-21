"""
Module: fetcher
Layer: demo_game.graph_panel
Purpose: Fetch graph snapshots from the engine and compute deltas between polls.
         STUB — dataclasses defined now; functions implemented in Phase 2.4.
Dependencies: demo_game.client (via dependency injection)
Used by: demo_game.ui.game_window (background polling thread in Phase 2.4)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraphNode:
    """A single node from the engine graph.

    Attributes:
        id: Node identifier.
        node_type: Registered type string (e.g. "Character", "Location").
        properties: Raw property dict returned by the engine.
    """

    id: str
    node_type: str
    properties: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """A single edge from the engine graph.

    Attributes:
        src_id: Source node identifier.
        dst_id: Destination node identifier.
        edge_type: Registered type string (e.g. "KNOWS_ABOUT", "STANDS_WITH").
        properties: Raw property dict returned by the engine.
    """

    src_id: str
    dst_id: str
    edge_type: str
    properties: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GraphSnapshot:
    """Immutable snapshot of all nodes and edges at one poll tick.

    Attributes:
        nodes: All nodes fetched in this snapshot.
        edges: All edges fetched in this snapshot.
    """

    nodes: tuple[GraphNode, ...] = field(default_factory=tuple)
    edges: tuple[GraphEdge, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GraphDelta:
    """Nodes and edges that are new since the previous snapshot.

    Used by the renderer to highlight recently-added graph elements.

    Attributes:
        new_nodes: Nodes present in current snapshot but not in previous.
        new_edges: Edges present in current snapshot but not in previous.
    """

    new_nodes: tuple[GraphNode, ...] = field(default_factory=tuple)
    new_edges: tuple[GraphEdge, ...] = field(default_factory=tuple)


def fetch_snapshot(client: object) -> GraphSnapshot:
    """Fetch the full graph snapshot by polling all registered node and edge types.

    Args:
        client: An EngineClient instance.

    Returns:
        Immutable GraphSnapshot with all current nodes and edges.

    Raises:
        NotImplementedError: Full implementation arrives in Phase 2.4.
    """
    raise NotImplementedError("fetch_snapshot() will be implemented in Phase 2.4")


def compute_delta(prev: GraphSnapshot, curr: GraphSnapshot) -> GraphDelta:
    """Compute what is new in curr relative to prev.

    Args:
        prev: The previous snapshot.
        curr: The current snapshot.

    Returns:
        GraphDelta containing only the newly-added nodes and edges.

    Raises:
        NotImplementedError: Full implementation arrives in Phase 2.4.
    """
    raise NotImplementedError("compute_delta() will be implemented in Phase 2.4")
