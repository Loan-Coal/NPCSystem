"""
Module: fetcher
Layer: demo_game.graph_panel
Purpose: Fetch graph snapshots from the engine and compute deltas between polls.
         Structural nodes/edges are fetched via the generic graph API; Belief and Goal
         nodes are synthesized from the typed admin endpoints because typed graph-edge
         endpoints (BELIEVES, PURSUES) are not populated by the engine.
Dependencies: demo_game.client (via dependency injection)
Used by: demo_game.graph_panel.poller (background polling thread)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

# ---------------------------------------------------------------------------
# Node and edge types to fetch
# ---------------------------------------------------------------------------

_STRUCTURAL_NODE_TYPES: tuple[str, ...] = (
    "Character",
    "Location",
    "Faction",
    "Event",
    "world_state",
)

_STRUCTURAL_EDGE_TYPES: tuple[str, ...] = (
    "KNOWS_ABOUT",
    "STANDS_WITH",
    "OPPOSES",
    "MEMBER_OF",
    "RELATES_TO",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


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
    properties: dict = field(default_factory=dict, hash=False, compare=False)


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
    properties: dict = field(default_factory=dict, hash=False, compare=False)


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


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def fetch_snapshot(client: EngineClient) -> GraphSnapshot:
    """Fetch the full graph snapshot by polling all registered node and edge types.

    Fetches structural nodes (Character, Location, Faction, Event, world_state) and
    structural edges (KNOWS_ABOUT, STANDS_WITH, OPPOSES, MEMBER_OF, RELATES_TO) via the
    generic graph API. Belief and Goal nodes are synthesized from the typed admin
    endpoints because the BELIEVES/PURSUES graph-edge endpoints return no data.

    Args:
        client: An EngineClient instance.

    Returns:
        Immutable GraphSnapshot with all current nodes and edges.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    char_ids: list[str] = []

    for node_type in _STRUCTURAL_NODE_TYPES:
        for raw in client.get_graph_nodes(node_type):
            nodes.append(GraphNode(id=raw["id"], node_type=node_type, properties=raw))
            if node_type == "Character":
                char_ids.append(raw["id"])

    for char_id in char_ids:
        for belief in client.get_beliefs(char_id):
            nodes.append(GraphNode(id=belief["id"], node_type="Belief", properties=belief))
            edges.append(GraphEdge(src_id=char_id, dst_id=belief["id"], edge_type="BELIEVES"))

        for goal in client.get_goals(char_id):
            nodes.append(GraphNode(id=goal["id"], node_type="Goal", properties=goal))
            edges.append(GraphEdge(src_id=char_id, dst_id=goal["id"], edge_type="PURSUES"))

    for edge_type in _STRUCTURAL_EDGE_TYPES:
        for raw in client.get_graph_edges(edge_type):
            edges.append(GraphEdge(
                src_id=raw["src_id"],
                dst_id=raw["dst_id"],
                edge_type=edge_type,
                properties=raw,
            ))

    return GraphSnapshot(nodes=tuple(nodes), edges=tuple(edges))


def compute_delta(prev: GraphSnapshot | None, curr: GraphSnapshot) -> GraphDelta:
    """Compute what is new in curr relative to prev.

    Identity is based on (id, node_type) for nodes and (src_id, dst_id, edge_type)
    for edges. Property changes on existing nodes/edges are not tracked.

    Args:
        prev: The previous snapshot, or None for the first poll (all items are new).
        curr: The current snapshot.

    Returns:
        GraphDelta containing only the newly-added nodes and edges.
    """
    if prev is None:
        return GraphDelta(new_nodes=curr.nodes, new_edges=curr.edges)

    prev_node_keys = {(n.id, n.node_type) for n in prev.nodes}
    prev_edge_keys = {(e.src_id, e.dst_id, e.edge_type) for e in prev.edges}

    new_nodes = tuple(n for n in curr.nodes if (n.id, n.node_type) not in prev_node_keys)
    new_edges = tuple(e for e in curr.edges if (e.src_id, e.dst_id, e.edge_type) not in prev_edge_keys)

    return GraphDelta(new_nodes=new_nodes, new_edges=new_edges)
